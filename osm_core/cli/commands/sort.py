"""Sort command - sort features by attribute."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the sort subcommand parser."""
    parser = subparsers.add_parser(
        'sort',
        help='Sort features by attribute',
        description='Sort OSM features by a tag value or property'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', required=True, help='Output file')
    parser.add_argument(
        '--by', '-b',
        required=True,
        help='Sort by: tag name, "id", "lat", "lon", "type"'
    )
    parser.add_argument(
        '--reverse', '-r',
        action='store_true',
        help='Sort in descending order'
    )
    parser.add_argument(
        '--numeric',
        action='store_true',
        help='Sort numerically (for numeric tag values)'
    )
    parser.add_argument(
        '--filter',
        help='Filter by tag before sorting (e.g., highway=*)'
    )
    parser.add_argument(
        '--limit', '-n',
        type=int,
        help='Limit output to N elements'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv'],
        default='geojson',
        help='Output format (default: geojson)'
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


def get_sort_key(elem, sort_by, numeric):
    """Get sort key for element."""
    if sort_by == 'id':
        return elem['id']
    elif sort_by == 'lat':
        return elem['lat']
    elif sort_by == 'lon':
        return elem['lon']
    elif sort_by == 'type':
        return elem['type']
    else:
        # Sort by tag value
        value = elem['tags'].get(sort_by, '')
        if numeric:
            try:
                # Handle values like "50 km/h" or "100m"
                num_str = ''.join(c for c in str(value) if c.isdigit() or c == '.' or c == '-')
                return float(num_str) if num_str else float('-inf')
            except ValueError:
                return float('-inf')
        return str(value).lower()


def run(args):
    """Execute the sort command."""
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

    # Sort
    try:
        sorted_elements = sorted(
            elements,
            key=lambda e: get_sort_key(e, args.by, args.numeric),
            reverse=args.reverse
        )
    except Exception as e:
        print(f"Error sorting: {e}", file=sys.stderr)
        return 1

    # Apply limit
    if args.limit:
        sorted_elements = sorted_elements[:args.limit]

    elapsed = time.time() - start_time

    # Generate output
    if args.format == 'geojson':
        features = []
        for elem in sorted_elements:
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
        output_str = json.dumps([{k: v for k, v in e.items() if k != 'coords'} for e in sorted_elements], indent=2)

    elif args.format == 'csv':
        import csv, io
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        # Include sort column prominently
        sort_col = args.by if args.by not in ('id', 'type', 'lat', 'lon') else None
        headers = ['id', 'type', 'lat', 'lon']
        if sort_col:
            headers.append(sort_col)
        headers.append('name')
        writer.writerow(headers)

        for e in sorted_elements:
            row = [e['id'], e['type'], e['lat'], e['lon']]
            if sort_col:
                row.append(e['tags'].get(sort_col, ''))
            row.append(e['tags'].get('name', ''))
            writer.writerow(row)
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nSort complete:")
    print(f"  Elements: {len(sorted_elements)} of {len(elements)}")
    print(f"  Sorted by: {args.by} ({'desc' if args.reverse else 'asc'})")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
