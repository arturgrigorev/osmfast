"""Sample command - random sample of features."""
import argparse
import json
import random
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the sample subcommand parser."""
    parser = subparsers.add_parser(
        'sample',
        help='Random sample of features',
        description='Extract a random sample of features from OSM data'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '-n', '--count',
        type=int,
        default=100,
        help='Number of features to sample (default: 100)'
    )
    parser.add_argument(
        '--percent', '-p',
        type=float,
        help='Percentage of features to sample (overrides --count)'
    )
    parser.add_argument(
        '--type',
        choices=['nodes', 'ways', 'all'],
        default='all',
        help='Element type to sample (default: all)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        help='Random seed for reproducibility'
    )
    parser.add_argument(
        '--filter',
        help='Filter by tag (e.g., highway=*, amenity=restaurant)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv', 'osm'],
        default='geojson',
        help='Output format (default: geojson)'
    )

    parser.set_defaults(func=run)
    return parser


def parse_filter(filter_str):
    """Parse filter string into key, value."""
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
    """Execute the sample command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    if args.seed is not None:
        random.seed(args.seed)

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

    # Collect elements based on type
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
                'node_refs': way.node_refs,
                'tags': way.tags
            })

    # Calculate sample size
    if args.percent:
        sample_size = int(len(elements) * args.percent / 100)
    else:
        sample_size = min(args.count, len(elements))

    # Random sample
    sampled = random.sample(elements, sample_size) if sample_size < len(elements) else elements

    elapsed = time.time() - start_time

    if not args.output:
        print(f"Sampled {len(sampled)} from {len(elements)} elements")
        for elem in sampled[:10]:
            name = elem['tags'].get('name', '')
            tags_preview = ', '.join(f"{k}={v}" for k, v in list(elem['tags'].items())[:3])
            print(f"  {elem['type']} {elem['id']}: {tags_preview}")
        if len(sampled) > 10:
            print(f"  ... and {len(sampled) - 10} more")
        return 0

    # Generate output
    if args.format == 'geojson':
        features = []
        for elem in sampled:
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
        output_str = json.dumps([{k: v for k, v in e.items() if k not in ('coords', 'node_refs')} for e in sampled], indent=2)

    elif args.format == 'csv':
        import csv, io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'type', 'lat', 'lon', 'name', 'tags'])
        for e in sampled:
            tags_str = ';'.join(f"{k}={v}" for k, v in e['tags'].items())
            writer.writerow([e['id'], e['type'], e['lat'], e['lon'], e['tags'].get('name', ''), tags_str])
        output_str = buffer.getvalue()

    elif args.format == 'osm':
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append('<osm version="0.6">')
        for e in sampled:
            if e['type'] == 'node':
                lines.append(f'  <node id="{e["id"]}" lat="{e["lat"]}" lon="{e["lon"]}">')
                for k, v in e['tags'].items():
                    lines.append(f'    <tag k="{k}" v="{v}"/>')
                lines.append('  </node>')
            else:
                lines.append(f'  <way id="{e["id"]}">')
                for ref in e.get('node_refs', []):
                    lines.append(f'    <nd ref="{ref}"/>')
                for k, v in e['tags'].items():
                    lines.append(f'    <tag k="{k}" v="{v}"/>')
                lines.append('  </way>')
        lines.append('</osm>')
        output_str = '\n'.join(lines)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nSample complete:")
    print(f"  Total elements: {len(elements)}")
    print(f"  Sampled: {len(sampled)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
