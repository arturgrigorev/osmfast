"""Split command - divide large OSM files."""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser
from ...utils.xml_utils import xml_escape


def setup_parser(subparsers):
    """Setup the split subcommand parser."""
    parser = subparsers.add_parser(
        'split',
        help='Divide large OSM files into smaller parts',
        description='Split OSM files by grid, bounding boxes, or file size'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', required=True,
                        help='Output directory')

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        '--grid',
        help='Split into grid (e.g., 2x2, 4x4)'
    )
    mode_group.add_argument(
        '--bbox-file',
        help='File with bounding boxes (JSON or CSV)'
    )
    mode_group.add_argument(
        '--count',
        type=int,
        help='Split into N roughly equal parts'
    )

    parser.add_argument(
        '--prefix',
        default='tile',
        help='Output file prefix (default: tile)'
    )
    parser.add_argument(
        '--format',
        choices=['osm', 'geojson'],
        default='osm',
        help='Output format (default: osm)'
    )

    parser.set_defaults(func=run)
    return parser


def get_file_bounds(nodes):
    """Calculate bounding box from nodes."""
    if not nodes:
        return None

    min_lat = min_lon = float('inf')
    max_lat = max_lon = float('-inf')

    for node in nodes:
        lat, lon = float(node.lat), float(node.lon)
        min_lat = min(min_lat, lat)
        max_lat = max(max_lat, lat)
        min_lon = min(min_lon, lon)
        max_lon = max(max_lon, lon)

    return min_lat, min_lon, max_lat, max_lon


def generate_grid_bboxes(bounds, rows, cols):
    """Generate grid of bounding boxes."""
    min_lat, min_lon, max_lat, max_lon = bounds
    lat_step = (max_lat - min_lat) / rows
    lon_step = (max_lon - min_lon) / cols

    bboxes = []
    for row in range(rows):
        for col in range(cols):
            bbox = {
                'name': f'{row}_{col}',
                'min_lat': min_lat + row * lat_step,
                'max_lat': min_lat + (row + 1) * lat_step,
                'min_lon': min_lon + col * lon_step,
                'max_lon': min_lon + (col + 1) * lon_step
            }
            bboxes.append(bbox)

    return bboxes


def point_in_bbox(lat, lon, bbox):
    """Check if point is in bounding box."""
    return (bbox['min_lat'] <= lat <= bbox['max_lat'] and
            bbox['min_lon'] <= lon <= bbox['max_lon'])


def write_osm_file(filepath, nodes, ways, node_coords):
    """Write OSM XML file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<osm version="0.6" generator="osmfast">\n')

        for node in nodes:
            f.write(f'  <node id="{node.id}" lat="{node.lat}" lon="{node.lon}"')
            if node.tags:
                f.write('>\n')
                for k, v in node.tags.items():
                    f.write(f'    <tag k="{xml_escape(k)}" v="{xml_escape(v)}"/>\n')
                f.write('  </node>\n')
            else:
                f.write('/>\n')

        for way in ways:
            f.write(f'  <way id="{way.id}">\n')
            for ref in way.node_refs:
                f.write(f'    <nd ref="{ref}"/>\n')
            for k, v in way.tags.items():
                f.write(f'    <tag k="{xml_escape(k)}" v="{xml_escape(v)}"/>\n')
            f.write('  </way>\n')

        f.write('</osm>\n')


def write_geojson_file(filepath, nodes, ways, node_coords):
    """Write GeoJSON file."""
    features = []

    for node in nodes:
        if node.tags:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(node.lon), float(node.lat)]
                },
                "properties": {"id": node.id, **node.tags}
            })

    for way in ways:
        coords = []
        for ref in way.node_refs:
            if ref in node_coords:
                coords.append(node_coords[ref])

        if len(coords) >= 2:
            if len(coords) > 2 and coords[0] == coords[-1]:
                geom_type = "Polygon"
                coordinates = [coords]
            else:
                geom_type = "LineString"
                coordinates = coords

            features.append({
                "type": "Feature",
                "geometry": {"type": geom_type, "coordinates": coordinates},
                "properties": {"id": way.id, **way.tags}
            })

    output = {"type": "FeatureCollection", "features": features}

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)


def run(args):
    """Execute the split command."""
    input_path = Path(args.input)
    output_dir = Path(args.output)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()

    # Parse the file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Build node coordinate lookup
    node_coords = {}
    for node in nodes:
        node_coords[node.id] = [float(node.lon), float(node.lat)]

    # Get file bounds
    bounds = get_file_bounds(nodes)
    if not bounds:
        print("Error: No nodes found in file", file=sys.stderr)
        return 1

    # Generate bounding boxes based on mode
    if args.grid:
        parts = args.grid.lower().split('x')
        if len(parts) != 2:
            print("Error: Grid format should be NxM (e.g., 2x2)", file=sys.stderr)
            return 1
        rows, cols = int(parts[0]), int(parts[1])
        bboxes = generate_grid_bboxes(bounds, rows, cols)

    elif args.bbox_file:
        bbox_path = Path(args.bbox_file)
        if not bbox_path.exists():
            print(f"Error: Bbox file not found: {args.bbox_file}", file=sys.stderr)
            return 1

        with open(bbox_path) as f:
            if bbox_path.suffix == '.json':
                bboxes = json.load(f)
            else:
                # CSV format: name,min_lat,min_lon,max_lat,max_lon
                import csv
                reader = csv.DictReader(f)
                bboxes = list(reader)
                for bbox in bboxes:
                    for key in ['min_lat', 'max_lat', 'min_lon', 'max_lon']:
                        bbox[key] = float(bbox[key])

    elif args.count:
        # Split into N parts by latitude bands
        rows = int(math.ceil(math.sqrt(args.count)))
        cols = int(math.ceil(args.count / rows))
        bboxes = generate_grid_bboxes(bounds, rows, cols)[:args.count]

    # Assign nodes to tiles
    tile_nodes = {i: [] for i in range(len(bboxes))}
    node_to_tile = {}

    for node in nodes:
        lat, lon = float(node.lat), float(node.lon)
        for i, bbox in enumerate(bboxes):
            if point_in_bbox(lat, lon, bbox):
                tile_nodes[i].append(node)
                node_to_tile[node.id] = i
                break

    # Assign ways to tiles (by first node)
    tile_ways = {i: [] for i in range(len(bboxes))}
    for way in ways:
        if way.node_refs:
            first_ref = way.node_refs[0]
            if first_ref in node_to_tile:
                tile_idx = node_to_tile[first_ref]
                tile_ways[tile_idx].append(way)

                # Include all nodes referenced by this way
                for ref in way.node_refs:
                    if ref in node_coords and ref not in node_to_tile:
                        # Find node object
                        for node in nodes:
                            if node.id == ref:
                                tile_nodes[tile_idx].append(node)
                                break

    # Write output files
    ext = 'geojson' if args.format == 'geojson' else 'osm'
    written_files = 0

    for i, bbox in enumerate(bboxes):
        tile_name = bbox.get('name', str(i))
        output_file = output_dir / f"{args.prefix}_{tile_name}.{ext}"

        t_nodes = tile_nodes[i]
        t_ways = tile_ways[i]

        if not t_nodes and not t_ways:
            continue

        if args.format == 'geojson':
            write_geojson_file(output_file, t_nodes, t_ways, node_coords)
        else:
            write_osm_file(output_file, t_nodes, t_ways, node_coords)

        written_files += 1

    elapsed = time.time() - start_time

    print(f"\nSplit complete:")
    print(f"  Input: {len(nodes)} nodes, {len(ways)} ways")
    print(f"  Output: {written_files} files in {output_dir}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
