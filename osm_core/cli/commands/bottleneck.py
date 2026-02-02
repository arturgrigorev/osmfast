"""Bottleneck command - identify network chokepoints."""
import argparse
import json
import math
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
        'bottleneck',
        help='Identify network chokepoints',
        description='Find critical edges/nodes whose removal disconnects the network'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('-n', '--top', type=int, default=20, help='Show top N bottlenecks')
    parser.add_argument('--format', '-f', choices=['geojson', 'json', 'text'], default='text')

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
    edges = []  # (from_id, to_id, way_id, name, highway)

    for way in ways:
        highway = way.tags.get('highway')
        if highway not in ALLOWED_ROADS:
            continue

        name = way.tags.get('name', '')
        refs = way.node_refs

        for i in range(len(refs) - 1):
            from_id, to_id = refs[i], refs[i + 1]
            if from_id not in node_coords or to_id not in node_coords:
                continue

            if from_id not in graph:
                graph[from_id] = set()
            if to_id not in graph:
                graph[to_id] = set()

            graph[from_id].add(to_id)
            graph[to_id].add(from_id)

            edges.append((from_id, to_id, way.id, name, highway))

    return graph, edges


def count_components(graph):
    """Count connected components."""
    if not graph:
        return 0

    visited = set()
    count = 0

    for start in graph:
        if start in visited:
            continue
        count += 1

        queue = [start]
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    queue.append(neighbor)

    return count


def find_bridges(graph):
    """Find bridge edges (whose removal disconnects the graph)."""
    bridges = []
    original_components = count_components(graph)

    # For each edge, check if removing it increases components
    checked = set()

    for node, neighbors in graph.items():
        for neighbor in neighbors:
            edge = tuple(sorted([node, neighbor]))
            if edge in checked:
                continue
            checked.add(edge)

            # Temporarily remove edge
            graph[node].remove(neighbor)
            graph[neighbor].remove(node)

            new_components = count_components(graph)

            # Restore edge
            graph[node].add(neighbor)
            graph[neighbor].add(node)

            if new_components > original_components:
                bridges.append(edge)

    return bridges


def find_articulation_points(graph):
    """Find articulation points (cut vertices)."""
    articulation = []
    original_components = count_components(graph)

    for node in list(graph.keys()):
        if len(graph[node]) < 2:
            continue

        # Temporarily remove node
        neighbors = graph[node].copy()
        del graph[node]
        for neighbor in neighbors:
            graph[neighbor].discard(node)

        new_components = count_components(graph)

        # Restore node
        graph[node] = neighbors
        for neighbor in neighbors:
            graph[neighbor].add(node)

        if new_components > original_components:
            articulation.append((node, new_components - original_components))

    return articulation


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
    graph, edges = build_graph(ways, node_coords)

    if not graph:
        print("Error: No roads found", file=sys.stderr)
        return 1

    print(f"Nodes: {len(graph)}, Edges: {len(edges)}", file=sys.stderr)

    print("Finding bridge edges...", file=sys.stderr)
    bridges = find_bridges(graph)

    print("Finding articulation points...", file=sys.stderr)
    articulation = find_articulation_points(graph)
    articulation.sort(key=lambda x: -x[1])

    # Build edge lookup
    edge_info = {}
    for from_id, to_id, way_id, name, highway in edges:
        edge = tuple(sorted([from_id, to_id]))
        edge_info[edge] = {'way_id': way_id, 'name': name, 'highway': highway}

    elapsed = time.time() - start_time

    if args.format == 'text':
        print(f"\nNetwork Bottlenecks")
        print("=" * 60)
        print(f"Total nodes: {len(graph)}")
        print(f"Total edges: {len(edges)}")

        print(f"\nBridge Edges (critical links): {len(bridges)}")
        for i, edge in enumerate(bridges[:args.top], 1):
            info = edge_info.get(edge, {})
            name = info.get('name') or info.get('highway', 'Unknown')
            print(f"  {i}. {name} (way {info.get('way_id', '?')})")

        print(f"\nArticulation Points (critical nodes): {len(articulation)}")
        for i, (node_id, split_count) in enumerate(articulation[:args.top], 1):
            lon, lat = node_coords.get(node_id, (0, 0))
            print(f"  {i}. Node {node_id} (would create {split_count} new components)")
            print(f"      Location: {lat:.6f}, {lon:.6f}")

        print(f"\n[{elapsed:.3f}s]")

        if not args.output:
            return 0

    # Generate output
    if args.format == 'geojson' or args.output:
        features = []

        # Add bridge edges
        for edge in bridges:
            if edge[0] in node_coords and edge[1] in node_coords:
                info = edge_info.get(edge, {})
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            list(node_coords[edge[0]]),
                            list(node_coords[edge[1]])
                        ]
                    },
                    "properties": {
                        "type": "bridge_edge",
                        "name": info.get('name', ''),
                        "highway": info.get('highway', ''),
                        "way_id": info.get('way_id')
                    }
                })

        # Add articulation points
        for node_id, split_count in articulation[:args.top]:
            if node_id in node_coords:
                lon, lat = node_coords[node_id]
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "type": "articulation_point",
                        "node_id": node_id,
                        "split_count": split_count
                    }
                })

        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output = {
            'total_nodes': len(graph),
            'total_edges': len(edges),
            'bridge_edges': [
                {
                    'nodes': list(edge),
                    'name': edge_info.get(edge, {}).get('name', ''),
                    'highway': edge_info.get(edge, {}).get('highway', '')
                }
                for edge in bridges
            ],
            'articulation_points': [
                {
                    'node_id': node_id,
                    'split_count': split_count,
                    'lat': node_coords[node_id][1] if node_id in node_coords else None,
                    'lon': node_coords[node_id][0] if node_id in node_coords else None
                }
                for node_id, split_count in articulation[:args.top]
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
