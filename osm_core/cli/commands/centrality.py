"""Centrality command - find most important network nodes."""
import argparse
import heapq
import json
import math
import random
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


ALLOWED_ROADS = frozenset({
    'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
    'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'residential',
    'living_street', 'unclassified', 'service', 'road'
})


def setup_parser(subparsers):
    parser = subparsers.add_parser(
        'centrality',
        help='Find most important network nodes',
        description='Calculate betweenness centrality for road intersections'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '-n', '--top',
        type=int,
        default=20,
        help='Show top N nodes (default: 20)'
    )
    parser.add_argument(
        '--sample',
        type=int,
        default=100,
        help='Sample size for approximation (default: 100)'
    )
    parser.add_argument(
        '--format', '-f',
        choices=['geojson', 'json', 'text'],
        default='text'
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


def build_graph(ways, node_coords):
    graph = {}

    for way in ways:
        highway = way.tags.get('highway')
        if highway not in ALLOWED_ROADS:
            continue

        refs = way.node_refs
        for i in range(len(refs) - 1):
            from_id, to_id = refs[i], refs[i + 1]
            if from_id not in node_coords or to_id not in node_coords:
                continue

            from_coord, to_coord = node_coords[from_id], node_coords[to_id]
            distance = haversine_distance(from_coord[0], from_coord[1], to_coord[0], to_coord[1])

            if from_id not in graph:
                graph[from_id] = []
            if to_id not in graph:
                graph[to_id] = []

            graph[from_id].append((to_id, distance))
            graph[to_id].append((from_id, distance))

    return graph


def dijkstra_with_paths(graph, start):
    """Dijkstra that returns all shortest paths."""
    distances = {start: 0}
    paths = {start: [[start]]}
    heap = [(0, start)]
    visited = set()

    while heap:
        curr_dist, curr_node = heapq.heappop(heap)

        if curr_node in visited:
            continue
        visited.add(curr_node)

        for neighbor, edge_dist in graph.get(curr_node, []):
            new_dist = curr_dist + edge_dist

            if neighbor not in distances or new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
                paths[neighbor] = [p + [neighbor] for p in paths[curr_node]]
                heapq.heappush(heap, (new_dist, neighbor))
            elif new_dist == distances[neighbor]:
                paths[neighbor].extend([p + [neighbor] for p in paths[curr_node]])

    return distances, paths


def calculate_betweenness(graph, sample_size):
    """Calculate approximate betweenness centrality."""
    nodes = list(graph.keys())
    centrality = {n: 0.0 for n in nodes}

    # Sample source nodes
    sample_nodes = random.sample(nodes, min(sample_size, len(nodes)))

    for i, source in enumerate(sample_nodes):
        if (i + 1) % 10 == 0:
            print(f"  Processing {i+1}/{len(sample_nodes)}...", file=sys.stderr)

        distances, paths = dijkstra_with_paths(graph, source)

        for target in nodes:
            if target == source or target not in paths:
                continue

            all_paths = paths[target]
            if not all_paths:
                continue

            # Count how many times each node appears in shortest paths
            for path in all_paths:
                for node in path[1:-1]:  # Exclude source and target
                    centrality[node] += 1.0 / len(all_paths)

    # Normalize
    n = len(nodes)
    if n > 2:
        scale = 2.0 / ((n - 1) * (n - 2))
        for node in centrality:
            centrality[node] *= scale * (len(nodes) / len(sample_nodes))

    return centrality


def run(args):
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Use parser's coordinate cache (includes ALL nodes, not just tagged)
    node_coords = {}
    for node_id, (lat, lon) in parser.node_coordinates.items():
        node_coords[node_id] = (float(lon), float(lat))

    print("Building network...", file=sys.stderr)
    graph = build_graph(ways, node_coords)

    if not graph:
        print("Error: No roads found", file=sys.stderr)
        return 1

    # Find intersections (nodes with degree >= 3)
    intersections = {n for n, edges in graph.items() if len(edges) >= 3}
    print(f"Found {len(intersections)} intersections", file=sys.stderr)

    print(f"Calculating centrality (sample={args.sample})...", file=sys.stderr)
    centrality = calculate_betweenness(graph, args.sample)

    # Sort by centrality
    sorted_nodes = sorted(centrality.items(), key=lambda x: -x[1])
    top_nodes = sorted_nodes[:args.top]

    elapsed = time.time() - start_time

    if args.format == 'text':
        print(f"\nTop {args.top} Most Central Nodes")
        print("=" * 60)

        for i, (node_id, score) in enumerate(top_nodes, 1):
            lon, lat = node_coords.get(node_id, (0, 0))
            degree = len(graph.get(node_id, []))
            is_intersection = "intersection" if node_id in intersections else "node"
            print(f"{i:2}. Node {node_id}")
            print(f"    Centrality: {score:.6f}")
            print(f"    Degree: {degree} ({is_intersection})")
            print(f"    Location: {lat:.6f}, {lon:.6f}")
            print()

        print(f"[{elapsed:.3f}s]")

        if not args.output:
            return 0

    # Generate output
    results = []
    for rank, (node_id, score) in enumerate(top_nodes, 1):
        lon, lat = node_coords.get(node_id, (0, 0))
        results.append({
            'rank': rank,
            'node_id': node_id,
            'centrality': round(score, 6),
            'degree': len(graph.get(node_id, [])),
            'is_intersection': node_id in intersections,
            'lat': lat,
            'lon': lon
        })

    if args.format == 'geojson' or args.output:
        features = []
        for r in results:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r['lon'], r['lat']]},
                "properties": {
                    "rank": r['rank'],
                    "node_id": r['node_id'],
                    "centrality": r['centrality'],
                    "degree": r['degree'],
                    "is_intersection": r['is_intersection']
                }
            })
        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output = {
            'total_nodes': len(graph),
            'intersections': len(intersections),
            'sample_size': args.sample,
            'top_nodes': results
        }
        output_str = json.dumps(output, indent=2)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Results saved to {args.output}")
    elif args.format != 'text':
        print(output_str)

    return 0
