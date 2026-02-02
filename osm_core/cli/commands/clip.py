"""Clip command - clip by polygon."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser
from ...utils.xml_utils import xml_escape


def setup_parser(subparsers):
    """Setup the clip subcommand parser."""
    parser = subparsers.add_parser(
        'clip',
        help='Clip OSM data by polygon',
        description='Clip OSM data using a polygon boundary (GeoJSON)'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', required=True, help='Output file')
    parser.add_argument(
        '--polygon',
        required=True,
        help='Clipping polygon (GeoJSON file)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['osm', 'geojson'],
        default='osm',
        help='Output format (default: osm)'
    )
    parser.add_argument(
        '--complete-ways',
        action='store_true',
        help='Include complete ways even if partially outside'
    )

    parser.set_defaults(func=run)
    return parser


def point_in_polygon(x, y, polygon):
    """Check if point is inside polygon using ray casting."""
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def load_polygon(filepath):
    """Load polygon from GeoJSON file."""
    with open(filepath) as f:
        data = json.load(f)

    # Handle FeatureCollection
    if data['type'] == 'FeatureCollection':
        for feature in data['features']:
            if feature['geometry']['type'] == 'Polygon':
                return feature['geometry']['coordinates'][0]
            elif feature['geometry']['type'] == 'MultiPolygon':
                return feature['geometry']['coordinates'][0][0]
    # Handle Feature
    elif data['type'] == 'Feature':
        if data['geometry']['type'] == 'Polygon':
            return data['geometry']['coordinates'][0]
        elif data['geometry']['type'] == 'MultiPolygon':
            return data['geometry']['coordinates'][0][0]
    # Handle direct geometry
    elif data['type'] == 'Polygon':
        return data['coordinates'][0]
    elif data['type'] == 'MultiPolygon':
        return data['coordinates'][0][0]

    raise ValueError("No polygon found in GeoJSON")


def run(args):
    """Execute the clip command."""
    input_path = Path(args.input)
    polygon_path = Path(args.polygon)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    if not polygon_path.exists():
        print(f"Error: Polygon file not found: {args.polygon}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Load clipping polygon
    try:
        polygon = load_polygon(polygon_path)
    except Exception as e:
        print(f"Error loading polygon: {e}", file=sys.stderr)
        return 1

    # Parse OSM file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    node_coords = {}
    for node in nodes:
        node_coords[node.id] = [float(node.lon), float(node.lat)]

    # Filter nodes inside polygon
    inside_nodes = set()
    clipped_nodes = []

    for node in nodes:
        lon, lat = float(node.lon), float(node.lat)
        if point_in_polygon(lon, lat, polygon):
            inside_nodes.add(node.id)
            clipped_nodes.append(node)

    # Filter ways
    clipped_ways = []
    needed_nodes = set()

    for way in ways:
        refs_inside = [ref for ref in way.node_refs if ref in inside_nodes]

        if args.complete_ways:
            # Include if any node is inside
            if refs_inside:
                clipped_ways.append(way)
                needed_nodes.update(way.node_refs)
        else:
            # Only include if all nodes are inside
            if len(refs_inside) == len(way.node_refs):
                clipped_ways.append(way)

    # Add any additional nodes needed for complete ways
    if args.complete_ways:
        for node in nodes:
            if node.id in needed_nodes and node.id not in inside_nodes:
                clipped_nodes.append(node)

    elapsed = time.time() - start_time

    # Write output
    if args.format == 'osm':
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<osm version="0.6" generator="osmfast">\n')

            for node in clipped_nodes:
                if node.tags:
                    f.write(f'  <node id="{node.id}" lat="{node.lat}" lon="{node.lon}">\n')
                    for k, v in node.tags.items():
                        f.write(f'    <tag k="{xml_escape(k)}" v="{xml_escape(v)}"/>\n')
                    f.write('  </node>\n')
                else:
                    f.write(f'  <node id="{node.id}" lat="{node.lat}" lon="{node.lon}"/>\n')

            for way in clipped_ways:
                f.write(f'  <way id="{way.id}">\n')
                for ref in way.node_refs:
                    f.write(f'    <nd ref="{ref}"/>\n')
                for k, v in way.tags.items():
                    f.write(f'    <tag k="{xml_escape(k)}" v="{xml_escape(v)}"/>\n')
                f.write('  </way>\n')

            f.write('</osm>\n')

    elif args.format == 'geojson':
        features = []

        for node in clipped_nodes:
            if node.tags:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [float(node.lon), float(node.lat)]},
                    "properties": {"id": node.id, **node.tags}
                })

        for way in clipped_ways:
            coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
            if len(coords) >= 2:
                is_closed = len(coords) > 2 and coords[0] == coords[-1]
                if is_closed:
                    geom = {"type": "Polygon", "coordinates": [coords]}
                else:
                    geom = {"type": "LineString", "coordinates": coords}
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {"id": way.id, **way.tags}
                })

        output = {"type": "FeatureCollection", "features": features}
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

    print(f"\nClip complete:")
    print(f"  Nodes: {len(clipped_nodes)}")
    print(f"  Ways: {len(clipped_ways)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
