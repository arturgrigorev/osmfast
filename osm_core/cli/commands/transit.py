"""Transit command - extract public transport."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


TRANSIT_TYPES = {
    'stops': {
        'highway': frozenset({'bus_stop'}),
        'railway': frozenset({'station', 'halt', 'tram_stop', 'subway_entrance'}),
        'amenity': frozenset({'bus_station', 'ferry_terminal'}),
        'public_transport': frozenset({'stop_position', 'platform', 'station'})
    }
}


def setup_parser(subparsers):
    """Setup the transit subcommand parser."""
    parser = subparsers.add_parser(
        'transit',
        help='Extract public transport data',
        description='Extract bus stops, train stations, and transit routes'
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
        choices=['bus', 'rail', 'tram', 'subway', 'ferry', 'all'],
        default='all',
        help='Transit type'
    )
    parser.add_argument(
        '--stops-only',
        action='store_true',
        help='Only extract stops (no routes)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only'
    )

    parser.set_defaults(func=run)
    return parser


def get_transit_type(tags):
    """Determine transit type from tags."""
    if tags.get('highway') == 'bus_stop':
        return 'bus', 'stop'
    if tags.get('railway') == 'station':
        return 'rail', 'station'
    if tags.get('railway') == 'halt':
        return 'rail', 'halt'
    if tags.get('railway') == 'tram_stop':
        return 'tram', 'stop'
    if tags.get('railway') == 'subway_entrance':
        return 'subway', 'entrance'
    if tags.get('amenity') == 'bus_station':
        return 'bus', 'station'
    if tags.get('amenity') == 'ferry_terminal':
        return 'ferry', 'terminal'
    if tags.get('public_transport') == 'stop_position':
        return 'transit', 'stop'
    if tags.get('public_transport') == 'platform':
        return 'transit', 'platform'
    if tags.get('public_transport') == 'station':
        return 'transit', 'station'
    return None, None


def run(args):
    """Execute the transit command."""
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

    stops = []

    # Extract transit nodes
    for node in nodes:
        transit_type, feature_type = get_transit_type(node.tags)
        if not transit_type:
            continue

        if args.type != 'all' and transit_type != args.type:
            continue

        stops.append({
            'id': node.id,
            'type': 'node',
            'transit_type': transit_type,
            'feature_type': feature_type,
            'name': node.tags.get('name'),
            'ref': node.tags.get('ref'),
            'operator': node.tags.get('operator'),
            'network': node.tags.get('network'),
            'routes': node.tags.get('route_ref'),
            'shelter': node.tags.get('shelter'),
            'bench': node.tags.get('bench'),
            'wheelchair': node.tags.get('wheelchair'),
            'lat': float(node.lat),
            'lon': float(node.lon)
        })

    # Extract from ways (platforms, stations)
    for way in ways:
        transit_type, feature_type = get_transit_type(way.tags)
        if not transit_type:
            continue

        if args.type != 'all' and transit_type != args.type:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        stops.append({
            'id': way.id,
            'type': 'way',
            'transit_type': transit_type,
            'feature_type': feature_type,
            'name': way.tags.get('name'),
            'ref': way.tags.get('ref'),
            'operator': way.tags.get('operator'),
            'network': way.tags.get('network'),
            'routes': way.tags.get('route_ref'),
            'shelter': way.tags.get('shelter'),
            'bench': way.tags.get('bench'),
            'wheelchair': way.tags.get('wheelchair'),
            'lat': centroid_lat,
            'lon': centroid_lon
        })

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nPublic Transport: {args.input}")
        print("=" * 60)
        print(f"Total stops/stations: {len(stops)}")

        print("\nBy transit type:")
        by_type = {}
        for s in stops:
            t = s['transit_type']
            by_type[t] = by_type.get(t, 0) + 1
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        print("\nBy feature type:")
        by_feature = {}
        for s in stops:
            f = s['feature_type']
            by_feature[f] = by_feature.get(f, 0) + 1
        for f, count in sorted(by_feature.items(), key=lambda x: -x[1]):
            print(f"  {f}: {count}")

        with_name = sum(1 for s in stops if s['name'])
        with_operator = sum(1 for s in stops if s['operator'])
        print(f"\nWith name: {with_name} ({100*with_name//max(len(stops),1)}%)")
        print(f"With operator: {with_operator} ({100*with_operator//max(len(stops),1)}%)")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'geojson':
        features = []
        for s in stops:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s['lon'], s['lat']]},
                "properties": {k: v for k, v in s.items() if k not in ['lat', 'lon']}
            })
        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_str = json.dumps(stops, indent=2)

    elif args.format == 'csv':
        import csv
        import io
        buffer = io.StringIO()
        fieldnames = ['id', 'type', 'transit_type', 'feature_type', 'name', 'ref',
                      'operator', 'network', 'lat', 'lon']
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(stops)
        output_str = buffer.getvalue()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(stops)} transit stops to: {args.output}")
    else:
        print(output_str)

    return 0
