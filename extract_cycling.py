"""Extract cycling infrastructure to shapefiles.

Extracts:
- Dedicated cycleways (highway=cycleway)
- Paths with bicycle access (highway=path + bicycle=designated/yes)
- Roads with cycle lanes (cycleway=lane/track/shared_lane)
- Roads with bicycle access (bicycle=designated/yes)
- Cycling amenities (bicycle_parking, bicycle_rental, bicycle_repair_station)
- Bicycle shops

Includes geometry calculations for routes.
"""
import os
import sys
from typing import Dict, List, Set

from osm_core.parsing.mmap_parser import UltraFastOSMParser
from osm_core.utils.geo_utils import (
    calculate_line_length, calculate_sinuosity, calculate_line_bearing
)
from osm_core.filters.semantic_categories import CYCLING_ATTRIBUTES

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

# Cycling infrastructure categories
CYCLING_FEATURES = {
    # Dedicated cycling routes (highway tag)
    'cycleways': {
        'tag': 'highway',
        'values': {'cycleway'},
        'type': 'way',
        'description': 'Dedicated cycleways'
    },
    'shared_paths': {
        'tag': 'highway',
        'values': {'path', 'bridleway'},
        'filter': lambda tags: tags.get('bicycle') in ('designated', 'yes', 'permissive'),
        'type': 'way',
        'description': 'Shared paths with bicycle access'
    },
    # Roads with cycle infrastructure
    'roads_with_cycle_lanes': {
        'tag': 'cycleway',
        'values': {'lane', 'track', 'shared_lane', 'share_busway', 'shoulder', 'separate'},
        'type': 'way',
        'description': 'Roads with cycle lanes'
    },
    'roads_bicycle_designated': {
        'tag': 'bicycle',
        'values': {'designated'},
        'filter': lambda tags: tags.get('highway') in (
            'residential', 'tertiary', 'secondary', 'primary', 'unclassified', 'service'
        ),
        'type': 'way',
        'description': 'Roads with designated bicycle access'
    },
    # Cycling amenities (point features)
    'bicycle_parking': {
        'tag': 'amenity',
        'values': {'bicycle_parking'},
        'type': 'node',
        'description': 'Bicycle parking'
    },
    'bicycle_rental': {
        'tag': 'amenity',
        'values': {'bicycle_rental'},
        'type': 'node',
        'description': 'Bicycle rental stations'
    },
    'bicycle_repair': {
        'tag': 'amenity',
        'values': {'bicycle_repair_station'},
        'type': 'node',
        'description': 'Bicycle repair stations'
    },
    'bicycle_shops': {
        'tag': 'shop',
        'values': {'bicycle'},
        'type': 'node',
        'description': 'Bicycle shops'
    },
}


def extract_cycling_infrastructure(osm_file: str) -> Dict[str, Dict]:
    """Extract all cycling infrastructure in a single pass."""
    parser = UltraFastOSMParser()
    print(f"Parsing {osm_file}...")
    nodes, ways = parser.parse_file_ultra_fast(osm_file)
    print(f"Parsed {len(nodes):,} nodes and {len(ways):,} ways")

    # Initialize results
    results = {name: {'nodes': [], 'ways': []} for name in CYCLING_FEATURES}

    # Build node coordinate lookup
    node_coords = {}
    print("Processing nodes...")
    for node in nodes:
        node_coords[node.id] = (node.lon, node.lat)

        # Check node features
        for feat_name, feat_def in CYCLING_FEATURES.items():
            if feat_def['type'] != 'node':
                continue

            tag_key = feat_def['tag']
            tag_values = feat_def['values']

            if node.tags.get(tag_key) in tag_values:
                # Apply additional filter if present
                if 'filter' in feat_def and not feat_def['filter'](node.tags):
                    continue

                results[feat_name]['nodes'].append({
                    'id': node.id,
                    'lon': node.lon,
                    'lat': node.lat,
                    'tags': node.tags
                })

    # Process ways
    print("Processing ways...")
    for way in ways:
        # Check way features
        for feat_name, feat_def in CYCLING_FEATURES.items():
            if feat_def['type'] != 'way':
                continue

            tag_key = feat_def['tag']
            tag_values = feat_def['values']

            if way.tags.get(tag_key) in tag_values:
                # Apply additional filter if present
                if 'filter' in feat_def and not feat_def['filter'](way.tags):
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

                results[feat_name]['ways'].append({
                    'id': way.id,
                    'coords': coords,
                    'tags': way.tags,
                    'length_m': round(length_m, 1),
                    'length_km': round(length_km, 3),
                    'sinuosity': round(sinuosity, 3),
                    'bearing': round(bearing, 1),
                })

    return results


def write_point_shapefile(features: List[Dict], output_path: str) -> int:
    """Write point features to shapefile."""
    if not features:
        return 0

    w = shapefile.Writer(output_path, shapeType=shapefile.POINT)

    # Fields
    w.field('osm_id', 'C', 20)
    w.field('name', 'C', 100)
    w.field('operator', 'C', 100)
    w.field('capacity', 'C', 20)
    w.field('covered', 'C', 10)
    w.field('fee', 'C', 10)
    w.field('access', 'C', 50)

    for f in features:
        w.point(f['lon'], f['lat'])
        tags = f['tags']
        w.record(
            osm_id=str(f['id']),
            name=str(tags.get('name', ''))[:100],
            operator=str(tags.get('operator', ''))[:100],
            capacity=str(tags.get('capacity', ''))[:20],
            covered=str(tags.get('covered', ''))[:10],
            fee=str(tags.get('fee', ''))[:10],
            access=str(tags.get('access', ''))[:50],
        )

    w.close()
    with open(f"{output_path}.prj", 'w') as prj:
        prj.write(WGS84_PRJ)

    return len(features)


def write_line_shapefile(features: List[Dict], output_path: str) -> int:
    """Write line features to shapefile with geometry attributes."""
    if not features:
        return 0

    w = shapefile.Writer(output_path, shapeType=shapefile.POLYLINE)

    # Fields
    w.field('osm_id', 'C', 20)
    w.field('name', 'C', 100)
    w.field('highway', 'C', 30)
    w.field('cycleway', 'C', 30)
    w.field('bicycle', 'C', 20)
    w.field('surface', 'C', 30)
    w.field('smoothness', 'C', 20)
    w.field('width', 'C', 10)
    w.field('lit', 'C', 10)
    w.field('segregated', 'C', 10)
    w.field('oneway', 'C', 10)
    w.field('length_m', 'N', 12, 1)
    w.field('length_km', 'N', 10, 3)
    w.field('sinuosity', 'N', 8, 3)
    w.field('bearing', 'N', 6, 1)

    for f in features:
        w.line([f['coords']])
        tags = f['tags']
        w.record(
            osm_id=str(f['id']),
            name=str(tags.get('name', ''))[:100],
            highway=str(tags.get('highway', ''))[:30],
            cycleway=str(tags.get('cycleway', ''))[:30],
            bicycle=str(tags.get('bicycle', ''))[:20],
            surface=str(tags.get('surface', ''))[:30],
            smoothness=str(tags.get('smoothness', ''))[:20],
            width=str(tags.get('width', ''))[:10],
            lit=str(tags.get('lit', ''))[:10],
            segregated=str(tags.get('segregated', ''))[:10],
            oneway=str(tags.get('oneway', ''))[:10],
            length_m=f['length_m'],
            length_km=f['length_km'],
            sinuosity=f['sinuosity'],
            bearing=f['bearing'],
        )

    w.close()
    with open(f"{output_path}.prj", 'w') as prj:
        prj.write(WGS84_PRJ)

    return len(features)


def cleanup_empty(output_base: str, count: int, suffix: str):
    """Remove empty shapefile if count is 0."""
    if count == 0:
        for ext in ['.shp', '.shx', '.dbf', '.prj']:
            try:
                os.unlink(f"{output_base}_{suffix}{ext}")
            except FileNotFoundError:
                pass


def main():
    osm_file = sys.argv[1] if len(sys.argv) > 1 else 'sydney.osm'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'sydney_cycling'

    os.makedirs(output_dir, exist_ok=True)

    print(f"Extracting cycling infrastructure from {osm_file}")
    print(f"Output directory: {output_dir}")

    # Extract all features
    all_features = extract_cycling_infrastructure(osm_file)

    print("=" * 80)
    print(f"{'Category':<35} {'Points':>10} {'Lines':>10} {'Length (km)':>12}")
    print("-" * 80)

    total_points = 0
    total_lines = 0
    total_length_km = 0

    for feat_name, feat_def in CYCLING_FEATURES.items():
        data = all_features[feat_name]
        nodes = data['nodes']
        ways = data['ways']

        output_base = os.path.join(output_dir, feat_name)

        if feat_def['type'] == 'node':
            points = write_point_shapefile(nodes, f"{output_base}_points")
            cleanup_empty(output_base, points, 'points')
            length_km = 0
            lines = 0
        else:
            lines = write_line_shapefile(ways, f"{output_base}_lines")
            cleanup_empty(output_base, lines, 'lines')
            length_km = sum(w['length_km'] for w in ways)
            points = 0

        total_points += points
        total_lines += lines
        total_length_km += length_km

        if points + lines > 0:
            desc = feat_def['description']
            print(f"  {desc:<33} {points:>10,} {lines:>10,} {length_km:>12,.1f}")

    print("=" * 80)
    print(f"{'TOTAL':<35} {total_points:>10,} {total_lines:>10,} {total_length_km:>12,.1f}")

    # Write combined cycling routes shapefile
    print("\nCreating combined cycling routes...")
    all_routes = []
    for feat_name in ['cycleways', 'shared_paths', 'roads_with_cycle_lanes', 'roads_bicycle_designated']:
        all_routes.extend(all_features[feat_name]['ways'])

    if all_routes:
        combined_path = os.path.join(output_dir, 'all_cycling_routes_lines')
        combined_count = write_line_shapefile(all_routes, combined_path)
        combined_length = sum(r['length_km'] for r in all_routes)
        print(f"  Combined routes: {combined_count:,} segments, {combined_length:,.1f} km")


if __name__ == '__main__':
    main()
