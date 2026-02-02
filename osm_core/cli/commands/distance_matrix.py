"""Distance-matrix command - many-to-many distances."""
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
        'distance-matrix',
        help='Many-to-many distances',
        description='Calculate distance/time matrix between multiple points'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--points', '-p',
        required=True,
        help='Points as "lat1,lon1;lat2,lon2;..." or path to CSV file'
    )
    parser.add_argument('--mode', '-m', choices=['walk', 'bike', 'drive'], default='drive')
    parser.add_argument(
        '--metric',
        choices=['time', 'distance', 'both'],
        default='both',
        help='What to calculate (default: both)'
    )
    parser.add_argument('-f', '--format', choices=['json', 'csv', 'text'], default='text')

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
    speeds = DEFAULT_SPEEDS[mode]
    allowed = ALLOWED_ROADS[mode]

    for way in ways:
        highway = way.tags.get('highway')
        if highway not in allowed:
            continue

        speed = speeds.get(highway, speeds.get('default', 30))
        oneway = way.tags.get('oneway') in ('yes', '1', 'true')
        reverse = way.tags.get('oneway') == '-1'

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

    return graph


def dijkstra_all(graph, start, targets):
    """Find shortest paths from start to all targets."""
    distances = {start: (0, 0)}  # node -> (distance, time)
    heap = [(0, 0, start)]  # (time, distance, node)
    visited = set()
    results = {}
    remaining = set(targets)

    while heap and remaining:
        curr_time, curr_dist, curr_node = heapq.heappop(heap)

        if curr_node in visited:
            continue
        visited.add(curr_node)

        if curr_node in remaining:
            results[curr_node] = (curr_dist, curr_time)
            remaining.remove(curr_node)

        for neighbor, edge_dist, edge_time in graph.get(curr_node, []):
            if neighbor in visited:
                continue
            new_dist = curr_dist + edge_dist
            new_time = curr_time + edge_time
            if neighbor not in distances or new_time < distances[neighbor][1]:
                distances[neighbor] = (new_dist, new_time)
                heapq.heappush(heap, (new_time, new_dist, neighbor))

    return results


def parse_points(points_arg):
    """Parse points from argument or file."""
    if Path(points_arg).exists():
        # Read from CSV file
        points = []
        with open(points_arg, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(',')
                if len(parts) >= 2:
                    try:
                        lat, lon = float(parts[0]), float(parts[1])
                        name = parts[2].strip() if len(parts) > 2 else f"Point {len(points)+1}"
                        points.append((lat, lon, name))
                    except ValueError:
                        continue
        return points
    else:
        # Parse inline format
        points = []
        for i, wp in enumerate(points_arg.split(';')):
            parts = wp.strip().split(',')
            lat, lon = float(parts[0]), float(parts[1])
            name = parts[2].strip() if len(parts) > 2 else f"Point {i+1}"
            points.append((lat, lon, name))
        return points


def run(args):
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    try:
        points = parse_points(args.points)
        if len(points) < 2:
            raise ValueError("Need at least 2 points")
    except Exception as e:
        print(f"Error parsing points: {e}", file=sys.stderr)
        return 1

    start_time = time.time()

    parser_osm = UltraFastOSMParser()
    nodes, ways = parser_osm.parse_file_ultra_fast(str(input_path))

    # Use parser's coordinate cache (includes ALL nodes, not just tagged)
    node_coords = {}
    for node_id, (lat, lon) in parser_osm.node_coordinates.items():
        node_coords[node_id] = (float(lon), float(lat))

    print(f"Building {args.mode} network...", file=sys.stderr)
    graph = build_graph(ways, node_coords, args.mode)

    if not graph:
        print("Error: No roads found", file=sys.stderr)
        return 1

    # Find nearest nodes for all points
    point_nodes = []
    for lat, lon, name in points:
        node, dist = find_nearest_node(lon, lat, node_coords)
        if node is None:
            print(f"Warning: No road near {name}", file=sys.stderr)
        point_nodes.append(node)

    # Calculate matrix
    n = len(points)
    distance_matrix = [[None] * n for _ in range(n)]
    time_matrix = [[None] * n for _ in range(n)]

    for i in range(n):
        if point_nodes[i] is None:
            continue

        targets = [point_nodes[j] for j in range(n) if j != i and point_nodes[j] is not None]
        results = dijkstra_all(graph, point_nodes[i], targets)

        for j in range(n):
            if i == j:
                distance_matrix[i][j] = 0
                time_matrix[i][j] = 0
            elif point_nodes[j] in results:
                dist, time_s = results[point_nodes[j]]
                distance_matrix[i][j] = round(dist, 1)
                time_matrix[i][j] = round(time_s, 1)

    elapsed = time.time() - start_time

    if args.format == 'text':
        print(f"\nDistance Matrix ({args.mode})")
        print("=" * 60)

        # Header
        names = [p[2][:10] for p in points]
        header = "From\\To".ljust(12) + "".join(n.ljust(12) for n in names)
        print(header)
        print("-" * len(header))

        for i, (lat, lon, name) in enumerate(points):
            row = name[:10].ljust(12)
            for j in range(n):
                if args.metric in ('distance', 'both'):
                    val = distance_matrix[i][j]
                    cell = f"{val/1000:.1f}km" if val is not None else "N/A"
                else:
                    val = time_matrix[i][j]
                    cell = f"{val/60:.0f}m" if val is not None else "N/A"
                row += cell.ljust(12)
            print(row)

        if args.metric == 'both':
            print(f"\nTime Matrix (minutes)")
            print("-" * 60)
            for i, (lat, lon, name) in enumerate(points):
                row = name[:10].ljust(12)
                for j in range(n):
                    val = time_matrix[i][j]
                    cell = f"{val/60:.1f}" if val is not None else "N/A"
                    row += cell.ljust(12)
                print(row)

        print(f"\n[{elapsed:.3f}s]")

        if not args.output:
            return 0

    # Generate output
    output = {
        'mode': args.mode,
        'points': [{'name': p[2], 'lat': p[0], 'lon': p[1]} for p in points],
        'distance_matrix_m': distance_matrix,
        'time_matrix_s': time_matrix
    }

    if args.format == 'json' or args.output:
        output_str = json.dumps(output, indent=2)

    elif args.format == 'csv':
        import io
        buffer = io.StringIO()
        names = [p[2] for p in points]

        # Distance matrix
        buffer.write("Distance (m)," + ",".join(names) + "\n")
        for i, name in enumerate(names):
            row = [name] + [str(distance_matrix[i][j]) if distance_matrix[i][j] is not None else "" for j in range(n)]
            buffer.write(",".join(row) + "\n")

        buffer.write("\nTime (s)," + ",".join(names) + "\n")
        for i, name in enumerate(names):
            row = [name] + [str(time_matrix[i][j]) if time_matrix[i][j] is not None else "" for j in range(n)]
            buffer.write(",".join(row) + "\n")

        output_str = buffer.getvalue()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Matrix saved to {args.output}")
    elif args.format != 'text':
        print(output_str)

    return 0
