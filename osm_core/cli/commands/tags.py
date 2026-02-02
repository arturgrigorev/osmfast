"""Tags command - explore tag usage in OSM files."""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the tags subcommand parser."""
    parser = subparsers.add_parser(
        'tags',
        help='Explore tag usage in OSM files',
        description='Analyze and explore tag keys and values'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument(
        '-k', '--key',
        help='Show values for specific tag key'
    )
    parser.add_argument(
        '-v', '--value',
        help='Show keys that have this value'
    )
    parser.add_argument(
        '--top', '-n',
        type=int,
        default=20,
        help='Number of results to show (default: 20)'
    )
    parser.add_argument(
        '--type', '-t',
        choices=['nodes', 'ways', 'all'],
        default='all',
        help='Element type to analyze'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )
    parser.add_argument(
        '--keys-only',
        action='store_true',
        help='Only show tag keys (no values)'
    )
    parser.add_argument(
        '--rare',
        action='store_true',
        help='Show rarely used tags (ascending order)'
    )
    parser.add_argument(
        '--pattern',
        help='Filter keys by pattern (e.g., "addr:*")'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output file'
    )

    parser.set_defaults(func=run)
    return parser


def matches_pattern(key, pattern):
    """Check if key matches pattern (supports * wildcard)."""
    if '*' not in pattern:
        return key == pattern

    if pattern.endswith('*'):
        return key.startswith(pattern[:-1])
    elif pattern.startswith('*'):
        return key.endswith(pattern[1:])
    else:
        parts = pattern.split('*')
        return key.startswith(parts[0]) and key.endswith(parts[1])


def run(args):
    """Execute the tags command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse the file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Collect tag statistics
    key_counts = defaultdict(int)
    value_counts = defaultdict(lambda: defaultdict(int))
    key_by_value = defaultdict(lambda: defaultdict(int))

    elements = []
    if args.type in ('nodes', 'all'):
        elements.extend(nodes)
    if args.type in ('ways', 'all'):
        elements.extend(ways)

    for element in elements:
        for key, value in element.tags.items():
            # Apply pattern filter
            if args.pattern and not matches_pattern(key, args.pattern):
                continue

            key_counts[key] += 1
            value_counts[key][value] += 1
            key_by_value[value][key] += 1

    elapsed = time.time() - start_time

    # Determine sort order
    reverse = not args.rare

    # Mode: Show values for specific key
    if args.key:
        if args.key not in value_counts:
            print(f"Tag key '{args.key}' not found in file.", file=sys.stderr)
            return 1

        values = value_counts[args.key]
        sorted_values = sorted(values.items(), key=lambda x: x[1], reverse=reverse)[:args.top]

        if args.json:
            output = {
                'key': args.key,
                'total_count': key_counts[args.key],
                'unique_values': len(values),
                'values': [{'value': v, 'count': c} for v, c in sorted_values]
            }
            output_str = json.dumps(output, indent=2)
        else:
            lines = []
            lines.append(f"\nValues for tag '{args.key}':")
            lines.append("=" * 60)
            lines.append(f"Total occurrences: {key_counts[args.key]}")
            lines.append(f"Unique values: {len(values)}")
            lines.append("")

            for value, count in sorted_values:
                pct = 100 * count / key_counts[args.key]
                # Truncate long values
                display_value = value[:40] + '...' if len(value) > 40 else value
                lines.append(f"  {display_value}: {count} ({pct:.1f}%)")

            lines.append(f"\nProcessing time: {elapsed:.3f}s")
            output_str = '\n'.join(lines)

    # Mode: Show keys that have specific value
    elif args.value:
        if args.value not in key_by_value:
            print(f"Value '{args.value}' not found in file.", file=sys.stderr)
            return 1

        keys = key_by_value[args.value]
        sorted_keys = sorted(keys.items(), key=lambda x: x[1], reverse=reverse)[:args.top]

        if args.json:
            output = {
                'value': args.value,
                'keys': [{'key': k, 'count': c} for k, c in sorted_keys]
            }
            output_str = json.dumps(output, indent=2)
        else:
            lines = []
            lines.append(f"\nTag keys with value '{args.value}':")
            lines.append("=" * 60)

            for key, count in sorted_keys:
                lines.append(f"  {key}: {count}")

            lines.append(f"\nProcessing time: {elapsed:.3f}s")
            output_str = '\n'.join(lines)

    # Mode: Show all tag keys
    else:
        sorted_keys = sorted(key_counts.items(), key=lambda x: x[1], reverse=reverse)[:args.top]

        if args.json:
            output = {
                'total_unique_keys': len(key_counts),
                'total_tags': sum(key_counts.values()),
                'keys': [
                    {
                        'key': k,
                        'count': c,
                        'unique_values': len(value_counts[k])
                    }
                    for k, c in sorted_keys
                ]
            }
            output_str = json.dumps(output, indent=2)
        else:
            lines = []
            lines.append(f"\nTag Statistics: {args.input}")
            lines.append("=" * 60)
            lines.append(f"Unique tag keys: {len(key_counts)}")
            lines.append(f"Total tag instances: {sum(key_counts.values())}")

            if args.pattern:
                lines.append(f"Pattern filter: {args.pattern}")

            order = "least common" if args.rare else "most common"
            lines.append(f"\n{order.title()} tag keys:")

            for key, count in sorted_keys:
                unique_vals = len(value_counts[key])
                if args.keys_only:
                    lines.append(f"  {key}: {count}")
                else:
                    # Show sample values
                    sample_values = sorted(
                        value_counts[key].items(),
                        key=lambda x: x[1],
                        reverse=True
                    )[:3]
                    sample_str = ', '.join(f"{v}" for v, _ in sample_values)
                    if len(value_counts[key]) > 3:
                        sample_str += ', ...'

                    lines.append(f"  {key}: {count} ({unique_vals} unique)")
                    lines.append(f"      values: {sample_str[:60]}")

            lines.append(f"\nProcessing time: {elapsed:.3f}s")
            output_str = '\n'.join(lines)

    # Output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved to: {args.output}")
    else:
        print(output_str)

    return 0
