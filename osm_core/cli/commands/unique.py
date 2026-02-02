"""Unique command - list unique values for a tag."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the unique subcommand parser."""
    parser = subparsers.add_parser(
        'unique',
        help='List unique values for a tag',
        description='Show all unique values for a specified tag'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument(
        '--key', '-k',
        required=True,
        help='Tag key to analyze (e.g., highway, amenity, surface)'
    )
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    parser.add_argument(
        '--count', '-c',
        action='store_true',
        help='Show counts for each value'
    )
    parser.add_argument(
        '--sort',
        choices=['alpha', 'count', 'none'],
        default='count',
        help='Sort order (default: count)'
    )
    parser.add_argument(
        '--limit', '-n',
        type=int,
        help='Limit to top N values'
    )
    parser.add_argument(
        '--type',
        choices=['nodes', 'ways', 'all'],
        default='all',
        help='Element type to analyze (default: all)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['text', 'json', 'csv'],
        default='text',
        help='Output format (default: text)'
    )
    parser.add_argument(
        '--min-count',
        type=int,
        default=1,
        help='Only show values with at least N occurrences'
    )

    parser.set_defaults(func=run)
    return parser


def run(args):
    """Execute the unique command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Count values
    value_counts = {}
    total_with_key = 0
    total_elements = 0

    if args.type in ('nodes', 'all'):
        for node in nodes:
            total_elements += 1
            value = node.tags.get(args.key)
            if value is not None:
                total_with_key += 1
                # Handle semicolon-separated values
                for v in str(value).split(';'):
                    v = v.strip()
                    if v:
                        value_counts[v] = value_counts.get(v, 0) + 1

    if args.type in ('ways', 'all'):
        for way in ways:
            total_elements += 1
            value = way.tags.get(args.key)
            if value is not None:
                total_with_key += 1
                for v in str(value).split(';'):
                    v = v.strip()
                    if v:
                        value_counts[v] = value_counts.get(v, 0) + 1

    # Filter by min count
    if args.min_count > 1:
        value_counts = {k: v for k, v in value_counts.items() if v >= args.min_count}

    # Sort
    if args.sort == 'count':
        sorted_values = sorted(value_counts.items(), key=lambda x: -x[1])
    elif args.sort == 'alpha':
        sorted_values = sorted(value_counts.items(), key=lambda x: x[0].lower())
    else:
        sorted_values = list(value_counts.items())

    # Limit
    if args.limit:
        sorted_values = sorted_values[:args.limit]

    elapsed = time.time() - start_time

    # Generate output
    if args.format == 'text':
        lines = []
        lines.append(f"Unique values for '{args.key}':")
        lines.append(f"=" * 50)
        lines.append(f"Total elements: {total_elements}")
        lines.append(f"With '{args.key}' tag: {total_with_key} ({100*total_with_key/max(total_elements,1):.1f}%)")
        lines.append(f"Unique values: {len(value_counts)}")
        lines.append("")

        if args.count:
            max_val_len = max((len(v) for v, _ in sorted_values), default=10)
            for value, count in sorted_values:
                pct = 100 * count / max(total_with_key, 1)
                lines.append(f"  {value:<{max_val_len}}  {count:>6}  ({pct:>5.1f}%)")
        else:
            for value, _ in sorted_values:
                lines.append(f"  {value}")

        lines.append(f"\n[{elapsed:.3f}s]")
        output_str = '\n'.join(lines)

    elif args.format == 'json':
        output = {
            'key': args.key,
            'total_elements': total_elements,
            'elements_with_key': total_with_key,
            'unique_count': len(value_counts),
            'values': [{'value': v, 'count': c} for v, c in sorted_values]
        }
        output_str = json.dumps(output, indent=2)

    elif args.format == 'csv':
        import csv, io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['value', 'count', 'percent'])
        for value, count in sorted_values:
            pct = 100 * count / max(total_with_key, 1)
            writer.writerow([value, count, f"{pct:.2f}"])
        output_str = buffer.getvalue()

    # Output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Unique values written to {args.output}")
    else:
        print(output_str)

    return 0
