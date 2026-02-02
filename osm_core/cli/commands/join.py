"""Join command - join external data to OSM features."""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the join subcommand parser."""
    parser = subparsers.add_parser(
        'join',
        help='Join external data to OSM features',
        description='Join CSV/JSON data to OSM features by ID or tag'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('data', help='External data file (CSV or JSON)')
    parser.add_argument('-o', '--output', required=True, help='Output file')
    parser.add_argument(
        '--osm-key',
        default='id',
        help='OSM key to join on: "id" or tag name (default: id)'
    )
    parser.add_argument(
        '--data-key',
        help='Column/field in data file to join on (default: first column)'
    )
    parser.add_argument(
        '--columns',
        help='Comma-separated list of columns to include (default: all)'
    )
    parser.add_argument(
        '--prefix',
        default='',
        help='Prefix for joined columns (e.g., "ext_")'
    )
    parser.add_argument(
        '--how',
        choices=['inner', 'left'],
        default='left',
        help='Join type: inner (only matches) or left (all OSM features) (default: left)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv'],
        default='geojson',
        help='Output format (default: geojson)'
    )

    parser.set_defaults(func=run)
    return parser


def load_external_data(data_path, data_key, columns):
    """Load external data from CSV or JSON file."""
    data_path = Path(data_path)

    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    ext = data_path.suffix.lower()

    if ext == '.csv':
        data = {}
        with open(data_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

            if not data_key:
                data_key = fieldnames[0]
            if data_key not in fieldnames:
                raise ValueError(f"Key '{data_key}' not found in CSV. Available: {fieldnames}")

            if columns:
                selected_cols = [c.strip() for c in columns.split(',')]
            else:
                selected_cols = [c for c in fieldnames if c != data_key]

            for row in reader:
                key = row[data_key]
                data[key] = {col: row.get(col) for col in selected_cols if col in row}

        return data, data_key, selected_cols

    elif ext in ('.json', '.geojson'):
        with open(data_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        # Handle GeoJSON
        if isinstance(raw, dict) and raw.get('type') == 'FeatureCollection':
            items = [f.get('properties', {}) for f in raw.get('features', [])]
        elif isinstance(raw, list):
            items = raw
        else:
            items = [raw]

        if not items:
            return {}, data_key, []

        # Detect key
        all_keys = list(items[0].keys()) if items else []
        if not data_key:
            data_key = all_keys[0] if all_keys else 'id'

        if columns:
            selected_cols = [c.strip() for c in columns.split(',')]
        else:
            selected_cols = [c for c in all_keys if c != data_key]

        data = {}
        for item in items:
            key = str(item.get(data_key, ''))
            if key:
                data[key] = {col: item.get(col) for col in selected_cols}

        return data, data_key, selected_cols

    else:
        raise ValueError(f"Unsupported data format: {ext}")


def run(args):
    """Execute the join command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Load external data
    try:
        ext_data, data_key, ext_columns = load_external_data(
            args.data, args.data_key, args.columns
        )
    except Exception as e:
        print(f"Error loading data file: {e}", file=sys.stderr)
        return 1

    print(f"Loaded {len(ext_data)} records from {args.data}", file=sys.stderr)
    print(f"Join key: OSM '{args.osm_key}' = Data '{data_key}'", file=sys.stderr)

    # Parse OSM
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    node_coords = {}
    for node in nodes:
        node_coords[node.id] = (float(node.lon), float(node.lat))

    # Collect and join
    results = []
    matched = 0

    def get_join_key(elem):
        if args.osm_key == 'id':
            return str(elem['id'])
        return elem['tags'].get(args.osm_key, '')

    def process_element(elem_dict):
        nonlocal matched
        join_key = get_join_key(elem_dict)
        ext_record = ext_data.get(join_key, {})

        if ext_record:
            matched += 1
        elif args.how == 'inner':
            return

        # Add external data with prefix
        for col in ext_columns:
            col_name = f"{args.prefix}{col}"
            elem_dict['tags'][col_name] = ext_record.get(col)

        results.append(elem_dict)

    for node in nodes:
        process_element({
            'id': node.id,
            'type': 'node',
            'lon': float(node.lon),
            'lat': float(node.lat),
            'tags': dict(node.tags)
        })

    for way in ways:
        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue
        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        process_element({
            'id': way.id,
            'type': 'way',
            'lon': centroid_lon,
            'lat': centroid_lat,
            'coords': coords,
            'tags': dict(way.tags)
        })

    elapsed = time.time() - start_time

    # Generate output
    if args.format == 'geojson':
        features = []
        for elem in results:
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
        output_str = json.dumps([{k: v for k, v in e.items() if k != 'coords'} for e in results], indent=2)

    elif args.format == 'csv':
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        # Headers
        headers = ['id', 'type', 'lat', 'lon', 'name']
        headers.extend([f"{args.prefix}{c}" for c in ext_columns])
        writer.writerow(headers)

        for e in results:
            row = [e['id'], e['type'], e['lat'], e['lon'], e['tags'].get('name', '')]
            for c in ext_columns:
                row.append(e['tags'].get(f"{args.prefix}{c}", ''))
            writer.writerow(row)
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nJoin complete:")
    print(f"  OSM elements: {len(results)}")
    print(f"  Matched: {matched}")
    print(f"  Join type: {args.how}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
