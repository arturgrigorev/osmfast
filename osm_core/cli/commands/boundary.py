"""Boundary command - extract administrative boundaries."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


ADMIN_LEVELS = {
    '2': 'country',
    '3': 'region',
    '4': 'state',
    '5': 'region',
    '6': 'county',
    '7': 'municipality',
    '8': 'city',
    '9': 'district',
    '10': 'suburb',
    '11': 'neighbourhood'
}


def setup_parser(subparsers):
    """Setup the boundary subcommand parser."""
    parser = subparsers.add_parser(
        'boundary',
        help='Extract administrative boundaries',
        description='Extract administrative boundaries from OSM'
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
        '--level',
        type=int,
        help='Filter by admin level (2-11)'
    )
    parser.add_argument(
        '--name',
        help='Filter by name (partial match)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List boundaries only (no geometry)'
    )

    parser.set_defaults(func=run)
    return parser


def run(args):
    """Execute the boundary command."""
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

    boundaries = []

    # Extract boundary ways
    for way in ways:
        tags = way.tags
        if tags.get('boundary') != 'administrative':
            if 'admin_level' not in tags:
                continue

        admin_level = tags.get('admin_level')

        # Apply filters
        if args.level and admin_level != str(args.level):
            continue

        name = tags.get('name', '')
        if args.name and args.name.lower() not in name.lower():
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if len(coords) < 3:
            continue

        boundaries.append({
            'id': way.id,
            'name': name,
            'admin_level': admin_level,
            'level_name': ADMIN_LEVELS.get(admin_level, 'unknown'),
            'ref': tags.get('ref'),
            'wikidata': tags.get('wikidata'),
            'coordinates': coords
        })

    elapsed = time.time() - start_time

    # List mode
    if args.list:
        print(f"\nAdministrative Boundaries: {args.input}")
        print("=" * 70)
        print(f"{'Level':<6} {'Type':<15} {'Name':<40}")
        print("-" * 70)

        for b in sorted(boundaries, key=lambda x: (x['admin_level'] or '99', x['name'])):
            level = b['admin_level'] or '?'
            level_name = b['level_name'][:15]
            name = (b['name'] or '(unnamed)')[:40]
            print(f"{level:<6} {level_name:<15} {name:<40}")

        print(f"\nTotal: {len(boundaries)} boundaries")
        print(f"Time: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'geojson':
        features = []
        for b in boundaries:
            coords = b['coordinates']
            if coords[0] != coords[-1]:
                coords.append(coords[0])

            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {
                    "id": b['id'],
                    "name": b['name'],
                    "admin_level": b['admin_level'],
                    "level_name": b['level_name']
                }
            })
        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_str = json.dumps([{k: v for k, v in b.items() if k != 'coordinates'}
                                  for b in boundaries], indent=2)

    elif args.format == 'csv':
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'name', 'admin_level', 'level_name', 'ref'])
        for b in boundaries:
            writer.writerow([b['id'], b['name'], b['admin_level'], b['level_name'], b['ref']])
        output_str = buffer.getvalue()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(boundaries)} boundaries to: {args.output}")
    else:
        print(output_str)

    return 0
