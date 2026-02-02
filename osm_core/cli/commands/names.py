"""Names command - extract all named features."""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the names subcommand parser."""
    parser = subparsers.add_parser(
        'names',
        help='Extract all named features',
        description='Extract all features with names (for geocoding, search indexes)'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '-f', '--format',
        choices=['csv', 'json', 'geojson'],
        default='csv',
        help='Output format (default: csv)'
    )
    parser.add_argument(
        '--include-alt-names',
        action='store_true',
        help='Include alternative names (name:en, old_name, etc.)'
    )
    parser.add_argument(
        '--language',
        help='Filter by language code (e.g., en, de, fr)'
    )
    parser.add_argument(
        '--min-importance',
        type=int,
        default=0,
        help='Minimum importance score (0-10)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only'
    )

    parser.set_defaults(func=run)
    return parser


def get_feature_type(tags):
    """Determine feature type for importance ranking."""
    # Order matters - first match wins
    type_map = [
        ('place', ['city', 'town', 'village', 'suburb', 'hamlet', 'neighbourhood']),
        ('highway', ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'residential']),
        ('amenity', None),
        ('shop', None),
        ('tourism', None),
        ('building', ['yes', 'residential', 'commercial']),
        ('natural', None),
        ('landuse', None),
    ]

    for key, values in type_map:
        if key in tags:
            if values is None or tags[key] in values:
                return key, tags[key]

    return 'other', 'unknown'


def calculate_importance(tags, feature_key, feature_value):
    """Calculate importance score (0-10)."""
    # Base importance by feature type
    importance_map = {
        ('place', 'city'): 10,
        ('place', 'town'): 9,
        ('place', 'village'): 7,
        ('place', 'suburb'): 6,
        ('highway', 'motorway'): 8,
        ('highway', 'primary'): 6,
        ('railway', 'station'): 7,
        ('amenity', 'hospital'): 6,
        ('amenity', 'university'): 6,
        ('tourism', 'attraction'): 5,
    }

    base = importance_map.get((feature_key, feature_value), 3)

    # Boost for Wikipedia/Wikidata
    if 'wikipedia' in tags or 'wikidata' in tags:
        base = min(10, base + 1)

    return base


def run(args):
    """Execute the names command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    node_coords = {}
    for node in nodes:
        node_coords[node.id] = [float(node.lon), float(node.lat)]

    features = []

    # Process nodes
    for node in nodes:
        name = node.tags.get('name')
        if not name:
            continue

        feature_key, feature_value = get_feature_type(node.tags)
        importance = calculate_importance(node.tags, feature_key, feature_value)

        if importance < args.min_importance:
            continue

        entry = {
            'id': node.id,
            'type': 'node',
            'name': name,
            'feature_type': feature_key,
            'feature_value': feature_value,
            'importance': importance,
            'lat': float(node.lat),
            'lon': float(node.lon)
        }

        if args.include_alt_names:
            alt_names = []
            for k, v in node.tags.items():
                if k.startswith('name:') or k in ('old_name', 'alt_name', 'short_name'):
                    if args.language:
                        if k == f'name:{args.language}':
                            entry['name_local'] = v
                    else:
                        alt_names.append(v)
            if alt_names:
                entry['alt_names'] = '|'.join(alt_names)

        features.append(entry)

    # Process ways
    for way in ways:
        name = way.tags.get('name')
        if not name:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        feature_key, feature_value = get_feature_type(way.tags)
        importance = calculate_importance(way.tags, feature_key, feature_value)

        if importance < args.min_importance:
            continue

        entry = {
            'id': way.id,
            'type': 'way',
            'name': name,
            'feature_type': feature_key,
            'feature_value': feature_value,
            'importance': importance,
            'lat': centroid_lat,
            'lon': centroid_lon
        }

        if args.include_alt_names:
            alt_names = []
            for k, v in way.tags.items():
                if k.startswith('name:') or k in ('old_name', 'alt_name', 'short_name'):
                    alt_names.append(v)
            if alt_names:
                entry['alt_names'] = '|'.join(alt_names)

        features.append(entry)

    # Sort by importance
    features.sort(key=lambda x: -x['importance'])

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nNamed Features: {args.input}")
        print("=" * 60)
        print(f"Total: {len(features)}")

        print("\nBy feature type:")
        by_type = {}
        for f in features:
            t = f['feature_type']
            by_type[t] = by_type.get(t, 0) + 1
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        print("\nBy importance:")
        by_imp = {}
        for f in features:
            i = f['importance']
            by_imp[i] = by_imp.get(i, 0) + 1
        for i in sorted(by_imp.keys(), reverse=True):
            print(f"  {i}: {by_imp[i]}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'csv':
        import io
        buffer = io.StringIO()
        fieldnames = ['id', 'type', 'name', 'feature_type', 'feature_value',
                      'importance', 'lat', 'lon']
        if args.include_alt_names:
            fieldnames.append('alt_names')
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(features)
        output_str = buffer.getvalue()

    elif args.format == 'json':
        output_str = json.dumps(features, indent=2)

    elif args.format == 'geojson':
        geojson_features = []
        for f in features:
            geojson_features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [f['lon'], f['lat']]},
                "properties": {k: v for k, v in f.items() if k not in ['lat', 'lon']}
            })
        output = {"type": "FeatureCollection", "features": geojson_features}
        output_str = json.dumps(output, indent=2)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(features)} named features to: {args.output}")
    else:
        print(output_str)

    return 0
