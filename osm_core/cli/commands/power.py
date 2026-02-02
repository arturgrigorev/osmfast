"""Power command - extract power infrastructure."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the power subcommand parser."""
    parser = subparsers.add_parser(
        'power',
        help='Extract power infrastructure',
        description='Extract power lines, substations, and generators'
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
        choices=['line', 'substation', 'generator', 'tower', 'pole', 'all'],
        default='all',
        help='Power feature type'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only'
    )

    parser.set_defaults(func=run)
    return parser


def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate distance in meters."""
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat/2)**2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def calculate_length(coords):
    """Calculate total length in meters."""
    if len(coords) < 2:
        return 0
    total = 0
    for i in range(len(coords) - 1):
        total += haversine_distance(coords[i][0], coords[i][1],
                                    coords[i+1][0], coords[i+1][1])
    return total


def run(args):
    """Execute the power command."""
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

    # Extract power nodes
    for node in nodes:
        power = node.tags.get('power')
        if not power:
            continue

        if args.type != 'all' and power != args.type:
            continue

        features.append({
            'id': node.id,
            'element_type': 'node',
            'power': power,
            'name': node.tags.get('name'),
            'operator': node.tags.get('operator'),
            'voltage': node.tags.get('voltage'),
            'output': node.tags.get('generator:output:electricity'),
            'source': node.tags.get('generator:source'),
            'lat': float(node.lat),
            'lon': float(node.lon),
            'geometry_type': 'Point'
        })

    # Extract power ways
    for way in ways:
        power = way.tags.get('power')
        if not power:
            continue

        if args.type != 'all' and power != args.type:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if len(coords) < 2:
            continue

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        feature = {
            'id': way.id,
            'element_type': 'way',
            'power': power,
            'name': way.tags.get('name'),
            'operator': way.tags.get('operator'),
            'voltage': way.tags.get('voltage'),
            'cables': way.tags.get('cables'),
            'wires': way.tags.get('wires'),
            'lat': centroid_lat,
            'lon': centroid_lon,
            'geometry_type': 'LineString',
            'coordinates': coords
        }

        if power == 'line':
            feature['length_m'] = round(calculate_length(coords), 1)

        features.append(feature)

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nPower Infrastructure: {args.input}")
        print("=" * 60)
        print(f"Total features: {len(features)}")

        print("\nBy type:")
        by_type = {}
        for f in features:
            t = f['power']
            if t not in by_type:
                by_type[t] = {'count': 0, 'length': 0}
            by_type[t]['count'] += 1
            by_type[t]['length'] += f.get('length_m', 0)

        for t, data in sorted(by_type.items(), key=lambda x: -x[1]['count']):
            if data['length'] > 0:
                print(f"  {t}: {data['count']} ({data['length']/1000:.1f} km)")
            else:
                print(f"  {t}: {data['count']}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'geojson':
        geojson_features = []
        for f in features:
            if f['geometry_type'] == 'Point':
                geom = {"type": "Point", "coordinates": [f['lon'], f['lat']]}
            else:
                geom = {"type": "LineString", "coordinates": f.get('coordinates', [])}

            props = {k: v for k, v in f.items()
                     if k not in ['lat', 'lon', 'coordinates', 'geometry_type']}
            geojson_features.append({"type": "Feature", "geometry": geom, "properties": props})

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
        writer.writerow(['id', 'power', 'name', 'operator', 'voltage', 'length_m', 'lat', 'lon'])
        for f in features:
            writer.writerow([f['id'], f['power'], f['name'], f['operator'],
                           f['voltage'], f.get('length_m', ''), f['lat'], f['lon']])
        output_str = buffer.getvalue()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(features)} power features to: {args.output}")
    else:
        print(output_str)

    return 0
