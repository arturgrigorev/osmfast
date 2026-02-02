"""Convert command - format conversion."""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser
from ...utils.xml_utils import xml_escape
from ...utils.geo_utils import calculate_polygon_area


def setup_parser(subparsers):
    """Setup the convert subcommand parser."""
    parser = subparsers.add_parser(
        'convert',
        help='Convert between file formats',
        description='Convert OSM files to various formats'
    )

    parser.add_argument('input', help='Input file')
    parser.add_argument('-o', '--output', required=True,
                        help='Output file')
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv', 'osm'],
        help='Output format (auto-detect from extension if not specified)'
    )
    parser.add_argument(
        '--nodes-only',
        action='store_true',
        help='Only convert nodes'
    )
    parser.add_argument(
        '--ways-only',
        action='store_true',
        help='Only convert ways'
    )
    parser.add_argument(
        '--tagged-only',
        action='store_true',
        help='Only elements with tags'
    )
    parser.add_argument(
        '--include-area',
        action='store_true',
        help='Calculate area for polygons'
    )
    parser.add_argument(
        '--include-length',
        action='store_true',
        help='Calculate length for ways'
    )
    parser.add_argument(
        '--flatten-tags',
        action='store_true',
        help='Flatten tags into columns (CSV)'
    )
    parser.add_argument(
        '--compact',
        action='store_true',
        help='Compact output (no indentation)'
    )

    parser.set_defaults(func=run)
    return parser


def detect_format(filepath):
    """Detect format from file extension."""
    ext = Path(filepath).suffix.lower()
    format_map = {
        '.geojson': 'geojson',
        '.json': 'json',
        '.csv': 'csv',
        '.osm': 'osm',
        '.xml': 'osm'
    }
    return format_map.get(ext, 'geojson')


def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate distance between two points in meters."""
    import math
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat/2)**2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def calculate_way_length(coords):
    """Calculate total length of way in meters."""
    if len(coords) < 2:
        return 0
    total = 0
    for i in range(len(coords) - 1):
        total += haversine_distance(coords[i][0], coords[i][1],
                                    coords[i+1][0], coords[i+1][1])
    return total


def convert_to_geojson(nodes, ways, node_coords, args):
    """Convert to GeoJSON format."""
    features = []

    if not args.ways_only:
        for node in nodes:
            if args.tagged_only and not node.tags:
                continue

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(node.lon), float(node.lat)]
                },
                "properties": {
                    "id": node.id,
                    "type": "node",
                    **node.tags
                }
            })

    if not args.nodes_only:
        for way in ways:
            if args.tagged_only and not way.tags:
                continue

            coords = []
            for ref in way.node_refs:
                if ref in node_coords:
                    coords.append(node_coords[ref])

            if len(coords) < 2:
                continue

            is_closed = len(coords) > 2 and coords[0] == coords[-1]
            props = {"id": way.id, "type": "way", **way.tags}

            if is_closed:
                geom = {"type": "Polygon", "coordinates": [coords]}
                if args.include_area:
                    props["area_sqm"] = round(calculate_polygon_area(coords), 1)
            else:
                geom = {"type": "LineString", "coordinates": coords}

            if args.include_length:
                props["length_m"] = round(calculate_way_length(coords), 1)

            features.append({"type": "Feature", "geometry": geom, "properties": props})

    return {"type": "FeatureCollection", "features": features}


def convert_to_json(nodes, ways, node_coords, args):
    """Convert to plain JSON format."""
    data = {"nodes": [], "ways": []}

    if not args.ways_only:
        for node in nodes:
            if args.tagged_only and not node.tags:
                continue
            data["nodes"].append({
                "id": node.id,
                "lat": float(node.lat),
                "lon": float(node.lon),
                "tags": node.tags
            })

    if not args.nodes_only:
        for way in ways:
            if args.tagged_only and not way.tags:
                continue

            coords = []
            for ref in way.node_refs:
                if ref in node_coords:
                    coords.append(node_coords[ref])

            way_data = {
                "id": way.id,
                "node_refs": way.node_refs,
                "coordinates": coords,
                "tags": way.tags
            }

            if args.include_length and len(coords) >= 2:
                way_data["length_m"] = round(calculate_way_length(coords), 1)

            if args.include_area and len(coords) > 2:
                is_closed = coords[0] == coords[-1]
                if is_closed:
                    way_data["area_sqm"] = round(calculate_polygon_area(coords), 1)

            data["ways"].append(way_data)

    return data


def convert_to_csv(nodes, ways, node_coords, args):
    """Convert to CSV format."""
    rows = []

    # Collect all unique tag keys if flattening
    tag_keys = set()
    if args.flatten_tags:
        for node in nodes:
            tag_keys.update(node.tags.keys())
        for way in ways:
            tag_keys.update(way.tags.keys())
        tag_keys = sorted(tag_keys)

    if not args.ways_only:
        for node in nodes:
            if args.tagged_only and not node.tags:
                continue

            row = {
                'type': 'node',
                'id': node.id,
                'lat': float(node.lat),
                'lon': float(node.lon)
            }

            if args.flatten_tags:
                for key in tag_keys:
                    row[key] = node.tags.get(key, '')
            else:
                row['tags'] = json.dumps(node.tags)

            rows.append(row)

    if not args.nodes_only:
        for way in ways:
            if args.tagged_only and not way.tags:
                continue

            coords = []
            for ref in way.node_refs:
                if ref in node_coords:
                    coords.append(node_coords[ref])

            if not coords:
                continue

            centroid_lon = sum(c[0] for c in coords) / len(coords)
            centroid_lat = sum(c[1] for c in coords) / len(coords)

            row = {
                'type': 'way',
                'id': way.id,
                'lat': centroid_lat,
                'lon': centroid_lon
            }

            if args.include_length and len(coords) >= 2:
                row['length_m'] = round(calculate_way_length(coords), 1)

            if args.include_area and len(coords) > 2:
                is_closed = coords[0] == coords[-1]
                if is_closed:
                    row['area_sqm'] = round(calculate_polygon_area(coords), 1)

            if args.flatten_tags:
                for key in tag_keys:
                    row[key] = way.tags.get(key, '')
            else:
                row['tags'] = json.dumps(way.tags)

            rows.append(row)

    return rows, tag_keys if args.flatten_tags else None


def convert_to_osm(nodes, ways, node_coords, args):
    """Convert to OSM XML format."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<osm version="0.6" generator="osmfast">']

    if not args.ways_only:
        for node in nodes:
            if args.tagged_only and not node.tags:
                continue

            if node.tags:
                lines.append(f'  <node id="{node.id}" lat="{node.lat}" lon="{node.lon}">')
                for k, v in node.tags.items():
                    lines.append(f'    <tag k="{xml_escape(k)}" v="{xml_escape(v)}"/>')
                lines.append('  </node>')
            else:
                lines.append(f'  <node id="{node.id}" lat="{node.lat}" lon="{node.lon}"/>')

    if not args.nodes_only:
        for way in ways:
            if args.tagged_only and not way.tags:
                continue

            lines.append(f'  <way id="{way.id}">')
            for ref in way.node_refs:
                lines.append(f'    <nd ref="{ref}"/>')
            for k, v in way.tags.items():
                lines.append(f'    <tag k="{xml_escape(k)}" v="{xml_escape(v)}"/>')
            lines.append('  </way>')

    lines.append('</osm>')
    return '\n'.join(lines)


def run(args):
    """Execute the convert command."""
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    # Detect output format
    out_format = args.format or detect_format(args.output)

    start_time = time.time()

    # Parse input
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Build node coordinate lookup
    node_coords = {}
    for node in nodes:
        node_coords[node.id] = [float(node.lon), float(node.lat)]

    # Convert based on format
    if out_format == 'geojson':
        output = convert_to_geojson(nodes, ways, node_coords, args)
        indent = None if args.compact else 2
        output_str = json.dumps(output, indent=indent)

    elif out_format == 'json':
        output = convert_to_json(nodes, ways, node_coords, args)
        indent = None if args.compact else 2
        output_str = json.dumps(output, indent=indent)

    elif out_format == 'csv':
        rows, tag_keys = convert_to_csv(nodes, ways, node_coords, args)

        import io
        buffer = io.StringIO()

        if rows:
            fieldnames = list(rows[0].keys())
            writer = csv.DictWriter(buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        output_str = buffer.getvalue()

    elif out_format == 'osm':
        output_str = convert_to_osm(nodes, ways, node_coords, args)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output_str)

    elapsed = time.time() - start_time

    node_count = len(nodes) if not args.ways_only else 0
    way_count = len(ways) if not args.nodes_only else 0

    print(f"Converted to {out_format}: {output_path}")
    print(f"  Nodes: {node_count}, Ways: {way_count}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
