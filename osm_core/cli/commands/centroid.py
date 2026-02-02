"""Centroid command - calculate centroids."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the centroid subcommand parser."""
    parser = subparsers.add_parser(
        'centroid',
        help='Calculate centroids of ways',
        description='Extract centroid points from ways/polygons'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--filter',
        help='Filter ways (e.g., building=*)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv'],
        default='geojson',
        help='Output format (default: geojson)'
    )
    parser.add_argument(
        '--include-nodes',
        action='store_true',
        help='Include nodes as-is (they are already points)'
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
    """Execute the centroid command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse filter
    filter_key, filter_value = None, None
    if args.filter:
        filter_key, filter_value = parse_filter(args.filter)

    # Parse OSM file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    node_coords = {}
    for node in nodes:
        node_coords[node.id] = [float(node.lon), float(node.lat)]

    centroids = []

    # Include nodes if requested
    if args.include_nodes:
        for node in nodes:
            if filter_key and not matches_filter(node.tags, filter_key, filter_value):
                continue
            if not node.tags:
                continue

            centroids.append({
                'id': node.id,
                'type': 'node',
                'name': node.tags.get('name'),
                'lat': float(node.lat),
                'lon': float(node.lon),
                'tags': node.tags
            })

    # Calculate way centroids
    for way in ways:
        if filter_key and not matches_filter(way.tags, filter_key, filter_value):
            continue
        if not way.tags:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        centroids.append({
            'id': way.id,
            'type': 'way',
            'name': way.tags.get('name'),
            'lat': centroid_lat,
            'lon': centroid_lon,
            'node_count': len(coords),
            'tags': way.tags
        })

    elapsed = time.time() - start_time

    # Generate output
    if args.format == 'geojson':
        features = []
        for c in centroids:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [c['lon'], c['lat']]},
                "properties": {
                    "id": c['id'],
                    "element_type": c['type'],
                    "name": c['name'],
                    **{k: v for k, v in c['tags'].items() if k != 'name'}
                }
            })
        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_str = json.dumps([{k: v for k, v in c.items() if k != 'tags'}
                                  for c in centroids], indent=2)

    elif args.format == 'csv':
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'type', 'name', 'lat', 'lon'])
        for c in centroids:
            writer.writerow([c['id'], c['type'], c['name'],
                           round(c['lat'], 7), round(c['lon'], 7)])
        output_str = buffer.getvalue()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(centroids)} centroids to: {args.output}")
    else:
        print(output_str)

    print(f"\nCentroids calculated: {len(centroids)}", file=sys.stderr)
    print(f"Time: {elapsed:.3f}s", file=sys.stderr)

    return 0
