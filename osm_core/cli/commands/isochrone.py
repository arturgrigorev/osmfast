"""Isochrone command - generate travel time polygons."""
import argparse
import heapq
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


# Default speeds in km/h
DEFAULT_SPEEDS = {
    'walk': {
        'default': 5,
        'steps': 3,
        'path': 4,
        'footway': 5,
        'pedestrian': 5,
        'residential': 5,
        'living_street': 5
    },
    'bike': {
        'default': 15,
        'cycleway': 18,
        'path': 12,
        'residential': 15,
        'tertiary': 18,
        'secondary': 20,
        'primary': 15
    },
    'drive': {
        'motorway': 110, 'motorway_link': 60,
        'trunk': 90, 'trunk_link': 50,
        'primary': 60, 'primary_link': 40,
        'secondary': 50, 'secondary_link': 35,
        'tertiary': 40, 'tertiary_link': 30,
        'residential': 30, 'living_street': 20,
        'unclassified': 30, 'service': 20,
        'default': 30
    }
}

ALLOWED_ROADS = {
    'walk': frozenset({
        'primary', 'secondary', 'tertiary', 'residential', 'living_street',
        'unclassified', 'service', 'pedestrian', 'footway', 'path', 'steps', 'track'
    }),
    'bike': frozenset({
        'primary', 'secondary', 'tertiary', 'residential', 'living_street',
        'unclassified', 'service', 'cycleway', 'path', 'track'
    }),
    'drive': frozenset({
        'motorway', 'motorway_link', 'trunk', 'trunk_link',
        'primary', 'primary_link', 'secondary', 'secondary_link',
        'tertiary', 'tertiary_link', 'residential', 'living_street',
        'unclassified', 'service', 'road'
    })
}


def setup_parser(subparsers):
    """Setup the isochrone subcommand parser."""
    parser = subparsers.add_parser(
        'isochrone',
        help='Generate travel time polygons',
        description='Create isochrone polygons showing reachable area within travel time'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', required=True, help='Output GeoJSON file')
    parser.add_argument(
        '--lat',
        type=float,
        required=True,
        help='Origin latitude'
    )
    parser.add_argument(
        '--lon',
        type=float,
        required=True,
        help='Origin longitude'
    )
    parser.add_argument(
        '--time', '-t',
        default='5,10,15',
        help='Travel times in minutes (comma-separated, default: 5,10,15)'
    )
    parser.add_argument(
        '--mode', '-m',
        choices=['walk', 'bike', 'drive'],
        default='walk',
        help='Travel mode (default: walk)'
    )
    parser.add_argument(
        '--resolution',
        type=int,
        default=36,
        help='Number of points for polygon boundary (default: 36)'
    )

    parser.set_defaults(func=run)
    return parser


def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate distance in meters."""
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat/2)**2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def find_nearest_node(target_lon, target_lat, node_coords):
    """Find the nearest node to target coordinates."""
    min_dist = float('inf')
    nearest = None

    for node_id, (lon, lat) in node_coords.items():
        dist = haversine_distance(target_lon, target_lat, lon, lat)
        if dist < min_dist:
            min_dist = dist
            nearest = node_id

    return nearest, min_dist


def build_graph(ways, node_coords, mode):
    """Build adjacency graph from ways."""
    graph = {}  # node_id -> [(neighbor_id, travel_time_seconds), ...]
    speeds = DEFAULT_SPEEDS[mode]
    allowed = ALLOWED_ROADS[mode]

    for way in ways:
        highway = way.tags.get('highway')
        if highway not in allowed:
            continue

        speed = speeds.get(highway, speeds.get('default', 5))
        oneway = way.tags.get('oneway') in ('yes', '1', 'true')
        reverse = way.tags.get('oneway') == '-1'

        refs = way.node_refs
        for i in range(len(refs) - 1):
            from_id = refs[i]
            to_id = refs[i + 1]

            if from_id not in node_coords or to_id not in node_coords:
                continue

            from_coord = node_coords[from_id]
            to_coord = node_coords[to_id]

            distance = haversine_distance(
                from_coord[0], from_coord[1],
                to_coord[0], to_coord[1]
            )

            # Travel time in seconds
            travel_time = (distance / 1000) / speed * 3600

            # Add edges
            if from_id not in graph:
                graph[from_id] = []
            if to_id not in graph:
                graph[to_id] = []

            if mode == 'drive':
                if reverse:
                    graph[to_id].append((from_id, travel_time))
                    if not oneway:
                        graph[from_id].append((to_id, travel_time))
                else:
                    graph[from_id].append((to_id, travel_time))
                    if not oneway:
                        graph[to_id].append((from_id, travel_time))
            else:
                # Walking and biking are bidirectional
                graph[from_id].append((to_id, travel_time))
                graph[to_id].append((from_id, travel_time))

    return graph


def dijkstra(graph, start, max_time):
    """Run Dijkstra's algorithm to find all reachable nodes within max_time seconds."""
    distances = {start: 0}
    heap = [(0, start)]

    while heap:
        curr_dist, curr_node = heapq.heappop(heap)

        if curr_dist > max_time:
            continue

        if curr_dist > distances.get(curr_node, float('inf')):
            continue

        for neighbor, travel_time in graph.get(curr_node, []):
            new_dist = curr_dist + travel_time
            if new_dist < distances.get(neighbor, float('inf')) and new_dist <= max_time:
                distances[neighbor] = new_dist
                heapq.heappush(heap, (new_dist, neighbor))

    return distances


def create_isochrone_polygon(reachable_nodes, node_coords, origin_lon, origin_lat, resolution):
    """Create a polygon boundary from reachable nodes."""
    if not reachable_nodes:
        return None

    # Get coordinates of reachable nodes
    points = [(node_coords[n][0], node_coords[n][1]) for n in reachable_nodes if n in node_coords]

    if len(points) < 3:
        return None

    # Find boundary points by angle from origin
    angle_points = []
    for lon, lat in points:
        angle = math.atan2(lat - origin_lat, lon - origin_lon)
        dist = haversine_distance(origin_lon, origin_lat, lon, lat)
        angle_points.append((angle, dist, lon, lat))

    # Bin points by angle and find farthest in each bin
    bin_size = 2 * math.pi / resolution
    bins = {}

    for angle, dist, lon, lat in angle_points:
        bin_idx = int((angle + math.pi) / bin_size) % resolution
        if bin_idx not in bins or dist > bins[bin_idx][0]:
            bins[bin_idx] = (dist, lon, lat)

    # Create polygon from bins
    polygon = []
    for i in range(resolution):
        if i in bins:
            _, lon, lat = bins[i]
            polygon.append([lon, lat])
        else:
            # Interpolate from neighbors
            prev_idx = (i - 1) % resolution
            next_idx = (i + 1) % resolution
            if prev_idx in bins and next_idx in bins:
                lon = (bins[prev_idx][1] + bins[next_idx][1]) / 2
                lat = (bins[prev_idx][2] + bins[next_idx][2]) / 2
                polygon.append([lon, lat])

    if len(polygon) < 3:
        return None

    # Close the polygon
    polygon.append(polygon[0])

    return polygon


def run(args):
    """Execute the isochrone command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    # Parse travel times
    try:
        travel_times = [int(t.strip()) for t in args.time.split(',')]
    except ValueError:
        print(f"Error: Invalid travel times: {args.time}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse the file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Use parser's coordinate cache (includes ALL nodes, not just tagged)
    node_coords = {}
    for node_id, (lat, lon) in parser.node_coordinates.items():
        node_coords[node_id] = (float(lon), float(lat))

    print(f"Building {args.mode} network...", file=sys.stderr)

    # Build graph
    graph = build_graph(ways, node_coords, args.mode)

    if not graph:
        print("Error: No roads found for selected mode", file=sys.stderr)
        return 1

    # Find nearest node to origin
    origin_node, origin_dist = find_nearest_node(args.lon, args.lat, node_coords)

    if origin_node is None:
        print("Error: No road network near origin point", file=sys.stderr)
        return 1

    print(f"Origin: nearest node {origin_dist:.0f}m away", file=sys.stderr)

    # Generate isochrones for each travel time
    features = []

    # Add origin point
    features.append({
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [args.lon, args.lat]
        },
        "properties": {
            "type": "origin",
            "mode": args.mode
        }
    })

    # Sort times descending so larger polygons are added first
    for travel_mins in sorted(travel_times, reverse=True):
        travel_secs = travel_mins * 60

        print(f"Computing {travel_mins} min isochrone...", file=sys.stderr)

        # Run Dijkstra
        reachable = dijkstra(graph, origin_node, travel_secs)

        # Create polygon
        polygon = create_isochrone_polygon(
            reachable.keys(), node_coords,
            args.lon, args.lat, args.resolution
        )

        if polygon:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [polygon]
                },
                "properties": {
                    "time_minutes": travel_mins,
                    "mode": args.mode,
                    "reachable_nodes": len(reachable)
                }
            })

    output = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)

    elapsed = time.time() - start_time

    print(f"\nIsochrone complete:")
    print(f"  Origin: {args.lat}, {args.lon}")
    print(f"  Mode: {args.mode}")
    print(f"  Times: {travel_times} minutes")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
