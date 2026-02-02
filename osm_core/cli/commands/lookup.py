"""Lookup command - reverse geocoding by coordinates."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the lookup subcommand parser."""
    parser = subparsers.add_parser(
        'lookup',
        help='Find features at or near coordinates',
        description='Reverse geocoding - find what features exist at given coordinates'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument(
        '--lat',
        type=float,
        required=True,
        help='Latitude'
    )
    parser.add_argument(
        '--lon',
        type=float,
        required=True,
        help='Longitude'
    )
    parser.add_argument(
        '--radius', '-r',
        type=str,
        default='50m',
        help='Search radius (default: 50m, e.g., 100m, 1km)'
    )
    parser.add_argument(
        '--limit', '-n',
        type=int,
        default=10,
        help='Maximum results (default: 10)'
    )
    parser.add_argument(
        '--type', '-t',
        choices=['nodes', 'ways', 'all'],
        default='all',
        help='Element type to search'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output file (GeoJSON)'
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


def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate distance between two points in meters."""
    R = 6371000  # Earth radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def point_to_line_distance(px, py, coords):
    """Calculate minimum distance from point to polyline in meters."""
    min_dist = float('inf')

    for i in range(len(coords) - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]

        # Vector from p1 to p2
        dx = x2 - x1
        dy = y2 - y1

        if dx == 0 and dy == 0:
            # Segment is a point
            dist = haversine_distance(px, py, x1, y1)
        else:
            # Project point onto line segment
            t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            dist = haversine_distance(px, py, proj_x, proj_y)

        min_dist = min(min_dist, dist)

    return min_dist


def get_feature_description(tags):
    """Get a human-readable description of a feature."""
    # Priority order for description
    description_tags = [
        ('amenity', lambda v: f"{v.replace('_', ' ')}"),
        ('shop', lambda v: f"{v.replace('_', ' ')} shop"),
        ('highway', lambda v: f"{v.replace('_', ' ')} road"),
        ('building', lambda v: f"building ({v})" if v != 'yes' else 'building'),
        ('tourism', lambda v: f"{v.replace('_', ' ')}"),
        ('leisure', lambda v: f"{v.replace('_', ' ')}"),
        ('natural', lambda v: f"{v.replace('_', ' ')}"),
        ('landuse', lambda v: f"{v.replace('_', ' ')} area"),
        ('place', lambda v: f"{v.replace('_', ' ')}"),
    ]

    for key, formatter in description_tags:
        if key in tags:
            return formatter(tags[key])

    return 'feature'


def run(args):
    """Execute the lookup command."""
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

    # Parse the file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Build node coordinate lookup
    node_coords = {}
    for node in nodes:
        node_coords[node.id] = [float(node.lon), float(node.lat)]

    query_lat = args.lat
    query_lon = args.lon

    results = []

    # Search nodes
    if args.type in ('nodes', 'all'):
        for node in nodes:
            # Skip nodes without meaningful tags
            if not node.tags or (len(node.tags) == 1 and 'source' in node.tags):
                continue

            dist = haversine_distance(query_lon, query_lat, float(node.lon), float(node.lat))

            if dist <= radius:
                results.append({
                    'type': 'node',
                    'id': node.id,
                    'name': node.tags.get('name'),
                    'description': get_feature_description(node.tags),
                    'distance_m': round(dist, 1),
                    'lat': float(node.lat),
                    'lon': float(node.lon),
                    'tags': node.tags
                })

    # Search ways
    if args.type in ('ways', 'all'):
        for way in ways:
            if not way.tags:
                continue

            # Get coordinates
            coords = []
            for ref in way.node_refs:
                if ref in node_coords:
                    coords.append(node_coords[ref])

            if len(coords) < 2:
                continue

            # Calculate distance to way
            dist = point_to_line_distance(query_lon, query_lat, coords)

            if dist <= radius:
                # Get centroid
                centroid_lon = sum(c[0] for c in coords) / len(coords)
                centroid_lat = sum(c[1] for c in coords) / len(coords)

                results.append({
                    'type': 'way',
                    'id': way.id,
                    'name': way.tags.get('name'),
                    'description': get_feature_description(way.tags),
                    'distance_m': round(dist, 1),
                    'lat': centroid_lat,
                    'lon': centroid_lon,
                    'coordinates': coords,
                    'tags': way.tags
                })

    # Sort by distance
    results.sort(key=lambda x: x['distance_m'])

    # Limit results
    if args.limit > 0:
        results = results[:args.limit]

    elapsed = time.time() - start_time

    # JSON output
    if args.json:
        output = {
            'query': {
                'lat': query_lat,
                'lon': query_lon,
                'radius_m': radius
            },
            'results': [
                {
                    'type': r['type'],
                    'id': r['id'],
                    'name': r['name'],
                    'description': r['description'],
                    'distance_m': r['distance_m'],
                    'lat': r['lat'],
                    'lon': r['lon'],
                    'tags': r['tags']
                }
                for r in results
            ],
            'count': len(results)
        }
        print(json.dumps(output, indent=2))
        return 0

    # GeoJSON file output
    if args.output:
        output = {
            "type": "FeatureCollection",
            "features": []
        }

        # Add query point
        output["features"].append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [query_lon, query_lat]
            },
            "properties": {
                "type": "query_point",
                "radius_m": radius
            }
        })

        for r in results:
            if r['type'] == 'node':
                geometry = {
                    "type": "Point",
                    "coordinates": [r['lon'], r['lat']]
                }
            else:
                coords = r.get('coordinates', [])
                if len(coords) > 2 and coords[0] == coords[-1]:
                    geometry = {
                        "type": "Polygon",
                        "coordinates": [coords]
                    }
                else:
                    geometry = {
                        "type": "LineString",
                        "coordinates": coords
                    }

            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "id": r['id'],
                    "element_type": r['type'],
                    "name": r['name'],
                    "description": r['description'],
                    "distance_m": r['distance_m'],
                    **{k: v for k, v in r['tags'].items() if k != 'name'}
                }
            }
            output["features"].append(feature)

        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        print(f"Saved {len(results)} results to: {args.output}")
        return 0

    # Console output
    print(f"\nLookup at {query_lat:.6f}, {query_lon:.6f} (radius: {args.radius})")
    print("=" * 60)

    if not results:
        print("No features found within radius.")
    else:
        # Find nearest
        nearest = results[0]
        print(f"\nNearest: \"{nearest['name'] or '(unnamed)'}\"")
        print(f"         {nearest['description']} ({nearest['type']})")
        print(f"         {nearest['distance_m']}m away")

        if len(results) > 1:
            print(f"\nWithin {args.radius}:")
            for r in results[1:]:
                name = r['name'] or '(unnamed)'
                print(f"  - \"{name}\" ({r['description']}) - {r['distance_m']}m")

    print(f"\n{'=' * 60}")
    print(f"Found {len(results)} features in {elapsed:.3f}s")

    return 0
