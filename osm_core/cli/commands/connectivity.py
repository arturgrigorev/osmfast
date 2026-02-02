"""Connectivity command - find disconnected network components."""
import argparse
import json
import math
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
        'connectivity',
        help='Analyze network connectivity',
        description='Find disconnected components and dead ends in road network'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('--mode', '-m', choices=['walk', 'bike', 'drive'], default='drive')
    parser.add_argument('--format', '-f', choices=['geojson', 'json', 'text'], default='text')
    parser.add_argument(
        '--show-components',
        action='store_true',
        help='Output all components as GeoJSON'
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

            if from_id not in graph:
                graph[from_id] = set()
            if to_id not in graph:
                graph[to_id] = set()

            if mode == 'drive':
                if reverse:
                    graph[to_id].add(from_id)
                    if not oneway:
                        graph[from_id].add(to_id)
                else:
                    graph[from_id].add(to_id)
                    if not oneway:
                        graph[to_id].add(from_id)
            else:
                graph[from_id].add(to_id)
                graph[to_id].add(from_id)

    return graph


def find_components(graph):
    """Find connected components using DFS."""
    visited = set()
    components = []

    for start_node in graph:
        if start_node in visited:
            continue

        # BFS to find component
        component = set()
        queue = [start_node]

        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            component.add(node)

            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    queue.append(neighbor)

        components.append(component)

    return components


def find_dead_ends(graph):
    """Find nodes with only one connection (dead ends)."""
    dead_ends = []
    for node, neighbors in graph.items():
        if len(neighbors) == 1:
            dead_ends.append(node)
    return dead_ends


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

    print("Finding components...", file=sys.stderr)
    components = find_components(graph)
    components.sort(key=len, reverse=True)

    dead_ends = find_dead_ends(graph)
    intersections = [n for n, edges in graph.items() if len(edges) >= 3]

    elapsed = time.time() - start_time

    if args.format == 'text':
        print(f"\nNetwork Connectivity: {args.mode}")
        print("=" * 60)
        print(f"Total nodes: {len(graph)}")
        print(f"Connected components: {len(components)}")
        print(f"Dead ends: {len(dead_ends)}")
        print(f"Intersections (3+ edges): {len(intersections)}")

        if len(components) > 1:
            print(f"\nComponent sizes:")
            for i, comp in enumerate(components[:10], 1):
                pct = 100 * len(comp) / len(graph)
                print(f"  {i}. {len(comp)} nodes ({pct:.1f}%)")
            if len(components) > 10:
                print(f"  ... and {len(components) - 10} more small components")

            # Main component analysis
            main_size = len(components[0])
            isolated = sum(len(c) for c in components[1:])
            print(f"\nMain component: {main_size} nodes ({100*main_size/len(graph):.1f}%)")
            print(f"Isolated nodes: {isolated} ({100*isolated/len(graph):.1f}%)")
        else:
            print("\nNetwork is fully connected!")

        print(f"\n[{elapsed:.3f}s]")

        if not args.output:
            return 0

    # Generate output
    if args.format == 'geojson' or (args.output and args.show_components):
        features = []

        # Add components with different colors
        colors = ['#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF']

        for i, component in enumerate(components[:6]):
            for node_id in component:
                if node_id in node_coords:
                    lon, lat = node_coords[node_id]
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lon, lat]},
                        "properties": {
                            "component": i + 1,
                            "component_size": len(component),
                            "color": colors[i % len(colors)]
                        }
                    })

        # Add dead ends
        for node_id in dead_ends:
            if node_id in node_coords:
                lon, lat = node_coords[node_id]
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {"type": "dead_end"}
                })

        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output = {
            'mode': args.mode,
            'total_nodes': len(graph),
            'num_components': len(components),
            'num_dead_ends': len(dead_ends),
            'num_intersections': len(intersections),
            'is_connected': len(components) == 1,
            'components': [
                {
                    'id': i + 1,
                    'size': len(comp),
                    'percentage': round(100 * len(comp) / len(graph), 2)
                }
                for i, comp in enumerate(components[:20])
            ],
            'dead_ends': [
                {'node_id': n, 'lat': node_coords[n][1], 'lon': node_coords[n][0]}
                for n in dead_ends[:100] if n in node_coords
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
