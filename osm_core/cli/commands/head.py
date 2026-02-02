"""Head command - first N elements from OSM file."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the head subcommand parser."""
    parser = subparsers.add_parser(
        'head',
        help='First N elements from file',
        description='Extract the first N elements from an OSM file'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '-n', '--count',
        type=int,
        default=10,
        help='Number of elements (default: 10)'
    )
    parser.add_argument(
        '--type',
        choices=['nodes', 'ways', 'all'],
        default='all',
        help='Element type (default: all)'
    )
    parser.add_argument(
        '--filter',
        help='Filter by tag (e.g., highway=*, amenity=restaurant)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv', 'text'],
        default='text',
        help='Output format (default: text)'
    )
    parser.add_argument(
        '--skip',
        type=int,
        default=0,
        help='Skip first N elements before selecting'
    )

    parser.set_defaults(func=run)
    return parser


def parse_filter(filter_str):
    """Parse filter string."""
    if '=' not in filter_str:
        return filter_str, '*'
    key, value = filter_str.split('=', 1)
    return key.strip(), value.strip()


def matches_filter(tags, key, value):
    """Check if tags match filter."""
    if key not in tags:
        return False
    if value == '*':
        return True
    return tags[key] == value


def run(args):
    """Execute the head command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    node_coords = {}
    for node in nodes:
        node_coords[node.id] = (float(node.lon), float(node.lat))

    # Parse filter
    filter_key, filter_value = None, None
    if args.filter:
        filter_key, filter_value = parse_filter(args.filter)

    # Collect elements
    elements = []

    if args.type in ('nodes', 'all'):
        for node in nodes:
            if filter_key and not matches_filter(node.tags, filter_key, filter_value):
                continue
            elements.append({
                'id': node.id,
                'type': 'node',
                'lon': float(node.lon),
                'lat': float(node.lat),
                'tags': node.tags
            })

    if args.type in ('ways', 'all'):
        for way in ways:
            if filter_key and not matches_filter(way.tags, filter_key, filter_value):
                continue
            coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
            if not coords:
                continue
            centroid_lon = sum(c[0] for c in coords) / len(coords)
            centroid_lat = sum(c[1] for c in coords) / len(coords)
            elements.append({
                'id': way.id,
                'type': 'way',
                'lon': centroid_lon,
                'lat': centroid_lat,
                'coords': coords,
                'tags': way.tags
            })

    # Apply skip and limit
    selected = elements[args.skip:args.skip + args.count]

    elapsed = time.time() - start_time

    # Text output (default, to stdout)
    if args.format == 'text' and not args.output:
        print(f"First {len(selected)} elements (of {len(elements)} total):")
        print("-" * 60)
        for i, elem in enumerate(selected, 1):
            print(f"\n{i}. {elem['type'].upper()} {elem['id']}")
            print(f"   Location: {elem['lat']:.6f}, {elem['lon']:.6f}")
            if elem['tags']:
                print(f"   Tags:")
                for k, v in list(elem['tags'].items())[:10]:
                    print(f"     {k} = {v}")
                if len(elem['tags']) > 10:
                    print(f"     ... and {len(elem['tags']) - 10} more tags")
        print(f"\n[{elapsed:.3f}s]")
        return 0

    if not args.output:
        args.output = '/dev/stdout'

    # Generate output
    if args.format == 'geojson':
        features = []
        for elem in selected:
            if elem['type'] == 'way' and elem.get('coords') and len(elem['coords']) > 1:
                is_closed = len(elem['coords']) > 2 and elem['coords'][0] == elem['coords'][-1]
                if is_closed:
                    geom = {"type": "Polygon", "coordinates": [elem['coords']]}
                else:
                    geom = {"type": "LineString", "coordinates": elem['coords']}
            else:
                geom = {"type": "Point", "coordinates": [elem['lon'], elem['lat']]}

            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {"id": elem['id'], "osm_type": elem['type'], **elem['tags']}
            })
        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_str = json.dumps([{k: v for k, v in e.items() if k != 'coords'} for e in selected], indent=2)

    elif args.format == 'csv':
        import csv, io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'type', 'lat', 'lon', 'name', 'tags'])
        for e in selected:
            tags_str = ';'.join(f"{k}={v}" for k, v in e['tags'].items())
            writer.writerow([e['id'], e['type'], e['lat'], e['lon'], e['tags'].get('name', ''), tags_str])
        output_str = buffer.getvalue()

    elif args.format == 'text':
        lines = [f"First {len(selected)} elements:"]
        for elem in selected:
            tags_preview = ', '.join(f"{k}={v}" for k, v in list(elem['tags'].items())[:5])
            lines.append(f"{elem['type']} {elem['id']}: {tags_preview}")
        output_str = '\n'.join(lines)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    if args.output != '/dev/stdout':
        print(f"\nHead complete:")
        print(f"  Elements: {len(selected)} of {len(elements)}")
        print(f"  Output: {args.output}")
        print(f"  Time: {elapsed:.3f}s")

    return 0
