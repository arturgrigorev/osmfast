"""Network command - export road network as graph."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


# Default speeds in km/h for different highway types
DEFAULT_SPEEDS = {
    'motorway': 110,
    'motorway_link': 60,
    'trunk': 90,
    'trunk_link': 50,
    'primary': 60,
    'primary_link': 40,
    'secondary': 50,
    'secondary_link': 35,
    'tertiary': 40,
    'tertiary_link': 30,
    'residential': 30,
    'living_street': 20,
    'unclassified': 30,
    'service': 20,
    'road': 30,
    'track': 15,
    'path': 5,
    'footway': 5,
    'cycleway': 15,
    'pedestrian': 5,
    'steps': 3
}


def setup_parser(subparsers):
    """Setup the network subcommand parser."""
    parser = subparsers.add_parser(
        'network',
        help='Export road network as graph',
        description='Export road network in graph formats for routing and analysis'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file (required unless --stats)')
    parser.add_argument(
        '-f', '--format',
        choices=['graphml', 'json', 'geojson', 'csv'],
        default='json',
        help='Output format (default: json)'
    )
    parser.add_argument(
        '--mode',
        choices=['drive', 'walk', 'bike', 'all'],
        default='drive',
        help='Travel mode for filtering roads (default: drive)'
    )
    parser.add_argument(
        '--directed',
        action='store_true',
        help='Create directed graph (respects oneway)'
    )
    parser.add_argument(
        '--include-speeds',
        action='store_true',
        help='Include speed estimates and travel times'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show network statistics only'
    )

    parser.set_defaults(func=run)
    return parser


# Road types by travel mode
ROAD_MODES = {
    'drive': frozenset({
        'motorway', 'motorway_link', 'trunk', 'trunk_link',
        'primary', 'primary_link', 'secondary', 'secondary_link',
        'tertiary', 'tertiary_link', 'residential', 'living_street',
        'unclassified', 'service', 'road'
    }),
    'walk': frozenset({
        'primary', 'secondary', 'tertiary', 'residential', 'living_street',
        'unclassified', 'service', 'pedestrian', 'footway', 'path',
        'steps', 'track'
    }),
    'bike': frozenset({
        'primary', 'secondary', 'tertiary', 'residential', 'living_street',
        'unclassified', 'service', 'cycleway', 'path', 'track'
    }),
    'all': frozenset(DEFAULT_SPEEDS.keys())
}


def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate distance in meters."""
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat/2)**2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def parse_speed(value):
    """Parse maxspeed tag to km/h."""
    if not value:
        return None
    value = str(value).strip().lower()
    if 'mph' in value:
        try:
            return int(float(value.replace('mph', '').strip()) * 1.60934)
        except ValueError:
            return None
    value = value.replace('km/h', '').replace('kmh', '').strip()
    try:
        return int(float(value))
    except ValueError:
        return None


def run(args):
    """Execute the network command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    if not args.stats and not args.output:
        print("Error: --output is required unless using --stats", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse the file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Build node coordinate lookup from parser's cache (includes ALL nodes, not just tagged)
    node_coords = {}
    for node_id, (lat, lon) in parser.node_coordinates.items():
        node_coords[node_id] = (float(lon), float(lat))

    # Get allowed road types for mode
    allowed_roads = ROAD_MODES.get(args.mode, ROAD_MODES['all'])

    # Build graph
    graph_nodes = {}  # node_id -> {lon, lat, ...}
    graph_edges = []  # list of edge dicts

    for way in ways:
        highway = way.tags.get('highway')
        if highway not in allowed_roads:
            continue

        # Get way properties
        name = way.tags.get('name')
        oneway = way.tags.get('oneway') in ('yes', '1', 'true', '-1')
        reverse = way.tags.get('oneway') == '-1'

        # Get speed
        speed = parse_speed(way.tags.get('maxspeed'))
        if not speed:
            speed = DEFAULT_SPEEDS.get(highway, 30)

        # Build edges from node refs
        refs = way.node_refs
        for i in range(len(refs) - 1):
            from_id = refs[i]
            to_id = refs[i + 1]

            if from_id not in node_coords or to_id not in node_coords:
                continue

            from_coord = node_coords[from_id]
            to_coord = node_coords[to_id]

            # Add nodes to graph
            if from_id not in graph_nodes:
                graph_nodes[from_id] = {
                    'id': from_id,
                    'lon': from_coord[0],
                    'lat': from_coord[1]
                }
            if to_id not in graph_nodes:
                graph_nodes[to_id] = {
                    'id': to_id,
                    'lon': to_coord[0],
                    'lat': to_coord[1]
                }

            # Calculate distance
            distance = haversine_distance(
                from_coord[0], from_coord[1],
                to_coord[0], to_coord[1]
            )

            # Calculate travel time (in seconds)
            travel_time = (distance / 1000) / speed * 3600

            edge = {
                'way_id': way.id,
                'from': from_id,
                'to': to_id,
                'highway': highway,
                'name': name,
                'length_m': round(distance, 1),
                'oneway': oneway
            }

            if args.include_speeds:
                edge['speed_kmh'] = speed
                edge['travel_time_s'] = round(travel_time, 1)

            if args.directed:
                if reverse:
                    edge['from'], edge['to'] = edge['to'], edge['from']
                graph_edges.append(edge)
                if not oneway:
                    # Add reverse edge
                    rev_edge = edge.copy()
                    rev_edge['from'], rev_edge['to'] = edge['to'], edge['from']
                    graph_edges.append(rev_edge)
            else:
                graph_edges.append(edge)

    elapsed = time.time() - start_time

    # Statistics mode
    if args.stats:
        print(f"\nNetwork Statistics: {args.input}")
        print("=" * 60)
        print(f"Mode: {args.mode}")
        print(f"Nodes: {len(graph_nodes)}")
        print(f"Edges: {len(graph_edges)}")

        total_length = sum(e['length_m'] for e in graph_edges)
        print(f"Total length: {total_length/1000:.1f} km")

        # Degree distribution
        in_degree = {}
        out_degree = {}
        for edge in graph_edges:
            out_degree[edge['from']] = out_degree.get(edge['from'], 0) + 1
            in_degree[edge['to']] = in_degree.get(edge['to'], 0) + 1

        # Find dead ends and intersections
        dead_ends = sum(1 for n in graph_nodes if in_degree.get(n, 0) + out_degree.get(n, 0) == 1)
        intersections = sum(1 for n in graph_nodes if in_degree.get(n, 0) + out_degree.get(n, 0) >= 3)

        print(f"\nTopology:")
        print(f"  Dead ends: {dead_ends}")
        print(f"  Intersections (3+ edges): {intersections}")

        # By highway type
        print(f"\nBy highway type:")
        by_type = {}
        for e in graph_edges:
            h = e['highway']
            if h not in by_type:
                by_type[h] = {'count': 0, 'length': 0}
            by_type[h]['count'] += 1
            by_type[h]['length'] += e['length_m']

        for h, data in sorted(by_type.items(), key=lambda x: -x[1]['length']):
            print(f"  {h}: {data['count']} edges, {data['length']/1000:.1f} km")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'json':
        output = {
            'metadata': {
                'mode': args.mode,
                'directed': args.directed,
                'node_count': len(graph_nodes),
                'edge_count': len(graph_edges)
            },
            'nodes': list(graph_nodes.values()),
            'edges': graph_edges
        }
        output_str = json.dumps(output, indent=2)

    elif args.format == 'geojson':
        features = []

        # Add edges as LineStrings
        for edge in graph_edges:
            from_node = graph_nodes[edge['from']]
            to_node = graph_nodes[edge['to']]

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [from_node['lon'], from_node['lat']],
                        [to_node['lon'], to_node['lat']]
                    ]
                },
                "properties": {k: v for k, v in edge.items() if k not in ['from', 'to']}
            })

        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'graphml':
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append('<graphml xmlns="http://graphml.graphdrawing.org/xmlns">')
        lines.append('  <key id="lon" for="node" attr.name="lon" attr.type="double"/>')
        lines.append('  <key id="lat" for="node" attr.name="lat" attr.type="double"/>')
        lines.append('  <key id="length" for="edge" attr.name="length_m" attr.type="double"/>')
        lines.append('  <key id="highway" for="edge" attr.name="highway" attr.type="string"/>')
        lines.append('  <key id="name" for="edge" attr.name="name" attr.type="string"/>')

        edge_default = 'directed' if args.directed else 'undirected'
        lines.append(f'  <graph id="G" edgedefault="{edge_default}">')

        for node in graph_nodes.values():
            lines.append(f'    <node id="{node["id"]}">')
            lines.append(f'      <data key="lon">{node["lon"]}</data>')
            lines.append(f'      <data key="lat">{node["lat"]}</data>')
            lines.append('    </node>')

        for i, edge in enumerate(graph_edges):
            lines.append(f'    <edge id="e{i}" source="{edge["from"]}" target="{edge["to"]}">')
            lines.append(f'      <data key="length">{edge["length_m"]}</data>')
            lines.append(f'      <data key="highway">{edge["highway"]}</data>')
            if edge.get('name'):
                lines.append(f'      <data key="name">{edge["name"]}</data>')
            lines.append('    </edge>')

        lines.append('  </graph>')
        lines.append('</graphml>')
        output_str = '\n'.join(lines)

    elif args.format == 'csv':
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        headers = ['from', 'to', 'highway', 'name', 'length_m', 'oneway']
        if args.include_speeds:
            headers.extend(['speed_kmh', 'travel_time_s'])
        writer.writerow(headers)

        for edge in graph_edges:
            row = [edge['from'], edge['to'], edge['highway'], edge.get('name', ''),
                   edge['length_m'], edge['oneway']]
            if args.include_speeds:
                row.extend([edge.get('speed_kmh', ''), edge.get('travel_time_s', '')])
            writer.writerow(row)

        output_str = buffer.getvalue()

    # Write output
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nNetwork exported:")
    print(f"  Nodes: {len(graph_nodes)}")
    print(f"  Edges: {len(graph_edges)}")
    print(f"  Format: {args.format}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
