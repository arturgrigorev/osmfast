"""Within command - find features within polygon."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the within subcommand parser."""
    parser = subparsers.add_parser(
        'within',
        help='Find features within polygon',
        description='Extract features that are inside a polygon boundary'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--polygon',
        required=True,
        help='Boundary polygon (GeoJSON file)'
    )
    parser.add_argument(
        '--filter',
        help='Additional filter (e.g., amenity=*)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv'],
        default='geojson',
        help='Output format (default: geojson)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only'
    )

    parser.set_defaults(func=run)
    return parser


def point_in_polygon(x, y, polygon):
    """Check if point is inside polygon using ray casting."""
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def load_polygon(filepath):
    """Load polygon from GeoJSON file."""
    with open(filepath) as f:
        data = json.load(f)

    if data['type'] == 'FeatureCollection':
        for feature in data['features']:
            if feature['geometry']['type'] == 'Polygon':
                return feature['geometry']['coordinates'][0]
    elif data['type'] == 'Feature':
        if data['geometry']['type'] == 'Polygon':
            return data['geometry']['coordinates'][0]
    elif data['type'] == 'Polygon':
        return data['coordinates'][0]

    raise ValueError("No polygon found in GeoJSON")


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
    """Execute the within command."""
    input_path = Path(args.input)
    polygon_path = Path(args.polygon)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    if not polygon_path.exists():
        print(f"Error: Polygon file not found: {args.polygon}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Load polygon
    try:
        polygon = load_polygon(polygon_path)
    except Exception as e:
        print(f"Error loading polygon: {e}", file=sys.stderr)
        return 1

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

    features = []

    # Check nodes
    for node in nodes:
        if filter_key and not matches_filter(node.tags, filter_key, filter_value):
            continue

        lon, lat = float(node.lon), float(node.lat)
        if point_in_polygon(lon, lat, polygon):
            features.append({
                'id': node.id,
                'type': 'node',
                'name': node.tags.get('name'),
                'lat': lat,
                'lon': lon,
                'tags': node.tags
            })

    # Check ways (by centroid)
    for way in ways:
        if filter_key and not matches_filter(way.tags, filter_key, filter_value):
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        if point_in_polygon(centroid_lon, centroid_lat, polygon):
            features.append({
                'id': way.id,
                'type': 'way',
                'name': way.tags.get('name'),
                'lat': centroid_lat,
                'lon': centroid_lon,
                'coordinates': coords,
                'tags': way.tags
            })

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nWithin Analysis: {args.input}")
        print("=" * 60)
        print(f"Polygon: {args.polygon}")
        if args.filter:
            print(f"Filter: {args.filter}")
        print(f"\nFeatures within polygon: {len(features)}")

        nodes_count = sum(1 for f in features if f['type'] == 'node')
        ways_count = sum(1 for f in features if f['type'] == 'way')
        print(f"  Nodes: {nodes_count}")
        print(f"  Ways: {ways_count}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'geojson':
        geojson_features = []
        for f in features:
            if f['type'] == 'node':
                geom = {"type": "Point", "coordinates": [f['lon'], f['lat']]}
            else:
                coords = f.get('coordinates', [])
                is_closed = len(coords) > 2 and coords[0] == coords[-1]
                if is_closed:
                    geom = {"type": "Polygon", "coordinates": [coords]}
                else:
                    geom = {"type": "LineString", "coordinates": coords}

            geojson_features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "id": f['id'],
                    "element_type": f['type'],
                    "name": f['name'],
                    **f['tags']
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
        writer.writerow(['id', 'type', 'name', 'lat', 'lon'])
        for f in features:
            writer.writerow([f['id'], f['type'], f['name'], f['lat'], f['lon']])
        output_str = buffer.getvalue()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(features)} features to: {args.output}")
    else:
        print(output_str)

    return 0
