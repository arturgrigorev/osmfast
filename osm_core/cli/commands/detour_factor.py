"""Detour-factor command - compare network vs straight-line distances."""
import argparse
import heapq
import json
import math
import random
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
                        'living_street', 'unclassified', 'service', 'road'})
}


def setup_parser(subparsers):
    parser = subparsers.add_parser(
        'detour-factor',
        help='Analyze network directness',
        description='Calculate detour factor (network distance / straight-line distance)'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('--mode', '-m', choices=['walk', 'bike', 'drive'], default='drive')
    parser.add_argument('--sample', type=int, default=100, help='Number of random pairs to sample')
    parser.add_argument('--format', '-f', choices=['json', 'text'], default='text')

    parser.set_defaults(func=run)
    return parser


def haversine_distance(lon1, lat1, lon2, lat2):
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def build_graph(ways, node_coords, mode):
    graph = {}
    allowed = ALLOWED_ROADS[mode]

    for way in ways:
        highway = way.tags.get('highway')
        if highway not in allowed:
            continue

        oneway = way.tags.get('oneway') in ('yes', '1', 'true')
        reverse = way.tags.get('oneway') == '-1'

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

            if mode == 'drive':
                if reverse:
                    graph[to_id].append((from_id, distance))
                    if not oneway:
                        graph[from_id].append((to_id, distance))
                else:
                    graph[from_id].append((to_id, distance))
                    if not oneway:
                        graph[to_id].append((from_id, distance))
            else:
                graph[from_id].append((to_id, distance))
                graph[to_id].append((from_id, distance))

    return graph


def dijkstra_distance(graph, start, end):
    """Find shortest path distance."""
    distances = {start: 0}
    heap = [(0, start)]
    visited = set()

    while heap:
        curr_dist, curr_node = heapq.heappop(heap)

        if curr_node in visited:
            continue
        visited.add(curr_node)

        if curr_node == end:
            return curr_dist

        for neighbor, edge_dist in graph.get(curr_node, []):
            if neighbor in visited:
                continue
            new_dist = curr_dist + edge_dist
            if new_dist < distances.get(neighbor, float('inf')):
                distances[neighbor] = new_dist
                heapq.heappush(heap, (new_dist, neighbor))

    return None


def find_largest_component(graph):
    """Find the largest connected component."""
    visited = set()
    largest = []

    for start in graph:
        if start in visited:
            continue

        component = []
        queue = [start]
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            for neighbor, _ in graph.get(node, []):
                if neighbor not in visited:
                    queue.append(neighbor)

        if len(component) > len(largest):
            largest = component

    return largest


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

    print(f"Building {args.mode} network...", file=sys.stderr)
    graph = build_graph(ways, node_coords, args.mode)

    if not graph:
        print("Error: No roads found", file=sys.stderr)
        return 1

    # Find largest connected component to sample from
    largest_component = find_largest_component(graph)
    if len(largest_component) < 2:
        print("Error: No connected road network found", file=sys.stderr)
        return 1

    print(f"Using largest component ({len(largest_component)} nodes)...", file=sys.stderr)

    # Sample random pairs from largest component only
    graph_nodes = largest_component
    n_pairs = min(args.sample, len(graph_nodes) * (len(graph_nodes) - 1) // 2)

    print(f"Sampling {n_pairs} random pairs...", file=sys.stderr)

    detour_factors = []
    samples = []

    attempts = 0
    max_attempts = n_pairs * 10

    while len(detour_factors) < n_pairs and attempts < max_attempts:
        attempts += 1

        # Pick random pair
        node1, node2 = random.sample(graph_nodes, 2)

        coord1 = node_coords[node1]
        coord2 = node_coords[node2]

        straight_dist = haversine_distance(coord1[0], coord1[1], coord2[0], coord2[1])

        # Skip very short distances
        if straight_dist < 100:
            continue

        network_dist = dijkstra_distance(graph, node1, node2)

        if network_dist is None:
            continue

        factor = network_dist / straight_dist

        detour_factors.append(factor)
        samples.append({
            'from': {'node': node1, 'lat': coord1[1], 'lon': coord1[0]},
            'to': {'node': node2, 'lat': coord2[1], 'lon': coord2[0]},
            'straight_line_m': round(straight_dist, 1),
            'network_m': round(network_dist, 1),
            'detour_factor': round(factor, 3)
        })

        if len(detour_factors) % 20 == 0:
            print(f"  Processed {len(detour_factors)}/{n_pairs}...", file=sys.stderr)

    elapsed = time.time() - start_time

    if not detour_factors:
        print("Error: Could not calculate any routes", file=sys.stderr)
        return 1

    # Statistics
    avg_factor = sum(detour_factors) / len(detour_factors)
    min_factor = min(detour_factors)
    max_factor = max(detour_factors)
    median_factor = sorted(detour_factors)[len(detour_factors) // 2]

    # Percentiles
    sorted_factors = sorted(detour_factors)
    p10 = sorted_factors[int(len(sorted_factors) * 0.1)]
    p90 = sorted_factors[int(len(sorted_factors) * 0.9)]

    if args.format == 'text':
        print(f"\nDetour Factor Analysis ({args.mode})")
        print("=" * 60)
        print(f"Samples analyzed: {len(detour_factors)}")

        print(f"\nDetour Factor Statistics:")
        print(f"  Mean:   {avg_factor:.3f}")
        print(f"  Median: {median_factor:.3f}")
        print(f"  Min:    {min_factor:.3f}")
        print(f"  Max:    {max_factor:.3f}")
        print(f"  10th percentile: {p10:.3f}")
        print(f"  90th percentile: {p90:.3f}")

        # Interpretation
        print(f"\nInterpretation:")
        if avg_factor < 1.2:
            print("  Excellent network directness")
        elif avg_factor < 1.4:
            print("  Good network directness")
        elif avg_factor < 1.6:
            print("  Average network directness")
        else:
            print("  Poor network directness (many detours required)")

        # Show some examples
        print(f"\nExample routes:")
        for sample in sorted(samples, key=lambda x: x['detour_factor'])[:3]:
            print(f"  Direct: {sample['straight_line_m']/1000:.2f}km, "
                  f"Network: {sample['network_m']/1000:.2f}km, "
                  f"Factor: {sample['detour_factor']:.2f}")

        print(f"\n[{elapsed:.3f}s]")

        if not args.output:
            return 0

    # Generate output
    output = {
        'mode': args.mode,
        'samples': len(detour_factors),
        'statistics': {
            'mean': round(avg_factor, 4),
            'median': round(median_factor, 4),
            'min': round(min_factor, 4),
            'max': round(max_factor, 4),
            'p10': round(p10, 4),
            'p90': round(p90, 4)
        },
        'sample_routes': samples[:20]  # First 20 samples
    }
    output_str = json.dumps(output, indent=2)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Results saved to {args.output}")
    elif args.format != 'text':
        print(output_str)

    return 0
