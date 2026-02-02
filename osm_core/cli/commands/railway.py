"""Railway command - extract rail network."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


RAILWAY_TYPES = frozenset({
    'rail', 'light_rail', 'subway', 'tram', 'monorail', 'narrow_gauge',
    'preserved', 'miniature', 'funicular'
})


def setup_parser(subparsers):
    """Setup the railway subcommand parser."""
    parser = subparsers.add_parser(
        'railway',
        help='Extract rail network',
        description='Extract railway lines, stations, and infrastructure'
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
        choices=['rail', 'light_rail', 'subway', 'tram', 'all'],
        default='all',
        help='Railway type'
    )
    parser.add_argument(
        '--lines-only',
        action='store_true',
        help='Only extract lines (no stations)'
    )
    parser.add_argument(
        '--stations-only',
        action='store_true',
        help='Only extract stations (no lines)'
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
    """Execute the railway command."""
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

    lines = []
    stations = []

    # Extract railway ways (lines)
    if not args.stations_only:
        for way in ways:
            railway = way.tags.get('railway')
            if railway not in RAILWAY_TYPES:
                continue

            if args.type != 'all' and railway != args.type:
                continue

            coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
            if len(coords) < 2:
                continue

            lines.append({
                'id': way.id,
                'railway': railway,
                'name': way.tags.get('name'),
                'ref': way.tags.get('ref'),
                'operator': way.tags.get('operator'),
                'electrified': way.tags.get('electrified'),
                'gauge': way.tags.get('gauge'),
                'tracks': way.tags.get('tracks'),
                'maxspeed': way.tags.get('maxspeed'),
                'length_m': round(calculate_length(coords), 1),
                'coordinates': coords
            })

    # Extract stations
    if not args.lines_only:
        for node in nodes:
            railway = node.tags.get('railway')
            if railway not in ('station', 'halt', 'stop'):
                continue

            stations.append({
                'id': node.id,
                'type': railway,
                'name': node.tags.get('name'),
                'ref': node.tags.get('ref'),
                'operator': node.tags.get('operator'),
                'network': node.tags.get('network'),
                'platforms': node.tags.get('platforms'),
                'lat': float(node.lat),
                'lon': float(node.lon)
            })

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nRailway Network: {args.input}")
        print("=" * 60)
        print(f"Lines: {len(lines)}")
        print(f"Stations: {len(stations)}")

        total_length = sum(l['length_m'] for l in lines)
        print(f"Total length: {total_length/1000:.1f} km")

        print("\nLines by type:")
        by_type = {}
        for l in lines:
            t = l['railway']
            if t not in by_type:
                by_type[t] = {'count': 0, 'length': 0}
            by_type[t]['count'] += 1
            by_type[t]['length'] += l['length_m']
        for t, data in sorted(by_type.items(), key=lambda x: -x[1]['length']):
            print(f"  {t}: {data['count']} segments, {data['length']/1000:.1f} km")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'geojson':
        features = []
        for l in lines:
            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": l['coordinates']},
                "properties": {k: v for k, v in l.items() if k != 'coordinates'}
            })
        for s in stations:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s['lon'], s['lat']]},
                "properties": {k: v for k, v in s.items() if k not in ['lat', 'lon']}
            })
        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output = {'lines': [{k: v for k, v in l.items() if k != 'coordinates'} for l in lines],
                  'stations': stations}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'csv':
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['element', 'id', 'railway', 'name', 'operator', 'length_m', 'lat', 'lon'])
        for l in lines:
            writer.writerow(['line', l['id'], l['railway'], l['name'], l['operator'], l['length_m'], '', ''])
        for s in stations:
            writer.writerow(['station', s['id'], s['type'], s['name'], s['operator'], '', s['lat'], s['lon']])
        output_str = buffer.getvalue()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(lines)} lines, {len(stations)} stations to: {args.output}")
    else:
        print(output_str)

    return 0
