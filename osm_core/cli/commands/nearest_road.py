"""Nearest-road command - snap points to nearest road."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


ALLOWED_ROADS = {
    'walk': frozenset({'primary', 'secondary', 'tertiary', 'residential', 'living_street',
                       'unclassified', 'service', 'pedestrian', 'footway', 'path', 'steps', 'track'}),
    'bike': frozenset({'primary', 'secondary', 'tertiary', 'residential', 'living_street',
                       'unclassified', 'service', 'cycleway', 'path', 'track'}),
    'drive': frozenset({'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
                        'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'residential',
                        'living_street', 'unclassified', 'service', 'road'}),
    'all': None
}


def setup_parser(subparsers):
    parser = subparsers.add_parser(
        'nearest-road',
        help='Find nearest point on road network',
        description='Snap a point to the nearest road segment'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('--lat', type=float, required=True, help='Latitude')
    parser.add_argument('--lon', type=float, required=True, help='Longitude')
    parser.add_argument('--mode', '-m', choices=['walk', 'bike', 'drive', 'all'], default='all')
    parser.add_argument('--format', '-f', choices=['geojson', 'json', 'text'], default='text')

    parser.set_defaults(func=run)
    return parser


def haversine_distance(lon1, lat1, lon2, lat2):
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def point_to_segment_distance(px, py, x1, y1, x2, y2):
    """Find nearest point on segment and distance to it."""
    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:
        return x1, y1, haversine_distance(px, py, x1, y1)

    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))

    nearest_x = x1 + t * dx
    nearest_y = y1 + t * dy

    dist = haversine_distance(px, py, nearest_x, nearest_y)

    return nearest_x, nearest_y, dist


def run(args):
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

    allowed = ALLOWED_ROADS.get(args.mode)

    best_dist = float('inf')
    best_point = None
    best_segment = None
    best_way = None

    for way in ways:
        highway = way.tags.get('highway')
        if not highway:
            continue
        if allowed and highway not in allowed:
            continue

        refs = way.node_refs
        for i in range(len(refs) - 1):
            if refs[i] not in node_coords or refs[i + 1] not in node_coords:
                continue

            x1, y1 = node_coords[refs[i]]
            x2, y2 = node_coords[refs[i + 1]]

            nearest_lon, nearest_lat, dist = point_to_segment_distance(
                args.lon, args.lat, x1, y1, x2, y2
            )

            if dist < best_dist:
                best_dist = dist
                best_point = (nearest_lon, nearest_lat)
                best_segment = [(x1, y1), (x2, y2)]
                best_way = {
                    'id': way.id,
                    'highway': highway,
                    'name': way.tags.get('name', ''),
                    'tags': way.tags
                }

    elapsed = time.time() - start_time

    if best_point is None:
        print("Error: No roads found", file=sys.stderr)
        return 1

    if args.format == 'text':
        print(f"\nNearest Road Point")
        print("=" * 50)
        print(f"Search point: {args.lat:.6f}, {args.lon:.6f}")
        print(f"Nearest point: {best_point[1]:.6f}, {best_point[0]:.6f}")
        print(f"Distance: {best_dist:.1f}m")
        print(f"\nRoad: {best_way['name'] or '(unnamed)'}")
        print(f"Type: {best_way['highway']}")
        print(f"Way ID: {best_way['id']}")
        print(f"\n[{elapsed:.3f}s]")

        if not args.output:
            return 0

    # Generate output
    if args.format == 'geojson' or args.output:
        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [args.lon, args.lat]},
                "properties": {"type": "input_point"}
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": list(best_point)},
                "properties": {
                    "type": "snapped_point",
                    "distance_m": round(best_dist, 1),
                    "road_name": best_way['name'],
                    "highway": best_way['highway'],
                    "way_id": best_way['id']
                }
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[args.lon, args.lat], list(best_point)]
                },
                "properties": {"type": "connection", "distance_m": round(best_dist, 1)}
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [list(best_segment[0]), list(best_segment[1])]
                },
                "properties": {
                    "type": "road_segment",
                    "name": best_way['name'],
                    "highway": best_way['highway']
                }
            }
        ]
        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output = {
            'input': {'lat': args.lat, 'lon': args.lon},
            'snapped': {'lat': best_point[1], 'lon': best_point[0]},
            'distance_m': round(best_dist, 1),
            'road': {
                'way_id': best_way['id'],
                'name': best_way['name'],
                'highway': best_way['highway']
            }
        }
        output_str = json.dumps(output, indent=2)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Result saved to {args.output}")
    elif args.format != 'text':
        print(output_str)

    return 0
