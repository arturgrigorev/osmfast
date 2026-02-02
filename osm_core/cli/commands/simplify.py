"""Simplify command - reduce geometry complexity."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the simplify subcommand parser."""
    parser = subparsers.add_parser(
        'simplify',
        help='Reduce geometry complexity',
        description='Simplify geometries using Douglas-Peucker algorithm'
    )

    parser.add_argument('input', help='Input OSM or GeoJSON file')
    parser.add_argument('-o', '--output', required=True, help='Output file')
    parser.add_argument(
        '--tolerance', '-t',
        required=True,
        help='Simplification tolerance (e.g., 10m, 0.001 degrees)'
    )
    parser.add_argument(
        '--filter',
        help='Filter features (e.g., highway=*)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'osm'],
        default='geojson',
        help='Output format (default: geojson)'
    )

    parser.set_defaults(func=run)
    return parser


def parse_tolerance(tolerance_str):
    """Parse tolerance to degrees."""
    tolerance_str = tolerance_str.strip().lower()
    if tolerance_str.endswith('m'):
        # Convert meters to approximate degrees
        meters = float(tolerance_str[:-1])
        return meters / 111320  # Approximate conversion
    elif tolerance_str.endswith('km'):
        km = float(tolerance_str[:-2])
        return km / 111.32
    else:
        return float(tolerance_str)


def perpendicular_distance(point, line_start, line_end):
    """Calculate perpendicular distance from point to line."""
    x, y = point
    x1, y1 = line_start
    x2, y2 = line_end

    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:
        return math.sqrt((x - x1)**2 + (y - y1)**2)

    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx**2 + dy**2)))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy

    return math.sqrt((x - proj_x)**2 + (y - proj_y)**2)


def douglas_peucker(coords, tolerance):
    """Simplify coordinates using Douglas-Peucker algorithm."""
    if len(coords) <= 2:
        return coords

    # Find point with maximum distance
    max_dist = 0
    max_idx = 0

    for i in range(1, len(coords) - 1):
        dist = perpendicular_distance(coords[i], coords[0], coords[-1])
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    # If max distance is greater than tolerance, recursively simplify
    if max_dist > tolerance:
        left = douglas_peucker(coords[:max_idx + 1], tolerance)
        right = douglas_peucker(coords[max_idx:], tolerance)
        return left[:-1] + right
    else:
        return [coords[0], coords[-1]]


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
    """Execute the simplify command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    try:
        tolerance = parse_tolerance(args.tolerance)
    except ValueError:
        print(f"Error: Invalid tolerance format: {args.tolerance}", file=sys.stderr)
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
            simplified = douglas_peucker(coords, tolerance)
            total_points_after += len(simplified)

            is_closed = len(coords) > 2 and coords[0] == coords[-1]

            features.append({
                'id': way.id,
                'type': 'way',
                'coordinates': simplified,
                'is_closed': is_closed,
                'original_points': len(coords),
                'simplified_points': len(simplified),
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
                simplified = douglas_peucker(coords, tolerance)
                total_points_after += len(simplified)

                features.append({
                    'coordinates': simplified,
                    'is_closed': False,
                    'tags': props
                })

            elif geom.get('type') == 'Polygon':
                for ring in geom['coordinates']:
                    total_points_before += len(ring)
                    simplified = douglas_peucker(ring, tolerance)
                    total_points_after += len(simplified)

                    features.append({
                        'coordinates': simplified,
                        'is_closed': True,
                        'tags': props
                    })

    else:
        print(f"Error: Unsupported file format", file=sys.stderr)
        return 1

    elapsed = time.time() - start_time

    # Generate output
    if args.format == 'geojson':
        geojson_features = []
        for f in features:
            coords = f['coordinates']
            if f['is_closed']:
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                geom = {"type": "Polygon", "coordinates": [coords]}
            else:
                geom = {"type": "LineString", "coordinates": coords}

            geojson_features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": f.get('tags', {})
            })

        output = {"type": "FeatureCollection", "features": geojson_features}
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

    reduction = 100 * (1 - total_points_after / max(total_points_before, 1))

    print(f"\nSimplify complete:")
    print(f"  Features: {len(features)}")
    print(f"  Points: {total_points_before} -> {total_points_after} ({reduction:.1f}% reduction)")
    print(f"  Tolerance: {args.tolerance}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
