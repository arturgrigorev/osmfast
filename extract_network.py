"""Extract road network with flexible filtering and infrastructure overlays.

Supports:
- Road level selection (1-6 or presets: motorway, arterial, main, driveable, all)
- Infrastructure filters (bridges, tunnels, fords, embankments, covered)
- Combined extraction (e.g., all bridges on main roads)
- Full geometry calculations

Examples:
    # Extract main roads (motorway/trunk/primary/secondary/tertiary)
    python extract_network.py sydney.osm sydney_network --levels main

    # Extract only bridges
    python extract_network.py sydney.osm sydney_bridges --infrastructure bridges

    # Extract bridges and tunnels on main roads
    python extract_network.py sydney.osm sydney_main --levels main --infrastructure bridges,tunnels

    # Extract specific road levels (1-3)
    python extract_network.py sydney.osm sydney_arterial --levels 1,2,3

    # Extract all roads with all infrastructure
    python extract_network.py sydney.osm sydney_full --levels all --infrastructure all
"""
import os
import sys
import re
import argparse
from typing import Dict, List, Set, Optional, Tuple

from osm_core.parsing.mmap_parser import UltraFastOSMParser
from osm_core.utils.geo_utils import (
    calculate_line_length, calculate_sinuosity, calculate_line_bearing
)
from osm_core.filters.semantic_categories import (
    ROAD_LEVELS, ROAD_LEVEL_PRESETS, DEFAULT_SPEEDS,
    BRIDGE_TYPES, TUNNEL_TYPES, FORD_TYPES, EMBANKMENT_TYPES, COVERED_TYPES,
    INFRASTRUCTURE_CATEGORIES
)

try:
    import shapefile
except ImportError:
    print("ERROR: pyshp is required. Install with: pip install pyshp")
    sys.exit(1)

WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137,298.257223563]],'
    'PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'
)


def parse_road_levels(level_arg: str) -> Set[str]:
    """Parse road level argument into set of highway types.

    Args:
        level_arg: Comma-separated levels (1-6) or preset name

    Returns:
        Set of highway type strings
    """
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

        # Check if it's a preset
        if part in ROAD_LEVEL_PRESETS:
            highway_types.update(ROAD_LEVEL_PRESETS[part])
            continue

        # Check if it's a level number
        try:
            level = int(part)
            if level in ROAD_LEVELS:
                highway_types.update(ROAD_LEVELS[level])
            else:
                print(f"Warning: Unknown road level {level}, valid: 1-6")
        except ValueError:
            # Might be a direct highway type
            highway_types.add(part)

    return highway_types


def parse_infrastructure_filter(infra_arg: str) -> Dict[str, Set[str]]:
    """Parse infrastructure filter argument.

    Args:
        infra_arg: Comma-separated infrastructure types or 'all'

    Returns:
        Dict mapping tag names to accepted values
    """
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
        if part == 'bridges' or part == 'bridge':
            filters['bridge'] = BRIDGE_TYPES
        elif part == 'tunnels' or part == 'tunnel':
            filters['tunnel'] = TUNNEL_TYPES
        elif part == 'fords' or part == 'ford':
            filters['ford'] = FORD_TYPES
        elif part == 'embankments' or part == 'embankment':
            filters['embankment'] = EMBANKMENT_TYPES
        elif part == 'covered':
            filters['covered'] = COVERED_TYPES
        else:
            print(f"Warning: Unknown infrastructure type '{part}'")

    return filters


def matches_infrastructure(tags: Dict[str, str], infra_filters: Dict[str, Set[str]]) -> Tuple[bool, str]:
    """Check if way matches infrastructure filters.

    Args:
        tags: Way tags
        infra_filters: Dict mapping tag names to accepted values

    Returns:
        Tuple of (matches, infrastructure_type)
    """
    if not infra_filters:
        return True, ''

    for tag_name, accepted_values in infra_filters.items():
        tag_value = tags.get(tag_name, '')
        if tag_value and tag_value.lower() in accepted_values:
            return True, f"{tag_name}={tag_value}"

    return False, ''


def parse_maxspeed(maxspeed_str: str) -> Optional[float]:
    """Parse maxspeed tag value to km/h."""
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


def has_sidewalk(tags: Dict[str, str]) -> bool:
    """Check if road has sidewalk."""
    sidewalk = tags.get('sidewalk', '').lower()
    if sidewalk in ('both', 'left', 'right', 'yes', 'separate'):
        return True
    if tags.get('sidewalk:left', 'no') != 'no' or tags.get('sidewalk:right', 'no') != 'no':
        return True
    return False


def is_lit(tags: Dict[str, str]) -> bool:
    """Check if road has street lighting."""
    return tags.get('lit', '').lower() in ('yes', '24/7', 'automatic', 'limited')


def is_oneway(tags: Dict[str, str]) -> bool:
    """Check if road is one-way."""
    return tags.get('oneway', '').lower() in ('yes', '1', 'true', '-1')


def extract_network(osm_file: str,
                    highway_types: Set[str],
                    infra_filters: Dict[str, Set[str]] = None,
                    require_infrastructure: bool = False) -> List[Dict]:
    """Extract road network with flexible filtering.

    Args:
        osm_file: Path to OSM file
        highway_types: Set of highway types to extract
        infra_filters: Infrastructure filters (bridge, tunnel, etc.)
        require_infrastructure: If True, only extract roads matching infra_filters

    Returns:
        List of road features with geometry
    """
    parser = UltraFastOSMParser()
    print(f"Parsing {osm_file}...")
    nodes, ways = parser.parse_file_ultra_fast(osm_file)
    print(f"Parsed {len(nodes):,} nodes and {len(ways):,} ways")

    # Build node coordinate lookup
    node_coords = {}
    print("Building coordinate index...")
    for node in nodes:
        node_coords[node.id] = (node.lon, node.lat)

    # Extract matching roads
    roads = []
    print("Processing roads...")

    for way in ways:
        highway_type = way.tags.get('highway')

        # Check highway type filter
        if highway_types and highway_type not in highway_types:
            continue

        # Check infrastructure filter
        if infra_filters:
            matches, infra_type = matches_infrastructure(way.tags, infra_filters)
            if require_infrastructure and not matches:
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

        # Get infrastructure info
        bridge = way.tags.get('bridge', '')
        tunnel = way.tags.get('tunnel', '')
        ford = way.tags.get('ford', '')
        layer = way.tags.get('layer', '0')

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
            'bridge': bridge,
            'tunnel': tunnel,
            'ford': ford,
            'layer': layer,
            'infra_type': infra_type,
        })

    print(f"Extracted {len(roads):,} road segments")
    return roads


def write_network_shapefile(roads: List[Dict], output_path: str) -> int:
    """Write road network to shapefile."""
    if not roads:
        return 0

    w = shapefile.Writer(output_path, shapeType=shapefile.POLYLINE)

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
    # Infrastructure fields
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

    with open(f"{output_path}.prj", 'w') as prj:
        prj.write(WGS84_PRJ)

    return len(roads)


def print_summary(roads: List[Dict], infra_filters: Dict[str, Set[str]]):
    """Print extraction summary."""
    if not roads:
        print("No roads found!")
        return

    # Summary by highway type
    by_type = {}
    for road in roads:
        hw = road['highway']
        if hw not in by_type:
            by_type[hw] = {'count': 0, 'length_km': 0, 'lane_km': 0}
        by_type[hw]['count'] += 1
        by_type[hw]['length_km'] += road['length_km']
        by_type[hw]['lane_km'] += road['lane_km']

    total_length_km = sum(r['length_km'] for r in roads)
    total_lane_km = sum(r['lane_km'] for r in roads)

    print(f"\n{'Highway Type':20} {'Count':>10} {'Length (km)':>12} {'Lane-km':>12}")
    print("-" * 56)
    for hw_type in sorted(by_type.keys()):
        stats = by_type[hw_type]
        print(f"  {hw_type:18} {stats['count']:>10,} {stats['length_km']:>12,.1f} {stats['lane_km']:>12,.1f}")

    print("-" * 56)
    print(f"  {'TOTAL':18} {len(roads):>10,} {total_length_km:>12,.1f} {total_lane_km:>12,.1f}")

    # Infrastructure summary
    if infra_filters:
        print(f"\nInfrastructure breakdown:")
        bridges = sum(1 for r in roads if r['bridge'])
        tunnels = sum(1 for r in roads if r['tunnel'])
        fords = sum(1 for r in roads if r['ford'])

        bridge_km = sum(r['length_km'] for r in roads if r['bridge'])
        tunnel_km = sum(r['length_km'] for r in roads if r['tunnel'])
        ford_km = sum(r['length_km'] for r in roads if r['ford'])

        if bridges:
            print(f"  Bridges: {bridges:,} segments, {bridge_km:,.1f} km")
        if tunnels:
            print(f"  Tunnels: {tunnels:,} segments, {tunnel_km:,.1f} km")
        if fords:
            print(f"  Fords: {fords:,} segments, {ford_km:,.1f} km")

    # General infrastructure in data
    roads_with_sidewalk = sum(1 for r in roads if r['has_sidewalk'])
    roads_lit = sum(1 for r in roads if r['is_lit'])

    print(f"\nRoad attributes:")
    print(f"  With sidewalk: {roads_with_sidewalk:,} ({100*roads_with_sidewalk/len(roads):.1f}%)")
    print(f"  With lighting: {roads_lit:,} ({100*roads_lit/len(roads):.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description='Extract road network with flexible filtering',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Road Levels:
  1 - Motorways (motorway, motorway_link)
  2 - Trunk/Primary (trunk, trunk_link, primary, primary_link)
  3 - Secondary/Tertiary (secondary, secondary_link, tertiary, tertiary_link)
  4 - Local (residential, unclassified, living_street)
  5 - Service (service, track)
  6 - Non-motorized (pedestrian, footway, cycleway, path, steps)

Presets:
  motorway  - Level 1 only
  arterial  - Levels 1-2
  main      - Levels 1-3
  driveable - Levels 1-5
  all       - All levels

Infrastructure:
  bridges, tunnels, fords, embankments, covered, all

Examples:
  %(prog)s sydney.osm output --levels main
  %(prog)s sydney.osm output --levels 1,2,3
  %(prog)s sydney.osm output --infrastructure bridges
  %(prog)s sydney.osm output --levels main --infrastructure bridges,tunnels
        """
    )

    parser.add_argument('osm_file', help='Input OSM file')
    parser.add_argument('output_dir', help='Output directory')
    parser.add_argument('-l', '--levels', default='driveable',
                        help='Road levels: 1-6, presets (motorway/arterial/main/driveable/all), or comma-separated')
    parser.add_argument('-i', '--infrastructure', default='',
                        help='Infrastructure filter: bridges,tunnels,fords,embankments,covered,all')
    parser.add_argument('--only-infrastructure', action='store_true',
                        help='Only extract roads with specified infrastructure')
    parser.add_argument('--split-by-type', action='store_true',
                        help='Create separate shapefiles by highway type')
    parser.add_argument('--split-by-infra', action='store_true',
                        help='Create separate shapefiles by infrastructure type')

    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Parse filters
    highway_types = parse_road_levels(args.levels)
    infra_filters = parse_infrastructure_filter(args.infrastructure)

    print(f"Extracting road network from {args.osm_file}")
    print(f"Output directory: {args.output_dir}")
    print(f"Road levels: {args.levels} ({len(highway_types)} types)")
    if infra_filters:
        print(f"Infrastructure filter: {', '.join(infra_filters.keys())}")
    if args.only_infrastructure:
        print("Mode: Only roads with specified infrastructure")
    print("=" * 70)

    # Extract roads
    roads = extract_network(
        args.osm_file,
        highway_types,
        infra_filters,
        require_infrastructure=args.only_infrastructure
    )

    if not roads:
        print("No roads found!")
        return

    # Print summary
    print_summary(roads, infra_filters)

    # Write main shapefile
    output_path = os.path.join(args.output_dir, 'network_all')
    count = write_network_shapefile(roads, output_path)
    print(f"\nShapefile saved: {output_path}.shp ({count:,} features)")

    # Split by highway type if requested
    if args.split_by_type:
        print("\nExporting by highway type:")
        by_type = {}
        for road in roads:
            hw = road['highway']
            if hw not in by_type:
                by_type[hw] = []
            by_type[hw].append(road)

        for hw_type, type_roads in sorted(by_type.items()):
            if type_roads:
                type_path = os.path.join(args.output_dir, f'network_{hw_type}')
                type_count = write_network_shapefile(type_roads, type_path)
                type_length = sum(r['length_km'] for r in type_roads)
                print(f"  {hw_type}: {type_count:,} segments, {type_length:,.1f} km")

    # Split by infrastructure if requested
    if args.split_by_infra and infra_filters:
        print("\nExporting by infrastructure type:")

        # Bridges
        bridges = [r for r in roads if r['bridge']]
        if bridges:
            bridge_path = os.path.join(args.output_dir, 'network_bridges')
            bridge_count = write_network_shapefile(bridges, bridge_path)
            bridge_length = sum(r['length_km'] for r in bridges)
            print(f"  bridges: {bridge_count:,} segments, {bridge_length:,.1f} km")

        # Tunnels
        tunnels = [r for r in roads if r['tunnel']]
        if tunnels:
            tunnel_path = os.path.join(args.output_dir, 'network_tunnels')
            tunnel_count = write_network_shapefile(tunnels, tunnel_path)
            tunnel_length = sum(r['length_km'] for r in tunnels)
            print(f"  tunnels: {tunnel_count:,} segments, {tunnel_length:,.1f} km")

        # Fords
        fords = [r for r in roads if r['ford']]
        if fords:
            ford_path = os.path.join(args.output_dir, 'network_fords')
            ford_count = write_network_shapefile(fords, ford_path)
            ford_length = sum(r['length_km'] for r in fords)
            print(f"  fords: {ford_count:,} segments, {ford_length:,.1f} km")


if __name__ == '__main__':
    main()
