"""Nearest command - find K nearest features of type X."""
import argparse
import heapq
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    parser = subparsers.add_parser(
        'nearest',
        help='Find K nearest features',
        description='Find the K nearest features of a specific type to a point'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--lat',
        type=float,
        required=True,
        help='Latitude of search point'
    )
    parser.add_argument(
        '--lon',
        type=float,
        required=True,
        help='Longitude of search point'
    )
    parser.add_argument(
        '--filter', '-f',
        required=True,
        help='Filter (e.g., amenity=restaurant, shop=*)'
    )
    parser.add_argument(
        '-k', '--count',
        type=int,
        default=5,
        help='Number of nearest features (default: 5)'
    )
    parser.add_argument(
        '--max-distance',
        type=float,
        help='Maximum distance in meters'
    )
    parser.add_argument(
        '--format',
        choices=['geojson', 'json', 'text'],
        default='text',
        help='Output format (default: text)'
    )

    parser.set_defaults(func=run)
    return parser


def haversine_distance(lon1, lat1, lon2, lat2):
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def parse_filter(filter_str):
    if '=' not in filter_str:
        return filter_str, '*'
    key, value = filter_str.split('=', 1)
    return key.strip(), value.strip()


def matches_filter(tags, key, value):
    if key not in tags:
        return False
    if value == '*':
        return True
    return tags[key] == value


def run(args):
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    filter_key, filter_value = parse_filter(args.filter)

    start_time = time.time()

    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    node_coords = {}
    for node in nodes:
        node_coords[node.id] = (float(node.lon), float(node.lat))

    # Collect matching features with distances
    candidates = []  # (distance, feature)

    # Process nodes
    for node in nodes:
        if not matches_filter(node.tags, filter_key, filter_value):
            continue

        dist = haversine_distance(args.lon, args.lat, float(node.lon), float(node.lat))

        if args.max_distance and dist > args.max_distance:
            continue

        candidates.append((dist, {
            'id': node.id,
            'type': 'node',
            'name': node.tags.get('name'),
            filter_key: node.tags.get(filter_key),
            'lon': float(node.lon),
            'lat': float(node.lat),
            'tags': node.tags
        }))

    # Process ways
    for way in ways:
        if not matches_filter(way.tags, filter_key, filter_value):
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)
        dist = haversine_distance(args.lon, args.lat, centroid_lon, centroid_lat)

        if args.max_distance and dist > args.max_distance:
            continue

        candidates.append((dist, {
            'id': way.id,
            'type': 'way',
            'name': way.tags.get('name'),
            filter_key: way.tags.get(filter_key),
            'lon': centroid_lon,
            'lat': centroid_lat,
            'tags': way.tags
        }))

    # Sort and take top K
    candidates.sort(key=lambda x: x[0])
    results = [(dist, feat) for dist, feat in candidates[:args.count]]

    elapsed = time.time() - start_time

    if args.format == 'text':
        print(f"\nNearest {args.filter} to ({args.lat}, {args.lon})")
        print("=" * 60)

        if not results:
            print("No matching features found")
        else:
            for i, (dist, feat) in enumerate(results, 1):
                name = feat.get('name') or '(unnamed)'
                dist_str = f"{dist:.0f}m" if dist < 1000 else f"{dist/1000:.2f}km"
                print(f"\n{i}. {name}")
                print(f"   {filter_key}: {feat.get(filter_key)}")
                print(f"   Distance: {dist_str}")
                print(f"   Location: {feat['lat']:.6f}, {feat['lon']:.6f}")

        print(f"\n[{elapsed:.3f}s]")

        if not args.output:
            return 0

    # Generate output
    if args.format == 'geojson' or args.output:
        features = []

        # Add search point
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [args.lon, args.lat]},
            "properties": {"type": "search_point"}
        })

        # Add results
        for i, (dist, feat) in enumerate(results, 1):
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [feat['lon'], feat['lat']]},
                "properties": {
                    "rank": i,
                    "distance_m": round(dist, 1),
                    "name": feat.get('name'),
                    filter_key: feat.get(filter_key),
                    "osm_id": feat['id'],
                    "osm_type": feat['type']
                }
            })

        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output = {
            'search_point': {'lat': args.lat, 'lon': args.lon},
            'filter': args.filter,
            'results': [
                {
                    'rank': i,
                    'distance_m': round(dist, 1),
                    'name': feat.get('name'),
                    filter_key: feat.get(filter_key),
                    'lat': feat['lat'],
                    'lon': feat['lon'],
                    'osm_id': feat['id'],
                    'osm_type': feat['type']
                }
                for i, (dist, feat) in enumerate(results, 1)
            ]
        }
        output_str = json.dumps(output, indent=2)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Results saved to {args.output}")
    elif args.format != 'text':
        print(output_str)

    return 0
