"""Densify command - add points to geometries."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the densify subcommand parser."""
    parser = subparsers.add_parser(
        'densify',
        help='Add points to geometries',
        description='Add intermediate points along line segments'
    )

    parser.add_argument('input', help='Input OSM or GeoJSON file')
    parser.add_argument('-o', '--output', required=True, help='Output file')
    parser.add_argument(
        '--interval', '-i',
        required=True,
        help='Maximum distance between points (e.g., 50m, 100m)'
    )
    parser.add_argument(
        '--filter',
        help='Filter features (e.g., highway=*)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['geojson'],
        default='geojson',
        help='Output format (default: geojson)'
    )

    parser.set_defaults(func=run)
    return parser


def parse_interval(interval_str):
    """Parse interval to meters."""
    interval_str = interval_str.strip().lower()
    if interval_str.endswith('km'):
        return float(interval_str[:-2]) * 1000
    elif interval_str.endswith('m'):
        return float(interval_str[:-1])
    else:
        return float(interval_str)


def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate distance in meters."""
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat/2)**2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def densify_segment(p1, p2, max_interval):
    """Add points between two coordinates at regular intervals."""
    lon1, lat1 = p1
    lon2, lat2 = p2

    distance = haversine_distance(lon1, lat1, lon2, lat2)

    if distance <= max_interval:
        return [p1]

    # Calculate number of segments
    num_segments = int(math.ceil(distance / max_interval))

    points = [p1]
    for i in range(1, num_segments):
        t = i / num_segments
        lon = lon1 + t * (lon2 - lon1)
        lat = lat1 + t * (lat2 - lat1)
        points.append([lon, lat])

    return points


def densify_line(coords, max_interval):
    """Densify a line by adding intermediate points."""
    if len(coords) < 2:
        return coords

    result = []
    for i in range(len(coords) - 1):
        segment_points = densify_segment(coords[i], coords[i + 1], max_interval)
        result.extend(segment_points)

    result.append(coords[-1])
    return result


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
    """Execute the densify command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    try:
        interval = parse_interval(args.interval)
    except ValueError:
        print(f"Error: Invalid interval format: {args.interval}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse filter
    filter_key, filter_value = None, None
    if args.filter:
        filter_key, filter_value = parse_filter(args.filter)

    # Parse input
    if input_path.suffix.lower() in ('.osm', '.xml'):
        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(input_path))

        node_coords = {}
        for node in nodes:
            node_coords[node.id] = [float(node.lon), float(node.lat)]

        features = []
        total_points_before = 0
        total_points_after = 0

        for way in ways:
            if filter_key and not matches_filter(way.tags, filter_key, filter_value):
                continue

            coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
            if len(coords) < 2:
                continue

            total_points_before += len(coords)
            densified = densify_line(coords, interval)
            total_points_after += len(densified)

            is_closed = len(coords) > 2 and coords[0] == coords[-1]

            features.append({
                'coordinates': densified,
                'is_closed': is_closed,
                'tags': way.tags
            })

    elif input_path.suffix.lower() in ('.geojson', '.json'):
        with open(input_path) as f:
            data = json.load(f)

        features = []
        total_points_before = 0
        total_points_after = 0

        input_features = data.get('features', [data] if data.get('type') == 'Feature' else [])

        for feature in input_features:
            geom = feature.get('geometry', {})
            props = feature.get('properties', {})

            if geom.get('type') == 'LineString':
                coords = geom['coordinates']
                total_points_before += len(coords)
                densified = densify_line(coords, interval)
                total_points_after += len(densified)

                features.append({
                    'coordinates': densified,
                    'is_closed': False,
                    'tags': props
                })

            elif geom.get('type') == 'Polygon':
                rings = []
                for ring in geom['coordinates']:
                    total_points_before += len(ring)
                    densified = densify_line(ring, interval)
                    total_points_after += len(densified)
                    rings.append(densified)

                features.append({
                    'coordinates': rings,
                    'is_closed': True,
                    'is_polygon': True,
                    'tags': props
                })

    else:
        print(f"Error: Unsupported file format", file=sys.stderr)
        return 1

    elapsed = time.time() - start_time

    # Generate output
    geojson_features = []
    for f in features:
        if f.get('is_polygon'):
            geom = {"type": "Polygon", "coordinates": f['coordinates']}
        elif f['is_closed']:
            coords = f['coordinates']
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            geom = {"type": "Polygon", "coordinates": [coords]}
        else:
            geom = {"type": "LineString", "coordinates": f['coordinates']}

        geojson_features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": f.get('tags', {})
        })

    output = {"type": "FeatureCollection", "features": geojson_features}
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)

    increase = 100 * (total_points_after / max(total_points_before, 1) - 1)

    print(f"\nDensify complete:")
    print(f"  Features: {len(features)}")
    print(f"  Points: {total_points_before} -> {total_points_after} (+{increase:.1f}%)")
    print(f"  Interval: {args.interval}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
