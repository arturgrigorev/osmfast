"""Water command - extract water features."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser
from ...utils.geo_utils import calculate_polygon_area


WATER_TYPES = {
    'natural': frozenset({'water', 'bay', 'beach', 'coastline', 'spring', 'hot_spring'}),
    'waterway': frozenset({'river', 'stream', 'canal', 'drain', 'ditch', 'waterfall', 'dam'}),
    'water': frozenset({'lake', 'pond', 'reservoir', 'basin', 'lagoon', 'river', 'canal'}),
    'landuse': frozenset({'reservoir', 'basin'})
}


def setup_parser(subparsers):
    """Setup the water subcommand parser."""
    parser = subparsers.add_parser(
        'water',
        help='Extract water features',
        description='Extract rivers, lakes, and other water features'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv'],
        default='geojson',
        help='Output format (default: geojson)'
    )
    parser.add_argument(
        '--type',
        choices=['river', 'lake', 'stream', 'canal', 'coastline', 'all'],
        default='all',
        help='Water feature type'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only'
    )

    parser.set_defaults(func=run)
    return parser


def is_water_feature(tags):
    """Check if tags indicate a water feature."""
    for key, values in WATER_TYPES.items():
        if key in tags and tags[key] in values:
            return True, key, tags[key]
    return False, None, None


def run(args):
    """Execute the water command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    node_coords = {}
    for node in nodes:
        node_coords[node.id] = [float(node.lon), float(node.lat)]

    features = []

    # Extract water nodes (springs, etc.)
    for node in nodes:
        is_water, key, value = is_water_feature(node.tags)
        if not is_water:
            continue

        if args.type != 'all' and value != args.type:
            continue

        features.append({
            'id': node.id,
            'type': 'node',
            'water_type': value,
            'tag_key': key,
            'name': node.tags.get('name'),
            'lat': float(node.lat),
            'lon': float(node.lon),
            'geometry_type': 'Point',
            'coordinates': [[float(node.lon), float(node.lat)]]
        })

    # Extract water ways
    for way in ways:
        is_water, key, value = is_water_feature(way.tags)
        if not is_water:
            continue

        if args.type != 'all' and value != args.type:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if len(coords) < 2:
            continue

        is_closed = len(coords) > 2 and coords[0] == coords[-1]

        feature = {
            'id': way.id,
            'type': 'way',
            'water_type': value,
            'tag_key': key,
            'name': way.tags.get('name'),
            'geometry_type': 'Polygon' if is_closed else 'LineString',
            'coordinates': coords
        }

        if is_closed:
            feature['area_sqm'] = round(calculate_polygon_area(coords), 1)

        features.append(feature)

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nWater Features: {args.input}")
        print("=" * 60)
        print(f"Total: {len(features)}")

        by_type = {}
        for f in features:
            t = f['water_type']
            by_type[t] = by_type.get(t, 0) + 1

        print("\nBy type:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'geojson':
        geojson_features = []
        for f in features:
            coords = f['coordinates']
            if f['geometry_type'] == 'Point':
                geom = {"type": "Point", "coordinates": coords[0]}
            elif f['geometry_type'] == 'Polygon':
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                geom = {"type": "Polygon", "coordinates": [coords]}
            else:
                geom = {"type": "LineString", "coordinates": coords}

            geojson_features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "id": f['id'],
                    "water_type": f['water_type'],
                    "name": f['name'],
                    "area_sqm": f.get('area_sqm')
                }
            })
        output = {"type": "FeatureCollection", "features": geojson_features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_str = json.dumps([{k: v for k, v in f.items() if k != 'coordinates'}
                                  for f in features], indent=2)

    elif args.format == 'csv':
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'type', 'water_type', 'name', 'geometry_type', 'area_sqm'])
        for f in features:
            writer.writerow([f['id'], f['type'], f['water_type'], f['name'],
                           f['geometry_type'], f.get('area_sqm', '')])
        output_str = buffer.getvalue()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(features)} water features to: {args.output}")
    else:
        print(output_str)

    return 0
