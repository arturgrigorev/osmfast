"""Count command - quick element counting."""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the count subcommand parser."""
    parser = subparsers.add_parser(
        'count',
        help='Quick element and tag counting',
        description='Fast counting of elements and tag values'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument(
        '--filter', '-f',
        help='Count elements matching filter (e.g., amenity=*, highway=primary)'
    )
    parser.add_argument(
        '--by', '-b',
        help='Group counts by tag key (e.g., --by highway)'
    )
    parser.add_argument(
        '--type', '-t',
        choices=['nodes', 'ways', 'all'],
        default='all',
        help='Element type to count'
    )
    parser.add_argument(
        '--top', '-n',
        type=int,
        default=20,
        help='Number of results for --by (default: 20)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Only output the count number'
    )

    parser.set_defaults(func=run)
    return parser


def parse_filter(filter_str):
    """Parse filter string like 'amenity=restaurant' or 'highway=*'."""
    if '=' not in filter_str:
        return filter_str, '*'

    key, value = filter_str.split('=', 1)
    return key.strip(), value.strip()


def matches_filter(tags, key, value):
    """Check if tags match the filter."""
    if key not in tags:
        return False
    if value == '*':
        return True
    if ',' in value:
        return tags[key] in [v.strip() for v in value.split(',')]
    return tags[key] == value


def run(args):
    """Execute the count command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse the file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Prepare filter
    filter_key = None
    filter_value = None
    if args.filter:
        filter_key, filter_value = parse_filter(args.filter)

    # Count elements
    node_count = 0
    way_count = 0
    matched_nodes = 0
    matched_ways = 0
    by_counts = defaultdict(int)

    # Count nodes
    if args.type in ('nodes', 'all'):
        for node in nodes:
            node_count += 1

            if filter_key:
                if matches_filter(node.tags, filter_key, filter_value):
                    matched_nodes += 1
                    if args.by and args.by in node.tags:
                        by_counts[node.tags[args.by]] += 1
            elif args.by:
                if args.by in node.tags:
                    by_counts[node.tags[args.by]] += 1

    # Count ways
    if args.type in ('ways', 'all'):
        for way in ways:
            way_count += 1

            if filter_key:
                if matches_filter(way.tags, filter_key, filter_value):
                    matched_ways += 1
                    if args.by and args.by in way.tags:
                        by_counts[way.tags[args.by]] += 1
            elif args.by:
                if args.by in way.tags:
                    by_counts[way.tags[args.by]] += 1

    elapsed = time.time() - start_time

    # Determine total count
    if filter_key:
        total_matched = matched_nodes + matched_ways
    else:
        total_matched = None

    # Quiet mode - just the number
    if args.quiet:
        if total_matched is not None:
            print(total_matched)
        else:
            print(node_count + way_count)
        return 0

    # JSON output
    if args.json:
        output = {
            'file': str(input_path),
            'nodes': node_count if args.type in ('nodes', 'all') else None,
            'ways': way_count if args.type in ('ways', 'all') else None,
            'total': node_count + way_count,
            'time_seconds': round(elapsed, 3)
        }

        if filter_key:
            output['filter'] = f"{filter_key}={filter_value}"
            output['matched'] = {
                'nodes': matched_nodes if args.type in ('nodes', 'all') else None,
                'ways': matched_ways if args.type in ('ways', 'all') else None,
                'total': total_matched
            }

        if args.by:
            sorted_counts = sorted(by_counts.items(), key=lambda x: -x[1])[:args.top]
            output['by'] = args.by
            output['breakdown'] = [{'value': v, 'count': c} for v, c in sorted_counts]

        print(json.dumps(output, indent=2))
        return 0

    # Standard output
    print(f"\nElement Count: {args.input}")
    print("=" * 50)

    if args.type in ('nodes', 'all'):
        print(f"Nodes: {node_count:,}")
    if args.type in ('ways', 'all'):
        print(f"Ways: {way_count:,}")

    if args.type == 'all':
        print(f"Total: {node_count + way_count:,}")

    if filter_key:
        print(f"\nFilter: {filter_key}={filter_value}")
        if args.type in ('nodes', 'all'):
            print(f"Matching nodes: {matched_nodes:,}")
        if args.type in ('ways', 'all'):
            print(f"Matching ways: {matched_ways:,}")
        if args.type == 'all':
            print(f"Total matching: {total_matched:,}")

    if args.by:
        print(f"\nBreakdown by '{args.by}':")
        sorted_counts = sorted(by_counts.items(), key=lambda x: -x[1])[:args.top]

        if not sorted_counts:
            print(f"  (no elements with tag '{args.by}')")
        else:
            total_by = sum(c for _, c in sorted_counts)
            for value, count in sorted_counts:
                pct = 100 * count / total_by if total_by > 0 else 0
                # Truncate long values
                display_value = value[:35] + '...' if len(str(value)) > 35 else value
                print(f"  {display_value}: {count:,} ({pct:.1f}%)")

            if len(by_counts) > args.top:
                print(f"  ... and {len(by_counts) - args.top} more")

    print(f"\nTime: {elapsed:.3f}s")

    return 0
