"""Extract road network with geometry calculations to shapefiles.

Includes calculated fields:
- length_m, length_km: Road segment length
- sinuosity: Curvature ratio (1.0 = straight)
- bearing: Direction in degrees
- speed_kph: Speed from maxspeed or default
- travel_min: Estimated travel time
- lane_km: lanes × length_km
- has_sidewalk, is_lit, is_oneway: Boolean flags
"""
import os
import sys
import re
from typing import Dict, List, Set, Optional

from osm_core.parsing.mmap_parser import UltraFastOSMParser
from osm_core.utils.geo_utils import (
    calculate_line_length, calculate_sinuosity, calculate_line_bearing
)
from osm_core.filters.semantic_categories import (
    ROAD_ATTRIBUTES, DEFAULT_SPEEDS, HIGHWAY_TYPES
)

# Try to import pyshp
try:
    import shapefile
    HAS_PYSHP = True
except ImportError:
    HAS_PYSHP = False
    print("ERROR: pyshp is required. Install with: pip install pyshp")
    sys.exit(1)

# WGS84 projection definition
WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137,298.257223563]],'
    'PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'
)

# Road types to extract (grouped by category)
ROAD_CATEGORIES = {
    'motorway': ['motorway', 'motorway_link'],
    'trunk': ['trunk', 'trunk_link'],
    'primary': ['primary', 'primary_link'],
    'secondary': ['secondary', 'secondary_link'],
    'tertiary': ['tertiary', 'tertiary_link'],
    'residential': ['residential', 'living_street'],
    'service': ['service'],
    'unclassified': ['unclassified'],
    'pedestrian': ['pedestrian', 'footway', 'path', 'steps'],
    'cycleway': ['cycleway'],
}

# All road types to extract
ALL_ROAD_TYPES = set()
for types in ROAD_CATEGORIES.values():
    ALL_ROAD_TYPES.update(types)


def parse_maxspeed(maxspeed_str: str) -> Optional[float]:
    """Parse maxspeed tag value to km/h.

    Handles formats: '50', '50 km/h', '30 mph', etc.
    """
    if not maxspeed_str:
        return None

    maxspeed_str = maxspeed_str.strip().lower()

    # Handle 'none', 'signals', etc.
    if maxspeed_str in ('none', 'signals', 'variable', 'walk'):
        return None

    # Extract numeric part
    match = re.match(r'(\d+(?:\.\d+)?)', maxspeed_str)
    if not match:
        return None

    value = float(match.group(1))

    # Convert mph to km/h
    if 'mph' in maxspeed_str:
        value = value * 1.60934

    return value


def has_sidewalk(tags: Dict[str, str]) -> bool:
    """Check if road has sidewalk."""
    sidewalk = tags.get('sidewalk', '').lower()
    if sidewalk in ('both', 'left', 'right', 'yes', 'separate'):
        return True
    # Check sidewalk:* tags
    if tags.get('sidewalk:left') or tags.get('sidewalk:right'):
        if tags.get('sidewalk:left', 'no') != 'no' or tags.get('sidewalk:right', 'no') != 'no':
            return True
    return False


def is_lit(tags: Dict[str, str]) -> bool:
    """Check if road has street lighting."""
    lit = tags.get('lit', '').lower()
    return lit in ('yes', '24/7', 'automatic', 'limited')


def is_oneway(tags: Dict[str, str]) -> bool:
    """Check if road is one-way."""
    oneway = tags.get('oneway', '').lower()
    return oneway in ('yes', '1', 'true', '-1')


def calculate_road_geometry(coords: List[List[float]], tags: Dict[str, str],
                            highway_type: str) -> Dict:
    """Calculate all geometry attributes for a road segment."""
    # Basic length calculations
    length_m = calculate_line_length(coords)
    length_km = length_m / 1000.0

    # Sinuosity and bearing
    sinuosity = calculate_sinuosity(coords)
    bearing = calculate_line_bearing(coords)

    # Speed: use maxspeed if available, otherwise default
    maxspeed = parse_maxspeed(tags.get('maxspeed', ''))
    if maxspeed is None:
        maxspeed = DEFAULT_SPEEDS.get(highway_type, 40)
    speed_kph = maxspeed

    # Travel time in minutes
    travel_min = (length_km / speed_kph * 60) if speed_kph > 0 else 0

    # Lane calculations
    lanes_str = tags.get('lanes', '')
    try:
        lanes = int(lanes_str) if lanes_str else 2  # Default to 2 lanes
    except ValueError:
        lanes = 2
    lane_km = lanes * length_km

    return {
        'length_m': round(length_m, 1),
        'length_km': round(length_km, 3),
        'sinuosity': round(sinuosity, 3),
        'bearing': round(bearing, 1),
        'speed_kph': round(speed_kph, 0),
        'travel_min': round(travel_min, 2),
        'lanes': lanes,
        'lane_km': round(lane_km, 3),
        'has_sidewalk': 1 if has_sidewalk(tags) else 0,
        'is_lit': 1 if is_lit(tags) else 0,
        'is_oneway': 1 if is_oneway(tags) else 0,
    }


def extract_roads(osm_file: str, road_types: Set[str] = None) -> List[Dict]:
    """Extract roads with geometry calculations.

    Args:
        osm_file: Path to OSM file
        road_types: Set of highway types to extract (None = all)

    Returns:
        List of road features with geometry attributes
    """
    if road_types is None:
        road_types = ALL_ROAD_TYPES

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
        if highway_type not in road_types:
            continue

        # Build coordinates
        coords = []
        for nid in way.node_refs:
            if nid in node_coords:
                coords.append(list(node_coords[nid]))

        if len(coords) < 2:
            continue

        # Calculate geometry
        geometry = calculate_road_geometry(coords, way.tags, highway_type)

        roads.append({
            'id': way.id,
            'coords': coords,
            'tags': way.tags,
            'highway': highway_type,
            'geometry': geometry
        })

    print(f"Extracted {len(roads):,} road segments")
    return roads


def write_roads_shapefile(roads: List[Dict], output_path: str,
                          include_osm_tags: bool = True) -> int:
    """Write roads to shapefile with geometry attributes."""
    if not roads:
        return 0

    w = shapefile.Writer(output_path, shapeType=shapefile.POLYLINE)

    # Standard ID fields
    w.field('osm_id', 'C', 20)
    w.field('highway', 'C', 20)

    # OSM tag fields (from ROAD_ATTRIBUTES)
    osm_fields = ['name', 'ref', 'maxspeed', 'lanes', 'surface', 'oneway',
                  'lit', 'sidewalk', 'access', 'toll', 'bridge', 'tunnel']
    for field in osm_fields:
        w.field(field[:10], 'C', 100)

    # Geometry calculated fields
    w.field('length_m', 'N', 12, 1)
    w.field('length_km', 'N', 10, 3)
    w.field('sinuosity', 'N', 8, 3)
    w.field('bearing', 'N', 6, 1)
    w.field('speed_kph', 'N', 5, 0)
    w.field('travel_min', 'N', 8, 2)
    w.field('lane_cnt', 'N', 3, 0)  # 'lanes' truncated
    w.field('lane_km', 'N', 10, 3)
    w.field('has_sidwlk', 'N', 1, 0)  # Boolean
    w.field('is_lit', 'N', 1, 0)      # Boolean
    w.field('is_oneway', 'N', 1, 0)   # Boolean

    # Write features
    for road in roads:
        w.line([road['coords']])

        tags = road['tags']
        geom = road['geometry']

        record = {
            'osm_id': str(road['id']),
            'highway': road['highway'],
            # OSM tags
            'name': str(tags.get('name', ''))[:100],
            'ref': str(tags.get('ref', ''))[:100],
            'maxspeed': str(tags.get('maxspeed', ''))[:100],
            'lanes': str(tags.get('lanes', ''))[:100],
            'surface': str(tags.get('surface', ''))[:100],
            'oneway': str(tags.get('oneway', ''))[:100],
            'lit': str(tags.get('lit', ''))[:100],
            'sidewalk': str(tags.get('sidewalk', ''))[:100],
            'access': str(tags.get('access', ''))[:100],
            'toll': str(tags.get('toll', ''))[:100],
            'bridge': str(tags.get('bridge', ''))[:100],
            'tunnel': str(tags.get('tunnel', ''))[:100],
            # Geometry fields
            'length_m': geom['length_m'],
            'length_km': geom['length_km'],
            'sinuosity': geom['sinuosity'],
            'bearing': geom['bearing'],
            'speed_kph': geom['speed_kph'],
            'travel_min': geom['travel_min'],
            'lane_cnt': geom['lanes'],
            'lane_km': geom['lane_km'],
            'has_sidwlk': geom['has_sidewalk'],
            'is_lit': geom['is_lit'],
            'is_oneway': geom['is_oneway'],
        }
        w.record(**record)

    w.close()

    # Write projection file
    with open(f"{output_path}.prj", 'w') as prj:
        prj.write(WGS84_PRJ)

    return len(roads)


def main():
    osm_file = sys.argv[1] if len(sys.argv) > 1 else 'sydney.osm'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'sydney_roads'

    os.makedirs(output_dir, exist_ok=True)

    print(f"Extracting road network with geometry from {osm_file}")
    print(f"Output directory: {output_dir}")
    print("=" * 70)

    # Extract all roads
    roads = extract_roads(osm_file, ALL_ROAD_TYPES)

    if not roads:
        print("No roads found!")
        return

    # Calculate summary statistics
    total_length_km = sum(r['geometry']['length_km'] for r in roads)
    total_lane_km = sum(r['geometry']['lane_km'] for r in roads)
    roads_with_sidewalk = sum(1 for r in roads if r['geometry']['has_sidewalk'])
    roads_lit = sum(1 for r in roads if r['geometry']['is_lit'])

    # Group by highway type for summary
    by_type = {}
    for road in roads:
        hw = road['highway']
        if hw not in by_type:
            by_type[hw] = {'count': 0, 'length_km': 0, 'lane_km': 0}
        by_type[hw]['count'] += 1
        by_type[hw]['length_km'] += road['geometry']['length_km']
        by_type[hw]['lane_km'] += road['geometry']['lane_km']

    # Print summary by type
    print(f"\n{'Highway Type':20} {'Count':>10} {'Length (km)':>12} {'Lane-km':>12}")
    print("-" * 56)
    for hw_type in sorted(by_type.keys()):
        stats = by_type[hw_type]
        print(f"  {hw_type:18} {stats['count']:>10,} {stats['length_km']:>12,.1f} {stats['lane_km']:>12,.1f}")

    print("-" * 56)
    print(f"  {'TOTAL':18} {len(roads):>10,} {total_length_km:>12,.1f} {total_lane_km:>12,.1f}")

    # Print infrastructure summary
    print(f"\nInfrastructure:")
    print(f"  Roads with sidewalk: {roads_with_sidewalk:,} ({100*roads_with_sidewalk/len(roads):.1f}%)")
    print(f"  Roads with lighting: {roads_lit:,} ({100*roads_lit/len(roads):.1f}%)")

    # Write combined shapefile
    output_path = os.path.join(output_dir, 'roads_all_geometry')
    count = write_roads_shapefile(roads, output_path)
    print(f"\nShapefile saved: {output_path}.shp ({count:,} features)")

    # Write separate shapefiles by category
    print("\nExporting by category:")
    for category, types in ROAD_CATEGORIES.items():
        category_roads = [r for r in roads if r['highway'] in types]
        if category_roads:
            cat_path = os.path.join(output_dir, f'roads_{category}_geometry')
            cat_count = write_roads_shapefile(category_roads, cat_path)
            cat_length = sum(r['geometry']['length_km'] for r in category_roads)
            print(f"  {category}: {cat_count:,} segments, {cat_length:,.1f} km")


if __name__ == '__main__':
    main()
