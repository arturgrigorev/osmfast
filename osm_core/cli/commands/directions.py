"""Directions command - turn-by-turn navigation instructions."""
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
        'directions',
        help='Turn-by-turn directions',
        description='Get turn-by-turn navigation instructions'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('--from', dest='origin', required=True, help='Origin (lat,lon)')
    parser.add_argument('--to', dest='destination', required=True, help='Destination (lat,lon)')
    parser.add_argument('--mode', '-m', choices=['walk', 'bike', 'drive'], default='drive')
    parser.add_argument('-f', '--format', choices=['text', 'json'], default='text')

    parser.set_defaults(func=run)
    return parser


def haversine_distance(lon1, lat1, lon2, lat2):
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def calculate_bearing(lon1, lat1, lon2, lat2):
    """Calculate bearing from point 1 to point 2."""
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    x = math.sin(delta_lon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
    bearing = math.atan2(x, y)
    return (math.degrees(bearing) + 360) % 360


def get_turn_instruction(angle_change):
    """Get turn instruction from angle change."""
    if abs(angle_change) < 20:
        return "Continue straight"
    elif angle_change > 150:
        return "Make a U-turn"
    elif angle_change > 70:
        return "Turn right"
    elif angle_change > 20:
        return "Bear right"
    elif angle_change < -150:
        return "Make a U-turn"
    elif angle_change < -70:
        return "Turn left"
    elif angle_change < -20:
        return "Bear left"
    return "Continue"


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
                graph[f].append((t, travel_time))
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

    path, _ = dijkstra_path(graph, origin_node, dest_node)

    if path is None:
        print("Error: No route found", file=sys.stderr)
        return 1

    # Generate turn-by-turn directions
    instructions = []
    current_street = None
    segment_distance = 0
    segment_time = 0
    prev_bearing = None

    for i in range(len(path) - 1):
        from_id, to_id = path[i], path[i + 1]
        info = edge_info.get((from_id, to_id), {})
        street_name = info.get('name', 'Unnamed road')
        distance = info.get('distance', 0)
        time_s = info.get('time', 0)

        from_coord = node_coords[from_id]
        to_coord = node_coords[to_id]
        bearing = calculate_bearing(from_coord[0], from_coord[1], to_coord[0], to_coord[1])

        if current_street is None:
            current_street = street_name
            segment_distance = distance
            segment_time = time_s
            prev_bearing = bearing
            continue

        # Check for turn
        if street_name != current_street or (prev_bearing is not None and abs(bearing - prev_bearing) > 30):
            angle_change = bearing - prev_bearing if prev_bearing else 0
            if angle_change > 180:
                angle_change -= 360
            elif angle_change < -180:
                angle_change += 360

            turn = get_turn_instruction(angle_change) if prev_bearing else "Head"

            instructions.append({
                'instruction': f"{turn} onto {street_name}" if street_name != current_street else turn,
                'street': current_street,
                'distance_m': round(segment_distance, 1),
                'time_s': round(segment_time, 1)
            })

            current_street = street_name
            segment_distance = distance
            segment_time = time_s
        else:
            segment_distance += distance
            segment_time += time_s

        prev_bearing = bearing

    # Final segment
    if current_street:
        instructions.append({
            'instruction': f"Arrive at destination",
            'street': current_street,
            'distance_m': round(segment_distance, 1),
            'time_s': round(segment_time, 1)
        })

    total_distance = sum(i['distance_m'] for i in instructions)
    total_time = sum(i['time_s'] for i in instructions)

    elapsed = time.time() - start_time

    if args.format == 'text':
        print(f"\nDirections: {args.mode}")
        print("=" * 60)

        for i, inst in enumerate(instructions, 1):
            dist_str = f"{inst['distance_m']:.0f}m" if inst['distance_m'] < 1000 else f"{inst['distance_m']/1000:.1f}km"
            time_str = f"{inst['time_s']:.0f}s" if inst['time_s'] < 60 else f"{inst['time_s']/60:.1f}min"
            print(f"{i}. {inst['instruction']}")
            print(f"   - {dist_str}, {time_str}")
            print()

        print(f"Total: {total_distance/1000:.2f} km, {total_time/60:.1f} min")
        print(f"[{elapsed:.3f}s]")

        if args.output:
            output = {'instructions': instructions, 'total_distance_m': total_distance, 'total_time_s': total_time}
            with open(args.output, 'w') as f:
                json.dump(output, f, indent=2)
            print(f"\nSaved to {args.output}")

    elif args.format == 'json':
        output = {
            'mode': args.mode,
            'origin': {'lat': origin_lat, 'lon': origin_lon},
            'destination': {'lat': dest_lat, 'lon': dest_lon},
            'instructions': instructions,
            'total_distance_m': round(total_distance, 1),
            'total_time_s': round(total_time, 1)
        }
        output_str = json.dumps(output, indent=2)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(output_str)
        else:
            print(output_str)

    return 0
