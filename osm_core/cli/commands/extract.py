"""Extract command implementation."""
import os
import sys
from typing import Dict, Any, List, Set

from osm_core.api import OSMFast
from osm_core.filters.osm_filter import OSMFilter
from osm_core.filters.semantic_categories import (
    ROAD_ATTRIBUTES, BUILDING_ATTRIBUTES, AMENITY_ATTRIBUTES, TRAFFIC_SAFETY_ATTRIBUTES,
    CYCLING_ATTRIBUTES, DEFAULT_SPEEDS,
    ROAD_LEVELS, ROAD_LEVEL_PRESETS, BRIDGE_TYPES, TUNNEL_TYPES, FORD_TYPES,
    EMBANKMENT_TYPES, COVERED_TYPES
)
from osm_core.utils.geo_utils import (
    calculate_line_length, calculate_sinuosity, calculate_line_bearing
)


def cmd_extract(args) -> int:
    """Handle extract command.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    input_file = args.input_file
    base = os.path.splitext(input_file)[0]

    # Determine output format first (needed for default extension)
    if args.format:
        output_format = args.format
    elif args.output_file:
        output_format = _determine_format(args, args.output_file)
    else:
        output_format = 'json'  # default

    # Determine output file with correct extension
    if args.output_file:
        output_file = args.output_file
    else:
        # Use appropriate extension for format
        ext_map = {
            'json': '.json',
            'geojson': '.geojson',
            'csv': '.csv',
            'xml': '.xml',
            'osm': '.osm',
            'shapefile': ''  # shapefile uses base path
        }
        ext = ext_map.get(output_format, '.json')
        output_file = f"{base}_features{ext}"

    # Build filter from arguments
    osm_filter = _build_filter(args)

    # Create extractor
    extractor = OSMFast(osm_filter)

    # Extract based on format
    if output_format == 'geojson':
        result = extractor.extract_to_geojson(input_file, output_file)
    elif output_format == 'csv':
        result = extractor.extract_to_csv(
            input_file, output_file,
            include_metadata=args.include_metadata
        )
    elif output_format in ('xml', 'osm'):
        result = extractor.extract_to_xml(input_file, output_file)
    elif output_format == 'shapefile':
        try:
            # Check if network extraction with filters is requested
            road_levels = getattr(args, 'road_levels', None)
            infrastructure = getattr(args, 'infrastructure', None)
            only_infrastructure = getattr(args, 'only_infrastructure', False)

            if road_levels or infrastructure:
                result = _extract_network_with_filters(
                    input_file, output_file,
                    road_levels, infrastructure, only_infrastructure
                )
            # Check if road geometry extraction is requested
            elif getattr(args, 'road_geometry', False):
                result = _extract_roads_with_geometry(input_file, output_file, osm_filter)
            else:
                # Determine tag filter
                tag_filter = None
                if getattr(args, 'road_attributes', False):
                    tag_filter = ROAD_ATTRIBUTES
                elif getattr(args, 'building_attributes', False):
                    tag_filter = BUILDING_ATTRIBUTES
                elif getattr(args, 'amenity_attributes', False):
                    tag_filter = AMENITY_ATTRIBUTES
                elif getattr(args, 'traffic_safety_attributes', False):
                    tag_filter = TRAFFIC_SAFETY_ATTRIBUTES
                elif getattr(args, 'cycling_attributes', False):
                    tag_filter = CYCLING_ATTRIBUTES
                result = extractor.extract_to_shapefile(
                    input_file, output_file,
                    include_all_tags=getattr(args, 'include_all_tags', False),
                    tag_filter=tag_filter
                )
        except ImportError as e:
            print(f"osmfast: error: {e}", file=sys.stderr)
            return 1
    else:  # json
        result = extractor.extract_to_json(input_file, output_file)

    # Print summary unless quiet
    if not args.quiet:
        _print_summary(result, output_format)

    return 0


def _determine_format(args, output_file: str) -> str:
    """Determine output format from args or file extension."""
    if args.format:
        return args.format

    ext = os.path.splitext(output_file)[1].lower()
    format_map = {
        '.geojson': 'geojson',
        '.json': 'json',
        '.csv': 'csv',
        '.xml': 'xml',
        '.osm': 'osm',
        '.shp': 'shapefile'
    }
    return format_map.get(ext, 'json')


def _build_filter(args) -> OSMFilter:
    """Build OSMFilter from command line arguments."""
    bbox = None
    if args.bbox:
        bbox = {
            'top': args.bbox[0],
            'left': args.bbox[1],
            'bottom': args.bbox[2],
            'right': args.bbox[3]
        }

    return OSMFilter.from_osmosis_args(
        accept_ways=args.accept_ways,
        reject_ways=args.reject_ways,
        accept_nodes=args.accept_nodes,
        reject_nodes=args.reject_nodes,
        used_node=args.used_node,
        reject_ways_global=args.reject_ways_global,
        reject_relations_global=args.reject_relations,
        reject_nodes_global=args.reject_nodes_global,
        bounding_box=bbox
    )


def _print_summary(result: Dict[str, Any], output_format: str) -> None:
    """Print extraction summary."""
    metadata = result.get('metadata', {})
    processing_time = metadata.get('processing_time_seconds', 0)

    if output_format == 'shapefile':
        print(f"\nShapefile export complete:")
        print(f"  Points: {metadata.get('points_exported', 0)}")
        print(f"  Lines: {metadata.get('lines_exported', 0)}")
        print(f"  Polygons: {metadata.get('polygons_exported', 0)}")
        print(f"  Total: {metadata.get('total_features_exported', 0)}")
        files = metadata.get('files_created', [])
        if files:
            print(f"  Files: {', '.join(os.path.basename(f) for f in files)}")
        # Show road geometry stats if available
        road_geom = metadata.get('road_geometry')
        if road_geom:
            print(f"  Total length: {road_geom.get('total_length_km', 0):,.1f} km")
            print(f"  Total lane-km: {road_geom.get('total_lane_km', 0):,.1f} km")
        # Show infrastructure stats if available
        infra = metadata.get('infrastructure')
        if infra:
            bridges = infra.get('bridges', 0)
            tunnels = infra.get('tunnels', 0)
            if bridges:
                print(f"  Bridges: {bridges:,}")
            if tunnels:
                print(f"  Tunnels: {tunnels:,}")
        print(f"  Time: {processing_time:.3f}s")
    elif 'features_extracted' in metadata:
        features = metadata['features_extracted']
        print(f"\nExtraction complete ({output_format}):")
        print(f"  Amenities: {features.get('amenities', 0)}")
        print(f"  Highways: {features.get('highways', 0)}")
        print(f"  Buildings: {features.get('buildings', 0)}")
        print(f"  Total: {features.get('total', 0)}")
        print(f"  Time: {processing_time:.3f}s")
    else:
        elements = metadata.get('elements', {})
        print(f"\nExport complete ({output_format}):")
        print(f"  Nodes: {elements.get('nodes', 0)}")
        print(f"  Ways: {elements.get('ways', 0)}")
        print(f"  Time: {processing_time:.3f}s")


def _extract_roads_with_geometry(input_file: str, output_base: str,
                                  osm_filter: OSMFilter) -> Dict[str, Any]:
    """Extract roads with geometry calculations.

    Args:
        input_file: Input OSM file path
        output_base: Output base path (without extension)
        osm_filter: OSM filter (used for accept filters)

    Returns:
        Result dictionary with metadata
    """
    import re
    import time

    try:
        import shapefile
    except ImportError:
        raise ImportError(
            "pyshp is required for Shapefile export. "
            "Install with: pip install osmfast[shapefile]"
        )

    from osm_core.parsing.mmap_parser import UltraFastOSMParser

    start_time = time.time()

    # WGS84 projection
    WGS84_PRJ = (
        'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
        'SPHEROID["WGS_1984",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'
    )

    # Determine which highway types to extract from filter
    highway_types = set()
    if osm_filter.tag_filter and osm_filter.tag_filter.rules:
        for rule in osm_filter.tag_filter.rules:
            if rule.action == 'accept' and rule.key == 'highway':
                if rule.value == '*':
                    # Accept all highway types
                    highway_types = {
                        'motorway', 'motorway_link', 'trunk', 'trunk_link',
                        'primary', 'primary_link', 'secondary', 'secondary_link',
                        'tertiary', 'tertiary_link', 'residential', 'living_street',
                        'service', 'unclassified', 'pedestrian', 'footway',
                        'cycleway', 'path', 'track', 'steps'
                    }
                    break
                else:
                    highway_types.add(rule.value)

    # Default to major roads if no filter specified
    if not highway_types:
        highway_types = {
            'motorway', 'motorway_link', 'trunk', 'trunk_link',
            'primary', 'primary_link', 'secondary', 'secondary_link',
            'tertiary', 'tertiary_link', 'residential', 'unclassified', 'service'
        }

    # Parse file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(input_file)

    # Build node coordinate lookup
    node_coords = {}
    for node in nodes:
        node_coords[node.id] = (node.lon, node.lat)

    # Helper functions
    def parse_maxspeed(maxspeed_str):
        if not maxspeed_str:
            return None
        maxspeed_str = maxspeed_str.strip().lower()
        if maxspeed_str in ('none', 'signals', 'variable', 'walk'):
            return None
        match = re.match(r'(\d+(?:\.\d+)?)', maxspeed_str)
        if not match:
            return None
        value = float(match.group(1))
        if 'mph' in maxspeed_str:
            value = value * 1.60934
        return value

    def has_sidewalk(tags):
        sidewalk = tags.get('sidewalk', '').lower()
        if sidewalk in ('both', 'left', 'right', 'yes', 'separate'):
            return True
        if tags.get('sidewalk:left', 'no') != 'no' or tags.get('sidewalk:right', 'no') != 'no':
            return True
        return False

    def is_lit(tags):
        return tags.get('lit', '').lower() in ('yes', '24/7', 'automatic', 'limited')

    def is_oneway(tags):
        return tags.get('oneway', '').lower() in ('yes', '1', 'true', '-1')

    # Extract matching roads
    roads = []
    for way in ways:
        highway_type = way.tags.get('highway')
        if highway_type not in highway_types:
            continue

        # Build coordinates
        coords = []
        for nid in way.node_refs:
            if nid in node_coords:
                coords.append(list(node_coords[nid]))

        if len(coords) < 2:
            continue

        # Calculate geometry
        length_m = calculate_line_length(coords)
        length_km = length_m / 1000.0
        sinuosity = calculate_sinuosity(coords)
        bearing = calculate_line_bearing(coords)

        maxspeed = parse_maxspeed(way.tags.get('maxspeed', ''))
        if maxspeed is None:
            maxspeed = DEFAULT_SPEEDS.get(highway_type, 40)

        travel_min = (length_km / maxspeed * 60) if maxspeed > 0 else 0

        try:
            lanes = int(way.tags.get('lanes', '2'))
        except ValueError:
            lanes = 2
        lane_km = lanes * length_km

        roads.append({
            'id': way.id,
            'coords': coords,
            'tags': way.tags,
            'highway': highway_type,
            'length_m': round(length_m, 1),
            'length_km': round(length_km, 3),
            'sinuosity': round(sinuosity, 3),
            'bearing': round(bearing, 1),
            'speed_kph': round(maxspeed, 0),
            'travel_min': round(travel_min, 2),
            'lanes': lanes,
            'lane_km': round(lane_km, 3),
            'has_sidewalk': 1 if has_sidewalk(way.tags) else 0,
            'is_lit': 1 if is_lit(way.tags) else 0,
            'is_oneway': 1 if is_oneway(way.tags) else 0,
        })

    # Write shapefile
    output_path = os.path.splitext(output_base)[0]
    w = shapefile.Writer(f"{output_path}_lines", shapeType=shapefile.POLYLINE)

    # Fields
    w.field('osm_id', 'C', 20)
    w.field('highway', 'C', 20)
    w.field('name', 'C', 100)
    w.field('ref', 'C', 50)
    w.field('maxspeed', 'C', 20)
    w.field('surface', 'C', 50)
    w.field('length_m', 'N', 12, 1)
    w.field('length_km', 'N', 10, 3)
    w.field('sinuosity', 'N', 8, 3)
    w.field('bearing', 'N', 6, 1)
    w.field('speed_kph', 'N', 5, 0)
    w.field('travel_min', 'N', 8, 2)
    w.field('lanes', 'N', 3, 0)
    w.field('lane_km', 'N', 10, 3)
    w.field('has_sidwlk', 'N', 1, 0)
    w.field('is_lit', 'N', 1, 0)
    w.field('is_oneway', 'N', 1, 0)

    for road in roads:
        w.line([road['coords']])
        w.record(
            osm_id=str(road['id']),
            highway=road['highway'],
            name=str(road['tags'].get('name', ''))[:100],
            ref=str(road['tags'].get('ref', ''))[:50],
            maxspeed=str(road['tags'].get('maxspeed', ''))[:20],
            surface=str(road['tags'].get('surface', ''))[:50],
            length_m=road['length_m'],
            length_km=road['length_km'],
            sinuosity=road['sinuosity'],
            bearing=road['bearing'],
            speed_kph=road['speed_kph'],
            travel_min=road['travel_min'],
            lanes=road['lanes'],
            lane_km=road['lane_km'],
            has_sidwlk=road['has_sidewalk'],
            is_lit=road['is_lit'],
            is_oneway=road['is_oneway'],
        )

    w.close()

    # Write projection file
    with open(f"{output_path}_lines.prj", 'w') as prj:
        prj.write(WGS84_PRJ)

    # Calculate statistics
    total_length_km = sum(r['length_km'] for r in roads)
    total_lane_km = sum(r['lane_km'] for r in roads)

    processing_time = time.time() - start_time

    return {
        'metadata': {
            'format': 'shapefile',
            'files_created': [f"{output_path}_lines.shp"],
            'points_exported': 0,
            'lines_exported': len(roads),
            'polygons_exported': 0,
            'total_features_exported': len(roads),
            'processing_time_seconds': processing_time,
            'road_geometry': {
                'total_length_km': round(total_length_km, 1),
                'total_lane_km': round(total_lane_km, 1),
            }
        }
    }


def _parse_road_levels(level_arg: str) -> Set[str]:
    """Parse road level argument into set of highway types."""
    if not level_arg:
        return set()

    level_arg = level_arg.lower().strip()

    # Check for preset
    if level_arg in ROAD_LEVEL_PRESETS:
        return set(ROAD_LEVEL_PRESETS[level_arg])

    # Parse comma-separated levels
    highway_types = set()
    for part in level_arg.split(','):
        part = part.strip()
        if part in ROAD_LEVEL_PRESETS:
            highway_types.update(ROAD_LEVEL_PRESETS[part])
            continue
        try:
            level = int(part)
            if level in ROAD_LEVELS:
                highway_types.update(ROAD_LEVELS[level])
        except ValueError:
            highway_types.add(part)

    return highway_types


def _parse_infrastructure_filter(infra_arg: str) -> Dict[str, Set[str]]:
    """Parse infrastructure filter argument."""
    if not infra_arg:
        return {}

    infra_arg = infra_arg.lower().strip()
    filters = {}

    if infra_arg == 'all':
        filters['bridge'] = BRIDGE_TYPES
        filters['tunnel'] = TUNNEL_TYPES
        filters['ford'] = FORD_TYPES
        filters['embankment'] = EMBANKMENT_TYPES
        filters['covered'] = COVERED_TYPES
        return filters

    for part in infra_arg.split(','):
        part = part.strip()
        if part in ('bridges', 'bridge'):
            filters['bridge'] = BRIDGE_TYPES
        elif part in ('tunnels', 'tunnel'):
            filters['tunnel'] = TUNNEL_TYPES
        elif part in ('fords', 'ford'):
            filters['ford'] = FORD_TYPES
        elif part in ('embankments', 'embankment'):
            filters['embankment'] = EMBANKMENT_TYPES
        elif part == 'covered':
            filters['covered'] = COVERED_TYPES

    return filters


def _extract_network_with_filters(input_file: str, output_base: str,
                                   road_levels: str, infrastructure: str,
                                   only_infrastructure: bool) -> Dict[str, Any]:
    """Extract road network with flexible filtering.

    Args:
        input_file: Input OSM file path
        output_base: Output base path
        road_levels: Road level filter argument
        infrastructure: Infrastructure filter argument
        only_infrastructure: Only extract roads with infrastructure

    Returns:
        Result dictionary with metadata
    """
    import time

    try:
        import shapefile
    except ImportError:
        raise ImportError(
            "pyshp is required for Shapefile export. "
            "Install with: pip install osmfast[shapefile]"
        )

    from osm_core.parsing.mmap_parser import UltraFastOSMParser

    start_time = time.time()

    WGS84_PRJ = (
        'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
        'SPHEROID["WGS_1984",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'
    )

    # Parse filters
    highway_types = _parse_road_levels(road_levels) if road_levels else set()
    infra_filters = _parse_infrastructure_filter(infrastructure) if infrastructure else {}

    # Parse file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(input_file)

    # Build node coordinate lookup
    node_coords = {}
    for node in nodes:
        node_coords[node.id] = (node.lon, node.lat)

    # Helper functions
    def parse_maxspeed(maxspeed_str):
        if not maxspeed_str:
            return None
        maxspeed_str = maxspeed_str.strip().lower()
        if maxspeed_str in ('none', 'signals', 'variable', 'walk'):
            return None
        import re
        match = re.match(r'(\d+(?:\.\d+)?)', maxspeed_str)
        if not match:
            return None
        value = float(match.group(1))
        if 'mph' in maxspeed_str:
            value = value * 1.60934
        return value

    def has_sidewalk(tags):
        sidewalk = tags.get('sidewalk', '').lower()
        if sidewalk in ('both', 'left', 'right', 'yes', 'separate'):
            return True
        if tags.get('sidewalk:left', 'no') != 'no' or tags.get('sidewalk:right', 'no') != 'no':
            return True
        return False

    def is_lit(tags):
        return tags.get('lit', '').lower() in ('yes', '24/7', 'automatic', 'limited')

    def is_oneway(tags):
        return tags.get('oneway', '').lower() in ('yes', '1', 'true', '-1')

    def matches_infrastructure(tags):
        if not infra_filters:
            return True, ''
        for tag_name, accepted_values in infra_filters.items():
            tag_value = tags.get(tag_name, '')
            if tag_value and tag_value.lower() in accepted_values:
                return True, f"{tag_name}={tag_value}"
        return False, ''

    # Extract matching roads
    roads = []
    for way in ways:
        highway_type = way.tags.get('highway')

        # Check highway type filter
        if highway_types and highway_type not in highway_types:
            continue

        # Check infrastructure filter
        if infra_filters:
            matches, infra_type = matches_infrastructure(way.tags)
            if only_infrastructure and not matches:
                continue
        else:
            infra_type = ''

        # Build coordinates
        coords = []
        for nid in way.node_refs:
            if nid in node_coords:
                coords.append(list(node_coords[nid]))

        if len(coords) < 2:
            continue

        # Calculate geometry
        length_m = calculate_line_length(coords)
        length_km = length_m / 1000.0
        sinuosity = calculate_sinuosity(coords)
        bearing = calculate_line_bearing(coords)

        maxspeed = parse_maxspeed(way.tags.get('maxspeed', ''))
        if maxspeed is None:
            maxspeed = DEFAULT_SPEEDS.get(highway_type, 40)

        travel_min = (length_km / maxspeed * 60) if maxspeed > 0 else 0

        try:
            lanes = int(way.tags.get('lanes', '2'))
        except ValueError:
            lanes = 2
        lane_km = lanes * length_km

        roads.append({
            'id': way.id,
            'coords': coords,
            'tags': way.tags,
            'highway': highway_type or '',
            'length_m': round(length_m, 1),
            'length_km': round(length_km, 3),
            'sinuosity': round(sinuosity, 3),
            'bearing': round(bearing, 1),
            'speed_kph': round(maxspeed, 0),
            'travel_min': round(travel_min, 2),
            'lanes': lanes,
            'lane_km': round(lane_km, 3),
            'has_sidewalk': 1 if has_sidewalk(way.tags) else 0,
            'is_lit': 1 if is_lit(way.tags) else 0,
            'is_oneway': 1 if is_oneway(way.tags) else 0,
            'bridge': way.tags.get('bridge', ''),
            'tunnel': way.tags.get('tunnel', ''),
            'ford': way.tags.get('ford', ''),
            'layer': way.tags.get('layer', '0'),
            'infra_type': infra_type,
        })

    # Write shapefile
    output_path = os.path.splitext(output_base)[0]
    w = shapefile.Writer(f"{output_path}_lines", shapeType=shapefile.POLYLINE)

    # Fields
    w.field('osm_id', 'C', 20)
    w.field('highway', 'C', 20)
    w.field('name', 'C', 100)
    w.field('ref', 'C', 50)
    w.field('maxspeed', 'C', 20)
    w.field('surface', 'C', 50)
    w.field('length_m', 'N', 12, 1)
    w.field('length_km', 'N', 10, 3)
    w.field('sinuosity', 'N', 8, 3)
    w.field('bearing', 'N', 6, 1)
    w.field('speed_kph', 'N', 5, 0)
    w.field('travel_min', 'N', 8, 2)
    w.field('lanes', 'N', 3, 0)
    w.field('lane_km', 'N', 10, 3)
    w.field('has_sidwlk', 'N', 1, 0)
    w.field('is_lit', 'N', 1, 0)
    w.field('is_oneway', 'N', 1, 0)
    w.field('bridge', 'C', 20)
    w.field('tunnel', 'C', 20)
    w.field('ford', 'C', 10)
    w.field('layer', 'C', 5)
    w.field('infra_type', 'C', 30)

    for road in roads:
        w.line([road['coords']])
        w.record(
            osm_id=str(road['id']),
            highway=road['highway'],
            name=str(road['tags'].get('name', ''))[:100],
            ref=str(road['tags'].get('ref', ''))[:50],
            maxspeed=str(road['tags'].get('maxspeed', ''))[:20],
            surface=str(road['tags'].get('surface', ''))[:50],
            length_m=road['length_m'],
            length_km=road['length_km'],
            sinuosity=road['sinuosity'],
            bearing=road['bearing'],
            speed_kph=road['speed_kph'],
            travel_min=road['travel_min'],
            lanes=road['lanes'],
            lane_km=road['lane_km'],
            has_sidwlk=road['has_sidewalk'],
            is_lit=road['is_lit'],
            is_oneway=road['is_oneway'],
            bridge=road['bridge'][:20],
            tunnel=road['tunnel'][:20],
            ford=road['ford'][:10],
            layer=road['layer'][:5],
            infra_type=road['infra_type'][:30],
        )

    w.close()

    with open(f"{output_path}_lines.prj", 'w') as prj:
        prj.write(WGS84_PRJ)

    # Calculate statistics
    total_length_km = sum(r['length_km'] for r in roads)
    total_lane_km = sum(r['lane_km'] for r in roads)
    bridges = sum(1 for r in roads if r['bridge'])
    tunnels = sum(1 for r in roads if r['tunnel'])

    processing_time = time.time() - start_time

    return {
        'metadata': {
            'format': 'shapefile',
            'files_created': [f"{output_path}_lines.shp"],
            'points_exported': 0,
            'lines_exported': len(roads),
            'polygons_exported': 0,
            'total_features_exported': len(roads),
            'processing_time_seconds': processing_time,
            'road_geometry': {
                'total_length_km': round(total_length_km, 1),
                'total_lane_km': round(total_lane_km, 1),
            },
            'infrastructure': {
                'bridges': bridges,
                'tunnels': tunnels,
            }
        }
    }
