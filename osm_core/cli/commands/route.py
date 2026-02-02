"""Route command - calculate shortest/fastest path between points."""
import argparse
import heapq
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


DEFAULT_SPEEDS = {
    'walk': {
        'default': 5, 'steps': 3, 'path': 4, 'footway': 5,
        'pedestrian': 5, 'residential': 5, 'living_street': 5
    },
    'bike': {
        'default': 15, 'cycleway': 18, 'path': 12, 'residential': 15,
        'tertiary': 18, 'secondary': 20, 'primary': 15
    },
    'drive': {
        'motorway': 110, 'motorway_link': 60, 'trunk': 90, 'trunk_link': 50,
        'primary': 60, 'primary_link': 40, 'secondary': 50, 'secondary_link': 35,
        'tertiary': 40, 'tertiary_link': 30, 'residential': 30, 'living_street': 20,
        'unclassified': 30, 'service': 20, 'default': 30
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
    """Setup the route subcommand parser."""
    parser = subparsers.add_parser(
        'route',
        help='Calculate route between points',
        description='Find shortest or fastest path between two points'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file (GeoJSON)')
    parser.add_argument(
        '--from', dest='origin',
        required=True,
        help='Origin coordinates (lat,lon)'
    )
    parser.add_argument(
        '--to', dest='destination',
        required=True,
        help='Destination coordinates (lat,lon)'
    )
    parser.add_argument(
        '--mode', '-m',
        choices=['walk', 'bike', 'drive'],
        default='drive',
        help='Travel mode (default: drive)'
    )
    parser.add_argument(
        '--optimize',
        choices=['time', 'distance'],
        default='time',
        help='Optimize for time or distance (default: time)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'text'],
        default='text',
        help='Output format (default: text)'
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
    """Find nearest node to target."""
    min_dist = float('inf')
    nearest = None
    for node_id, (lon, lat) in node_coords.items():
        dist = haversine_distance(target_lon, target_lat, lon, lat)
        if dist < min_dist:
            min_dist = dist
            nearest = node_id
    return nearest, min_dist


def build_graph(ways, node_coords, mode, optimize):
    """Build routing graph."""
    graph = {}
    edge_info = {}  # (from, to) -> {way_id, highway, name, distance, time}
    speeds = DEFAULT_SPEEDS[mode]
    allowed = ALLOWED_ROADS[mode]

    for way in ways:
        highway = way.tags.get('highway')
        if highway not in allowed:
            continue

        speed = speeds.get(highway, speeds.get('default', 30))
        oneway_tag = way.tags.get('oneway', '')
        # oneway=yes/1/true means forward only, oneway=-1 means reverse only
        is_oneway = oneway_tag in ('yes', '1', 'true', '-1')
        is_reverse = oneway_tag == '-1'
        name = way.tags.get('name', '')

        refs = way.node_refs
        for i in range(len(refs) - 1):
            from_id, to_id = refs[i], refs[i + 1]

            if from_id not in node_coords or to_id not in node_coords:
                continue

            from_coord = node_coords[from_id]
            to_coord = node_coords[to_id]
            distance = haversine_distance(from_coord[0], from_coord[1], to_coord[0], to_coord[1])
            travel_time = (distance / 1000) / speed * 3600  # seconds

            cost = travel_time if optimize == 'time' else distance

            if from_id not in graph:
                graph[from_id] = []
            if to_id not in graph:
                graph[to_id] = []

            def add_edge(f, t):
                graph[f].append((t, cost))
                edge_info[(f, t)] = {
                    'way_id': way.id, 'highway': highway, 'name': name,
                    'distance': distance, 'time': travel_time
                }

            if mode == 'drive':
                if is_reverse:
                    # oneway=-1: only allow travel from to_id to from_id
                    add_edge(to_id, from_id)
                elif is_oneway:
                    # oneway=yes/1/true: only allow travel from from_id to to_id
                    add_edge(from_id, to_id)
                else:
                    # Bidirectional road
                    add_edge(from_id, to_id)
                    add_edge(to_id, from_id)
            else:
                # Walk/bike modes are always bidirectional
                add_edge(from_id, to_id)
                add_edge(to_id, from_id)

    return graph, edge_info


def dijkstra_path(graph, start, end):
    """Find shortest path using Dijkstra."""
    distances = {start: 0}
    previous = {start: None}
    heap = [(0, start)]
    visited = set()

    while heap:
        curr_dist, curr_node = heapq.heappop(heap)

        if curr_node in visited:
            continue
        visited.add(curr_node)

        if curr_node == end:
            # Reconstruct path
            path = []
            node = end
            while node is not None:
                path.append(node)
                node = previous[node]
            return list(reversed(path)), distances[end]

        for neighbor, cost in graph.get(curr_node, []):
            if neighbor in visited:
                continue
            new_dist = curr_dist + cost
            if new_dist < distances.get(neighbor, float('inf')):
                distances[neighbor] = new_dist
                previous[neighbor] = curr_node
                heapq.heappush(heap, (new_dist, neighbor))

    return None, None


def run(args):
    """Execute the route command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    # Parse coordinates
    try:
        origin_parts = args.origin.split(',')
        origin_lat, origin_lon = float(origin_parts[0]), float(origin_parts[1])
        dest_parts = args.destination.split(',')
        dest_lat, dest_lon = float(dest_parts[0]), float(dest_parts[1])
    except (ValueError, IndexError):
        print("Error: Coordinates must be in format: lat,lon", file=sys.stderr)
        return 1

    start_time = time.time()

    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Use parser's coordinate cache (includes ALL nodes, not just tagged)
    node_coords = {}
    for node_id, (lat, lon) in parser.node_coordinates.items():
        node_coords[node_id] = (float(lon), float(lat))

    print(f"Building {args.mode} network...", file=sys.stderr)
    graph, edge_info = build_graph(ways, node_coords, args.mode, args.optimize)

    if not graph:
        print("Error: No roads found for selected mode", file=sys.stderr)
        return 1

    # Find nearest nodes
    origin_node, origin_dist = find_nearest_node(origin_lon, origin_lat, node_coords)
    dest_node, dest_dist = find_nearest_node(dest_lon, dest_lat, node_coords)

    if origin_node is None or dest_node is None:
        print("Error: Could not find road network near points", file=sys.stderr)
        return 1

    print(f"Origin: {origin_dist:.0f}m from road", file=sys.stderr)
    print(f"Destination: {dest_dist:.0f}m from road", file=sys.stderr)

    # Find route
    path, total_cost = dijkstra_path(graph, origin_node, dest_node)

    if path is None:
        print("Error: No route found between points", file=sys.stderr)
        return 1

    # Calculate route stats
    total_distance = 0
    total_time = 0
    route_coords = []
    segments = []

    for i in range(len(path) - 1):
        from_id, to_id = path[i], path[i + 1]
        info = edge_info.get((from_id, to_id), {})
        total_distance += info.get('distance', 0)
        total_time += info.get('time', 0)
        route_coords.append(list(node_coords[from_id]))
        segments.append({
            'from': from_id,
            'to': to_id,
            'name': info.get('name', ''),
            'highway': info.get('highway', ''),
            'distance': info.get('distance', 0),
            'time': info.get('time', 0)
        })

    route_coords.append(list(node_coords[path[-1]]))

    elapsed = time.time() - start_time

    # Output
    if args.format == 'text':
        print(f"\nRoute: {args.mode} ({args.optimize})")
        print("=" * 50)
        print(f"From: {origin_lat:.6f}, {origin_lon:.6f}")
        print(f"To:   {dest_lat:.6f}, {dest_lon:.6f}")
        print(f"\nDistance: {total_distance/1000:.2f} km")
        print(f"Time: {total_time/60:.1f} min")
        print(f"Nodes: {len(path)}")
        print(f"\nCalculated in {elapsed:.3f}s")

        if not args.output:
            return 0

    if args.format == 'geojson' or args.output:
        output = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": route_coords},
                    "properties": {
                        "mode": args.mode,
                        "optimize": args.optimize,
                        "distance_m": round(total_distance, 1),
                        "time_s": round(total_time, 1),
                        "nodes": len(path)
                    }
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [origin_lon, origin_lat]},
                    "properties": {"type": "origin"}
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [dest_lon, dest_lat]},
                    "properties": {"type": "destination"}
                }
            ]
        }
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output = {
            'mode': args.mode,
            'optimize': args.optimize,
            'origin': {'lat': origin_lat, 'lon': origin_lon},
            'destination': {'lat': dest_lat, 'lon': dest_lon},
            'distance_m': round(total_distance, 1),
            'time_s': round(total_time, 1),
            'path': path,
            'coordinates': route_coords,
            'segments': segments
        }
        output_str = json.dumps(output, indent=2)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Route saved to {args.output}")
    elif args.format != 'text':
        print(output_str)

    return 0
