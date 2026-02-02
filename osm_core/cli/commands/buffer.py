"""Buffer command - create buffer zones around features."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the buffer subcommand parser."""
    parser = subparsers.add_parser(
        'buffer',
        help='Create buffer zones around features',
        description='Generate buffer polygons around points or lines'
    )

    parser.add_argument('input', help='Input OSM or GeoJSON file')
    parser.add_argument('-o', '--output', required=True, help='Output GeoJSON file')
    parser.add_argument(
        '--radius', '-r',
        required=True,
        help='Buffer radius (e.g., 100m, 1km)'
    )
    parser.add_argument(
        '--filter',
        help='Filter elements (e.g., amenity=hospital)'
    )
    parser.add_argument(
        '--segments',
        type=int,
        default=16,
        help='Number of segments for circle approximation (default: 16)'
    )
    parser.add_argument(
        '--dissolve',
        action='store_true',
        help='Dissolve overlapping buffers'
    )

    parser.set_defaults(func=run)
    return parser


def parse_radius(radius_str):
    """Parse radius string to meters."""
    radius_str = radius_str.strip().lower()
    if radius_str.endswith('km'):
        return float(radius_str[:-2]) * 1000
    elif radius_str.endswith('m'):
        return float(radius_str[:-1])
    else:
        return float(radius_str)


def create_circle_polygon(center_lon, center_lat, radius_m, segments=16):
    """Create a circular polygon approximation."""
    coords = []

    # Convert radius to degrees (approximate)
    lat_rad = math.radians(center_lat)
    radius_deg_lat = radius_m / 111320  # meters per degree latitude
    radius_deg_lon = radius_m / (111320 * math.cos(lat_rad))

    for i in range(segments):
        angle = 2 * math.pi * i / segments
        lon = center_lon + radius_deg_lon * math.cos(angle)
        lat = center_lat + radius_deg_lat * math.sin(angle)
        coords.append([lon, lat])

    # Close the polygon
    coords.append(coords[0])

    return coords


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
    """Execute the buffer command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    try:
        radius = parse_radius(args.radius)
    except ValueError:
        print(f"Error: Invalid radius format: {args.radius}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse filter
    filter_key, filter_value = None, None
    if args.filter:
        filter_key, filter_value = parse_filter(args.filter)

    # Parse input file
    if input_path.suffix.lower() in ('.osm', '.xml'):
        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(input_path))

        node_coords = {}
        for node in nodes:
            node_coords[node.id] = [float(node.lon), float(node.lat)]

        points = []

        for node in nodes:
            if filter_key and not matches_filter(node.tags, filter_key, filter_value):
                continue
            points.append({
                'lon': float(node.lon),
                'lat': float(node.lat),
                'properties': {'id': node.id, **node.tags}
            })

        for way in ways:
            if filter_key and not matches_filter(way.tags, filter_key, filter_value):
                continue
            coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
            if coords:
                centroid_lon = sum(c[0] for c in coords) / len(coords)
                centroid_lat = sum(c[1] for c in coords) / len(coords)
                points.append({
                    'lon': centroid_lon,
                    'lat': centroid_lat,
                    'properties': {'id': way.id, **way.tags}
                })

    elif input_path.suffix.lower() in ('.geojson', '.json'):
        with open(input_path) as f:
            data = json.load(f)

        points = []
        features = data.get('features', [data] if data.get('type') == 'Feature' else [])

        for feature in features:
            geom = feature.get('geometry', {})
            props = feature.get('properties', {})

            if geom.get('type') == 'Point':
                lon, lat = geom['coordinates']
                points.append({'lon': lon, 'lat': lat, 'properties': props})
            elif geom.get('type') in ('LineString', 'Polygon'):
                coords = geom['coordinates']
                if geom['type'] == 'Polygon':
                    coords = coords[0]
                if coords:
                    centroid_lon = sum(c[0] for c in coords) / len(coords)
                    centroid_lat = sum(c[1] for c in coords) / len(coords)
                    points.append({'lon': centroid_lon, 'lat': centroid_lat, 'properties': props})

    else:
        print(f"Error: Unsupported file format: {input_path.suffix}", file=sys.stderr)
        return 1

    # Create buffer polygons
    features = []
    for point in points:
        circle = create_circle_polygon(
            point['lon'], point['lat'], radius, args.segments
        )
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [circle]},
            "properties": {
                **point['properties'],
                'buffer_radius_m': radius,
                'center_lon': point['lon'],
                'center_lat': point['lat']
            }
        })

    output = {"type": "FeatureCollection", "features": features}

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)

    elapsed = time.time() - start_time

    print(f"\nBuffer complete:")
    print(f"  Input points: {len(points)}")
    print(f"  Buffer radius: {radius}m")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
