"""Info command - quick file information."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the info subcommand parser."""
    parser = subparsers.add_parser(
        'info',
        help='Quick file information',
        description='Display quick summary information about an OSM file'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )
    parser.add_argument(
        '--oneline',
        action='store_true',
        help='Single line output'
    )

    parser.set_defaults(func=run)
    return parser


def format_size(size_bytes):
    """Format file size in human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def run(args):
    """Execute the info command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    # File info
    file_size = os.path.getsize(input_path)
    file_name = input_path.name

    # Parse
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    node_count = len(nodes)
    way_count = len(ways)

    # Quick bbox calculation
    if nodes:
        lats = [float(n.lat) for n in nodes]
        lons = [float(n.lon) for n in nodes]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        bbox = [min_lon, min_lat, max_lon, max_lat]
    else:
        bbox = None

    # Count tagged nodes
    tagged_nodes = sum(1 for n in nodes if n.tags)
    tagged_ways = sum(1 for w in ways if w.tags)

    # Top tags
    tag_counts = {}
    for node in nodes:
        for key in node.tags:
            tag_counts[key] = tag_counts.get(key, 0) + 1
    for way in ways:
        for key in way.tags:
            tag_counts[key] = tag_counts.get(key, 0) + 1

    top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:5]

    elapsed = time.time() - start_time

    info = {
        'file': file_name,
        'size': file_size,
        'size_human': format_size(file_size),
        'nodes': node_count,
        'ways': way_count,
        'total': node_count + way_count,
        'tagged_nodes': tagged_nodes,
        'tagged_ways': tagged_ways,
        'bbox': bbox,
        'top_tags': [{'key': k, 'count': c} for k, c in top_tags],
        'parse_time': round(elapsed, 3)
    }

    if args.json:
        print(json.dumps(info, indent=2))
        return 0

    if args.oneline:
        bbox_str = f"[{bbox[0]:.4f},{bbox[1]:.4f},{bbox[2]:.4f},{bbox[3]:.4f}]" if bbox else "N/A"
        print(f"{file_name}: {node_count} nodes, {way_count} ways, {format_size(file_size)}, bbox={bbox_str}")
        return 0

    # Default output
    print(f"\n{file_name}")
    print("=" * 50)
    print(f"Size:      {format_size(file_size)} ({file_size:,} bytes)")
    print(f"Nodes:     {node_count:,} ({tagged_nodes:,} tagged)")
    print(f"Ways:      {way_count:,} ({tagged_ways:,} tagged)")
    print(f"Total:     {node_count + way_count:,} elements")

    if bbox:
        print(f"\nBounding box:")
        print(f"  Min: {bbox[1]:.6f}, {bbox[0]:.6f}")
        print(f"  Max: {bbox[3]:.6f}, {bbox[2]:.6f}")
        lat_span = bbox[3] - bbox[1]
        lon_span = bbox[2] - bbox[0]
        print(f"  Span: {lat_span:.4f}° × {lon_span:.4f}°")

    if top_tags:
        print(f"\nTop tags:")
        for key, count in top_tags:
            print(f"  {key}: {count:,}")

    print(f"\n[{elapsed:.3f}s]")

    return 0
