"""Extract traffic safety features to separate shapefiles.

This script handles traffic safety features that are typically point features
on nodes (traffic signals, crossings, stop signs) as well as way features
(traffic calming, barriers).
"""
import os
import sys
from typing import Dict, List, Set
from collections import defaultdict

from osm_core.parsing.mmap_parser import UltraFastOSMParser
from osm_core.filters.semantic_categories import TRAFFIC_SAFETY_ATTRIBUTES

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

# Traffic safety feature definitions
# Format: (output_name, tag_key, tag_value, description)
TRAFFIC_SAFETY_FEATURES = [
    # Traffic control - point features (nodes with highway=*)
    ('traffic_signals', 'highway', 'traffic_signals', 'Traffic signals at intersections'),
    ('crossings', 'highway', 'crossing', 'Pedestrian crossings'),
    ('stop_signs', 'highway', 'stop', 'Stop signs'),
    ('give_way_signs', 'highway', 'give_way', 'Give way/yield signs'),
    ('speed_cameras', 'highway', 'speed_camera', 'Speed cameras'),
    ('street_lamps', 'highway', 'street_lamp', 'Street lamps'),
    ('toll_gantries', 'highway', 'toll_gantry', 'Toll gantries'),

    # Traffic calming - can be on nodes or ways
    ('traffic_calming_table', 'traffic_calming', 'table', 'Speed tables'),
    ('traffic_calming_hump', 'traffic_calming', 'hump', 'Speed humps'),
    ('traffic_calming_bump', 'traffic_calming', 'bump', 'Speed bumps'),
    ('traffic_calming_island', 'traffic_calming', 'island', 'Traffic islands'),
    ('traffic_calming_cushion', 'traffic_calming', 'cushion', 'Speed cushions'),
    ('traffic_calming_choker', 'traffic_calming', 'choker', 'Chokers'),
    ('traffic_calming_chicane', 'traffic_calming', 'chicane', 'Chicanes'),
    ('traffic_calming_rumble_strip', 'traffic_calming', 'rumble_strip', 'Rumble strips'),

    # Safety barriers - can be nodes or ways
    ('barriers_bollard', 'barrier', 'bollard', 'Bollards'),
    ('barriers_guard_rail', 'barrier', 'guard_rail', 'Guard rails'),
    ('barriers_jersey_barrier', 'barrier', 'jersey_barrier', 'Jersey barriers'),
    ('barriers_cycle_barrier', 'barrier', 'cycle_barrier', 'Cycle barriers'),
    ('barriers_height_restrictor', 'barrier', 'height_restrictor', 'Height restrictors'),

    # Emergency features - typically nodes
    ('emergency_phone', 'emergency', 'phone', 'Emergency phones'),
    ('emergency_defibrillator', 'emergency', 'defibrillator', 'Defibrillators'),
    ('emergency_fire_hydrant', 'emergency', 'fire_hydrant', 'Fire hydrants'),
    ('emergency_life_ring', 'emergency', 'life_ring', 'Life rings'),

    # Surveillance - typically nodes
    ('surveillance', 'man_made', 'surveillance', 'Surveillance cameras'),
]


def extract_all_features(osm_file: str) -> Dict[str, Dict]:
    """Extract all traffic safety features in a single pass.

    Returns:
        Dictionary mapping feature name to {nodes: [...], ways: [...]}
    """
    parser = UltraFastOSMParser()
    print(f"Parsing {osm_file}...")
    nodes, ways = parser.parse_file_ultra_fast(osm_file)
    print(f"Parsed {len(nodes):,} nodes and {len(ways):,} ways")

    # Build lookup table: (tag_key, tag_value) -> feature_name
    feature_lookup = {}
    for name, tag_key, tag_value, desc in TRAFFIC_SAFETY_FEATURES:
        feature_lookup[(tag_key, tag_value)] = name

    # Initialize results
    results = {name: {'nodes': [], 'ways': []} for name, _, _, _ in TRAFFIC_SAFETY_FEATURES}

    # Build node coordinate lookup and extract matching nodes
    node_coords = {}
    print("Processing nodes...")
    for node in nodes:
        node_coords[node.id] = (node.lon, node.lat)

        # Check all tags for matches
        for tag_key, tag_value in node.tags.items():
            key = (tag_key, tag_value)
            if key in feature_lookup:
                feature_name = feature_lookup[key]
                results[feature_name]['nodes'].append({
                    'id': node.id,
                    'lon': node.lon,
                    'lat': node.lat,
                    'tags': node.tags
                })

    # Extract matching ways
    print("Processing ways...")
    for way in ways:
        # Check all tags for matches
        for tag_key, tag_value in way.tags.items():
            key = (tag_key, tag_value)
            if key in feature_lookup:
                feature_name = feature_lookup[key]

                # Build coordinates for way
                coords = []
                for nid in way.node_refs:
                    if nid in node_coords:
                        coords.append(node_coords[nid])

                if len(coords) >= 2:
                    # Determine if polygon or line
                    is_polygon = (
                        len(coords) >= 4 and
                        coords[0] == coords[-1] and
                        way.tags.get('area') == 'yes'
                    )
                    results[feature_name]['ways'].append({
                        'id': way.id,
                        'coords': coords,
                        'tags': way.tags,
                        'is_polygon': is_polygon
                    })

    return results


def write_shapefile_points(features: List[Dict], output_path: str, tag_filter: Set[str]) -> int:
    """Write point features to shapefile."""
    if not features:
        return 0

    w = shapefile.Writer(output_path, shapeType=shapefile.POINT)

    # Standard fields
    w.field('osm_id', 'C', 20)
    w.field('osm_type', 'C', 10)

    # Add filtered tag fields
    field_names = {}
    for tag in sorted(tag_filter):
        truncated = tag[:10]
        base = truncated
        counter = 1
        while truncated in field_names.values():
            truncated = f"{base[:10-len(str(counter))]}{counter}"
            counter += 1
        field_names[tag] = truncated
        w.field(truncated, 'C', 100)

    # Write features
    for f in features:
        w.point(f['lon'], f['lat'])
        record = {
            'osm_id': str(f['id']),
            'osm_type': 'node'
        }
        for tag, field in field_names.items():
            record[field] = str(f['tags'].get(tag, ''))[:254]
        w.record(**record)

    w.close()

    # Write projection file
    with open(f"{output_path}.prj", 'w') as prj:
        prj.write(WGS84_PRJ)

    return len(features)


def write_shapefile_lines(features: List[Dict], output_path: str, tag_filter: Set[str]) -> int:
    """Write line features to shapefile."""
    line_features = [f for f in features if not f.get('is_polygon', False)]
    if not line_features:
        return 0

    w = shapefile.Writer(output_path, shapeType=shapefile.POLYLINE)

    # Standard fields
    w.field('osm_id', 'C', 20)
    w.field('osm_type', 'C', 10)

    # Add filtered tag fields
    field_names = {}
    for tag in sorted(tag_filter):
        truncated = tag[:10]
        base = truncated
        counter = 1
        while truncated in field_names.values():
            truncated = f"{base[:10-len(str(counter))]}{counter}"
            counter += 1
        field_names[tag] = truncated
        w.field(truncated, 'C', 100)

    # Write features
    for f in line_features:
        w.line([f['coords']])
        record = {
            'osm_id': str(f['id']),
            'osm_type': 'way'
        }
        for tag, field in field_names.items():
            record[field] = str(f['tags'].get(tag, ''))[:254]
        w.record(**record)

    w.close()

    with open(f"{output_path}.prj", 'w') as prj:
        prj.write(WGS84_PRJ)

    return len(line_features)


def write_shapefile_polygons(features: List[Dict], output_path: str, tag_filter: Set[str]) -> int:
    """Write polygon features to shapefile."""
    poly_features = [f for f in features if f.get('is_polygon', False)]
    if not poly_features:
        return 0

    w = shapefile.Writer(output_path, shapeType=shapefile.POLYGON)

    # Standard fields
    w.field('osm_id', 'C', 20)
    w.field('osm_type', 'C', 10)

    # Add filtered tag fields
    field_names = {}
    for tag in sorted(tag_filter):
        truncated = tag[:10]
        base = truncated
        counter = 1
        while truncated in field_names.values():
            truncated = f"{base[:10-len(str(counter))]}{counter}"
            counter += 1
        field_names[tag] = truncated
        w.field(truncated, 'C', 100)

    # Write features
    for f in poly_features:
        w.poly([f['coords']])
        record = {
            'osm_id': str(f['id']),
            'osm_type': 'way'
        }
        for tag, field in field_names.items():
            record[field] = str(f['tags'].get(tag, ''))[:254]
        w.record(**record)

    w.close()

    with open(f"{output_path}.prj", 'w') as prj:
        prj.write(WGS84_PRJ)

    return len(poly_features)


def cleanup_empty_shapefiles(output_base: str, points: int, lines: int, polygons: int):
    """Remove empty shapefile sets."""
    for geom_type, count in [('points', points), ('lines', lines), ('polygons', polygons)]:
        if count == 0:
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                try:
                    os.unlink(f"{output_base}_{geom_type}{ext}")
                except FileNotFoundError:
                    pass


def main():
    osm_file = sys.argv[1] if len(sys.argv) > 1 else 'sydney.osm'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'sydney_traffic_safety'

    os.makedirs(output_dir, exist_ok=True)

    print(f"Extracting traffic safety features from {osm_file}")
    print(f"Output directory: {output_dir}")

    # Extract all features in single pass
    all_features = extract_all_features(osm_file)

    print("=" * 80)
    print(f"{'Feature':40} {'Points':>10} {'Lines':>10} {'Polygons':>10}")
    print("-" * 80)

    total_points = 0
    total_lines = 0
    total_polygons = 0

    for name, tag_key, tag_value, desc in TRAFFIC_SAFETY_FEATURES:
        feature_data = all_features[name]
        nodes = feature_data['nodes']
        ways = feature_data['ways']

        output_base = os.path.join(output_dir, name)

        # Write shapefiles
        points = write_shapefile_points(nodes, f"{output_base}_points", TRAFFIC_SAFETY_ATTRIBUTES)
        lines = write_shapefile_lines(ways, f"{output_base}_lines", TRAFFIC_SAFETY_ATTRIBUTES)
        polygons = write_shapefile_polygons(ways, f"{output_base}_polygons", TRAFFIC_SAFETY_ATTRIBUTES)

        # Clean up empty files
        cleanup_empty_shapefiles(output_base, points, lines, polygons)

        total_points += points
        total_lines += lines
        total_polygons += polygons

        if points + lines + polygons > 0:
            print(f"  {name:38} {points:>10,} {lines:>10,} {polygons:>10,}")

    print("=" * 80)
    print(f"{'TOTAL':40} {total_points:>10,} {total_lines:>10,} {total_polygons:>10,}")


if __name__ == '__main__':
    main()
