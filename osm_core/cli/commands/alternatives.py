"""Alternatives command - find multiple route options."""
import argparse
import heapq
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


DEFAULT_SPEEDS = {
    'walk': {'default': 5, 'steps': 3, 'path': 4, 'footway': 5, 'pedestrian': 5, 'residential': 5},
    'bike': {'default': 15, 'cycleway': 18, 'path': 12, 'residential': 15, 'tertiary': 18, 'secondary': 20},
    'drive': {
        'motorway': 110, 'motorway_link': 60, 'trunk': 90, 'trunk_link': 50,
        'primary': 60, 'primary_link': 40, 'secondary': 50, 'secondary_link': 35,
        'tertiary': 40, 'tertiary_link': 30, 'residential': 30, 'living_street': 20,
        'unclassified': 30, 'service': 20, 'default': 30
    }
}

ALLOWED_ROADS = {
    'walk': frozenset({'primary', 'secondary', 'tertiary', 'residential', 'living_street',
                       'unclassified', 'service', 'pedestrian', 'footway', 'path', 'steps', 'track'}),
    'bike': frozenset({'primary', 'secondary', 'tertiary', 'residential', 'living_street',
                       'unclassified', 'service', 'cycleway', 'path', 'track'}),
    'drive': frozenset({'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
                        'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'residential',
                        'living_street', 'unclassified', 'service', 'road'})
}


def setup_parser(subparsers):
    parser = subparsers.add_parser(
        'alternatives',
        help='Find multiple route options',
        description='Calculate alternative routes between two points'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('--from', dest='origin', required=True, help='Origin (lat,lon)')
    parser.add_argument('--to', dest='destination', required=True, help='Destination (lat,lon)')
    parser.add_argument('--mode', '-m', choices=['walk', 'bike', 'drive'], default='drive')
    parser.add_argument('--count', '-n', type=int, default=3, help='Number of alternatives (default: 3)')
    parser.add_argument('-f', '--format', choices=['geojson', 'json', 'text'], default='text')

    parser.set_defaults(func=run)
    return parser


def haversine_distance(lon1, lat1, lon2, lat2):
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def find_nearest_node(target_lon, target_lat, node_coords):
    min_dist = float('inf')
    nearest = None
    for node_id, (lon, lat) in node_coords.items():
        dist = haversine_distance(target_lon, target_lat, lon, lat)
        if dist < min_dist:
            min_dist = dist
            nearest = node_id
    return nearest, min_dist


def build_graph(ways, node_coords, mode):
    graph = {}
    edge_info = {}
    speeds = DEFAULT_SPEEDS[mode]
    allowed = ALLOWED_ROADS[mode]

    for way in ways:
        highway = way.tags.get('highway')
        if highway not in allowed:
            continue

        speed = speeds.get(highway, speeds.get('default', 30))
        oneway = way.tags.get('oneway') in ('yes', '1', 'true')
        reverse = way.tags.get('oneway') == '-1'
        name = way.tags.get('name', '')

        refs = way.node_refs
        for i in range(len(refs) - 1):
            from_id, to_id = refs[i], refs[i + 1]
            if from_id not in node_coords or to_id not in node_coords:
                continue

            from_coord, to_coord = node_coords[from_id], node_coords[to_id]
            distance = haversine_distance(from_coord[0], from_coord[1], to_coord[0], to_coord[1])
            travel_time = (distance / 1000) / speed * 3600

            if from_id not in graph:
                graph[from_id] = []
            if to_id not in graph:
                graph[to_id] = []

            def add_edge(f, t):
                graph[f].append((t, distance, travel_time))
                edge_info[(f, t)] = {'name': name, 'highway': highway, 'distance': distance, 'time': travel_time}

            if mode == 'drive':
                if reverse:
                    add_edge(to_id, from_id)
                    if not oneway:
                        add_edge(from_id, to_id)
                else:
                    add_edge(from_id, to_id)
                    if not oneway:
                        add_edge(to_id, from_id)
            else:
                add_edge(from_id, to_id)
                add_edge(to_id, from_id)

    return graph, edge_info


def dijkstra_with_penalty(graph, start, end, edge_penalties):
    """Dijkstra with edge penalties to find alternatives."""
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
            path = []
            node = end
            while node is not None:
                path.append(node)
                node = previous[node]
            return list(reversed(path)), distances[end]

        for neighbor, distance, time_cost in graph.get(curr_node, []):
            if neighbor in visited:
                continue

            edge = (curr_node, neighbor)
            penalty = edge_penalties.get(edge, 1.0)
            cost = time_cost * penalty

            new_dist = curr_dist + cost
            if new_dist < distances.get(neighbor, float('inf')):
                distances[neighbor] = new_dist
                previous[neighbor] = curr_node
                heapq.heappush(heap, (new_dist, neighbor))

    return None, None


def calculate_route_stats(path, edge_info):
    """Calculate total distance and time for a route."""
    total_distance = 0
    total_time = 0
    for i in range(len(path) - 1):
        info = edge_info.get((path[i], path[i + 1]), {})
        total_distance += info.get('distance', 0)
        total_time += info.get('time', 0)
    return total_distance, total_time


def run(args):
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    try:
        origin_lat, origin_lon = map(float, args.origin.split(','))
        dest_lat, dest_lon = map(float, args.destination.split(','))
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
    graph, edge_info = build_graph(ways, node_coords, args.mode)

    if not graph:
        print("Error: No roads found", file=sys.stderr)
        return 1

    origin_node, _ = find_nearest_node(origin_lon, origin_lat, node_coords)
    dest_node, _ = find_nearest_node(dest_lon, dest_lat, node_coords)

    if origin_node is None or dest_node is None:
        print("Error: Could not find road network", file=sys.stderr)
        return 1

    # Find alternative routes using edge penalization
    routes = []
    edge_penalties = {}
    penalty_factor = 2.0  # Increase cost of used edges

    for route_num in range(args.count):
        path, cost = dijkstra_with_penalty(graph, origin_node, dest_node, edge_penalties)

        if path is None:
            break

        # Check if this is a truly different route
        path_set = set(zip(path[:-1], path[1:]))
        is_unique = True
        for prev_route in routes:
            prev_set = set(zip(prev_route['path'][:-1], prev_route['path'][1:]))
            overlap = len(path_set & prev_set) / max(len(path_set), 1)
            if overlap > 0.8:  # More than 80% overlap
                is_unique = False
                break

        if not is_unique and route_num < args.count * 2:
            # Increase penalties more aggressively
            for i in range(len(path) - 1):
                edge = (path[i], path[i + 1])
                edge_penalties[edge] = edge_penalties.get(edge, 1.0) * penalty_factor * 2
            continue

        distance, time_s = calculate_route_stats(path, edge_info)
        coords = [list(node_coords[n]) for n in path]

        route_type = "fastest" if route_num == 0 else f"alternative {route_num}"

        routes.append({
            'type': route_type,
            'path': path,
            'coordinates': coords,
            'distance_m': round(distance, 1),
            'time_s': round(time_s, 1),
            'nodes': len(path)
        })

        # Penalize edges used in this route
        for i in range(len(path) - 1):
            edge = (path[i], path[i + 1])
            edge_penalties[edge] = edge_penalties.get(edge, 1.0) * penalty_factor

    elapsed = time.time() - start_time

    if not routes:
        print("Error: No routes found", file=sys.stderr)
        return 1

    if args.format == 'text':
        print(f"\nAlternative Routes: {args.mode}")
        print("=" * 60)

        for i, route in enumerate(routes, 1):
            time_diff = ""
            dist_diff = ""
            if i > 1:
                time_diff = f" (+{(route['time_s'] - routes[0]['time_s'])/60:.1f} min)"
                dist_diff = f" (+{(route['distance_m'] - routes[0]['distance_m'])/1000:.2f} km)"

            print(f"\n{i}. {route['type'].title()}")
            print(f"   Distance: {route['distance_m']/1000:.2f} km{dist_diff}")
            print(f"   Time: {route['time_s']/60:.1f} min{time_diff}")
            print(f"   Nodes: {route['nodes']}")

        print(f"\n[{elapsed:.3f}s]")

        if not args.output:
            return 0

    # Generate output
    if args.format == 'geojson' or args.output:
        colors = ['#0066FF', '#FF6600', '#00CC00', '#CC00CC', '#CCCC00']
        features = []

        for i, route in enumerate(routes):
            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": route['coordinates']},
                "properties": {
                    "route_type": route['type'],
                    "distance_m": route['distance_m'],
                    "time_s": route['time_s'],
                    "color": colors[i % len(colors)]
                }
            })

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [origin_lon, origin_lat]},
            "properties": {"type": "origin"}
        })
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [dest_lon, dest_lat]},
            "properties": {"type": "destination"}
        })

        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output = {
            'mode': args.mode,
            'origin': {'lat': origin_lat, 'lon': origin_lon},
            'destination': {'lat': dest_lat, 'lon': dest_lon},
            'routes': [{k: v for k, v in r.items() if k != 'path'} for r in routes]
        }
        output_str = json.dumps(output, indent=2)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Routes saved to {args.output}")
    elif args.format != 'text':
        print(output_str)

    return 0
