"""Search command - find features by name."""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the search subcommand parser."""
    parser = subparsers.add_parser(
        'search',
        help='Search for features by name',
        description='Find OSM features by name or tag values'
    )

    parser.add_argument('query', help='Search query (name or pattern)')
    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file (GeoJSON)')
    parser.add_argument(
        '--regex', '-r',
        action='store_true',
        help='Treat query as regex pattern'
    )
    parser.add_argument(
        '--case-sensitive', '-c',
        action='store_true',
        help='Case-sensitive search (default: case-insensitive)'
    )
    parser.add_argument(
        '--type', '-t',
        choices=['nodes', 'ways', 'all'],
        default='all',
        help='Element type to search'
    )
    parser.add_argument(
        '--tag', '-k',
        default='name',
        help='Tag key to search (default: name)'
    )
    parser.add_argument(
        '--limit', '-n',
        type=int,
        default=100,
        help='Maximum results (default: 100, 0 for unlimited)'
    )
    parser.add_argument(
        '--count',
        action='store_true',
        help='Only show count of matches'
    )

    parser.set_defaults(func=run)
    return parser


def matches_query(value, query, is_regex=False, case_sensitive=False):
    """Check if value matches query."""
    if value is None:
        return False

    value = str(value)

    if not case_sensitive:
        value = value.lower()
        if not is_regex:
            query = query.lower()

    if is_regex:
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            return bool(re.search(query, value, flags))
        except re.error:
            return False
    else:
        return query in value


def run(args):
    """Execute the search command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse the file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Build node coordinate lookup for ways
    node_coords = {}
    for node in nodes:
        node_coords[node.id] = [float(node.lon), float(node.lat)]

    results = []
    tag_key = args.tag
    limit = args.limit if args.limit > 0 else float('inf')

    # Search nodes
    if args.type in ('nodes', 'all'):
        for node in nodes:
            if len(results) >= limit:
                break

            value = node.tags.get(tag_key)
            if matches_query(value, args.query, args.regex, args.case_sensitive):
                results.append({
                    'type': 'node',
                    'id': node.id,
                    'name': node.tags.get('name'),
                    'matched_value': value,
                    'matched_tag': tag_key,
                    'lat': float(node.lat),
                    'lon': float(node.lon),
                    'tags': node.tags
                })

    # Search ways
    if args.type in ('ways', 'all'):
        for way in ways:
            if len(results) >= limit:
                break

            value = way.tags.get(tag_key)
            if matches_query(value, args.query, args.regex, args.case_sensitive):
                # Get centroid
                coords = []
                for ref in way.node_refs:
                    if ref in node_coords:
                        coords.append(node_coords[ref])

                if coords:
                    centroid_lon = sum(c[0] for c in coords) / len(coords)
                    centroid_lat = sum(c[1] for c in coords) / len(coords)
                else:
                    centroid_lon = centroid_lat = None

                results.append({
                    'type': 'way',
                    'id': way.id,
                    'name': way.tags.get('name'),
                    'matched_value': value,
                    'matched_tag': tag_key,
                    'lat': centroid_lat,
                    'lon': centroid_lon,
                    'coordinates': coords,
                    'tags': way.tags
                })

    elapsed = time.time() - start_time

    # Count only mode
    if args.count:
        print(f"Found {len(results)} matches")
        return 0

    # Display results
    if not args.output:
        print(f"\nSearch results for '{args.query}' in {tag_key}:")
        print("=" * 60)

        if not results:
            print("No matches found.")
        else:
            for i, r in enumerate(results, 1):
                name = r['name'] or '(unnamed)'
                element_type = r['type']
                tags_preview = []

                # Show key identifying tags
                for key in ['amenity', 'highway', 'building', 'shop', 'tourism']:
                    if key in r['tags']:
                        tags_preview.append(f"{key}={r['tags'][key]}")

                tags_str = ', '.join(tags_preview[:3]) if tags_preview else ''

                print(f"\n{i}. {name}")
                print(f"   Type: {element_type} (id: {r['id']})")
                if tags_str:
                    print(f"   Tags: {tags_str}")
                if r['lat'] and r['lon']:
                    print(f"   Location: {r['lat']:.6f}, {r['lon']:.6f}")
                if tag_key != 'name' and r['matched_value']:
                    print(f"   {tag_key}: {r['matched_value']}")

        print(f"\n{'=' * 60}")
        print(f"Found {len(results)} matches in {elapsed:.3f}s")

        if len(results) >= limit and limit != float('inf'):
            print(f"(showing first {limit} results, use --limit 0 for all)")

    # GeoJSON output
    if args.output:
        output = {
            "type": "FeatureCollection",
            "features": []
        }

        for r in results:
            if r['type'] == 'node':
                geometry = {
                    "type": "Point",
                    "coordinates": [r['lon'], r['lat']]
                }
            else:
                if r['coordinates']:
                    if len(r['coordinates']) > 2 and r['coordinates'][0] == r['coordinates'][-1]:
                        geometry = {
                            "type": "Polygon",
                            "coordinates": [r['coordinates']]
                        }
                    else:
                        geometry = {
                            "type": "LineString",
                            "coordinates": r['coordinates']
                        }
                else:
                    continue

            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "id": r['id'],
                    "element_type": r['type'],
                    "name": r['name'],
                    "matched_tag": r['matched_tag'],
                    "matched_value": r['matched_value'],
                    **{k: v for k, v in r['tags'].items() if k != 'name'}
                }
            }
            output["features"].append(feature)

        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        print(f"Saved {len(results)} results to: {args.output}")

    return 0
