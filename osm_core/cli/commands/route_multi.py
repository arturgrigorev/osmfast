"""Route-multi command - route through multiple waypoints."""
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
    """Setup the route-multi subcommand parser."""
    parser = subparsers.add_parser(
        'route-multi',
        help='Route through multiple waypoints',
        description='Calculate route visiting multiple points in order'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--waypoints', '-w',
        required=True,
        help='Waypoints as "lat1,lon1;lat2,lon2;lat3,lon3"'
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


def build_graph(ways, node_coords, mode, optimize):
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
            cost = travel_time if optimize == 'time' else distance

            if from_id not in graph:
                graph[from_id] = []
            if to_id not in graph:
                graph[to_id] = []

            def add_edge(f, t):
                graph[f].append((t, cost))
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


def dijkstra_path(graph, start, end):
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
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    # Parse waypoints
    try:
        waypoints = []
        for wp in args.waypoints.split(';'):
            lat, lon = wp.strip().split(',')
            waypoints.append((float(lat), float(lon)))
        if len(waypoints) < 2:
            raise ValueError("Need at least 2 waypoints")
    except (ValueError, IndexError) as e:
        print(f"Error: Invalid waypoints format. Use 'lat1,lon1;lat2,lon2;...'", file=sys.stderr)
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

    # Find nearest nodes for all waypoints
    waypoint_nodes = []
    for i, (lat, lon) in enumerate(waypoints):
        node, dist = find_nearest_node(lon, lat, node_coords)
        if node is None:
            print(f"Error: No road near waypoint {i+1}", file=sys.stderr)
            return 1
        waypoint_nodes.append(node)
        print(f"Waypoint {i+1}: {dist:.0f}m from road", file=sys.stderr)

    # Calculate route through all waypoints
    full_path = []
    total_distance = 0
    total_time = 0
    legs = []

    for i in range(len(waypoint_nodes) - 1):
        from_node, to_node = waypoint_nodes[i], waypoint_nodes[i + 1]
        path, cost = dijkstra_path(graph, from_node, to_node)

        if path is None:
            print(f"Error: No route between waypoints {i+1} and {i+2}", file=sys.stderr)
            return 1

        # Calculate leg stats
        leg_distance = 0
        leg_time = 0
        for j in range(len(path) - 1):
            info = edge_info.get((path[j], path[j + 1]), {})
            leg_distance += info.get('distance', 0)
            leg_time += info.get('time', 0)

        legs.append({
            'from_waypoint': i + 1,
            'to_waypoint': i + 2,
            'distance_m': round(leg_distance, 1),
            'time_s': round(leg_time, 1),
            'nodes': len(path)
        })

        total_distance += leg_distance
        total_time += leg_time

        # Add to full path (avoid duplicates)
        if full_path:
            full_path.extend(path[1:])
        else:
            full_path.extend(path)

    route_coords = [list(node_coords[n]) for n in full_path]

    elapsed = time.time() - start_time

    if args.format == 'text':
        print(f"\nMulti-waypoint Route: {args.mode}")
        print("=" * 50)
        print(f"Waypoints: {len(waypoints)}")
        for i, (lat, lon) in enumerate(waypoints):
            print(f"  {i+1}. {lat:.6f}, {lon:.6f}")

        print(f"\nLegs:")
        for leg in legs:
            print(f"  {leg['from_waypoint']} -> {leg['to_waypoint']}: {leg['distance_m']/1000:.2f} km, {leg['time_s']/60:.1f} min")

        print(f"\nTotal distance: {total_distance/1000:.2f} km")
        print(f"Total time: {total_time/60:.1f} min")
        print(f"Total nodes: {len(full_path)}")
        print(f"\nCalculated in {elapsed:.3f}s")

        if not args.output:
            return 0

    # Generate output
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": route_coords},
            "properties": {
                "mode": args.mode,
                "waypoints": len(waypoints),
                "distance_m": round(total_distance, 1),
                "time_s": round(total_time, 1)
            }
        }
    ]

    for i, (lat, lon) in enumerate(waypoints):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"type": "waypoint", "order": i + 1}
        })

    if args.format == 'geojson' or (args.output and args.format != 'json'):
        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)
    else:
        output = {
            'mode': args.mode,
            'waypoints': [{'lat': lat, 'lon': lon} for lat, lon in waypoints],
            'legs': legs,
            'total_distance_m': round(total_distance, 1),
            'total_time_s': round(total_time, 1),
            'coordinates': route_coords
        }
        output_str = json.dumps(output, indent=2)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Route saved to {args.output}")
    elif args.format != 'text':
        print(output_str)

    return 0
