"""Trees command - extract trees and tree rows."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the trees subcommand parser."""
    parser = subparsers.add_parser(
        'trees',
        help='Extract trees and tree rows',
        description='Extract individual trees and tree rows from OSM'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv'],
        default='geojson',
        help='Output format (default: geojson)'
    )
    parser.add_argument(
        '--type',
        choices=['tree', 'tree_row', 'wood', 'all'],
        default='all',
        help='Tree feature type'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only'
    )

    parser.set_defaults(func=run)
    return parser


def run(args):
    """Execute the trees command."""
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

    # Extract tree nodes
    for node in nodes:
        natural = node.tags.get('natural')
        if natural != 'tree':
            continue

        if args.type != 'all' and args.type != 'tree':
            continue

        features.append({
            'id': node.id,
            'type': 'tree',
            'species': node.tags.get('species'),
            'species_common': node.tags.get('species:common'),
            'genus': node.tags.get('genus'),
            'leaf_type': node.tags.get('leaf_type'),
            'leaf_cycle': node.tags.get('leaf_cycle'),
            'height': node.tags.get('height'),
            'circumference': node.tags.get('circumference'),
            'diameter_crown': node.tags.get('diameter_crown'),
            'denotation': node.tags.get('denotation'),
            'lat': float(node.lat),
            'lon': float(node.lon),
            'geometry_type': 'Point'
        })

    # Extract tree rows and woods
    for way in ways:
        natural = way.tags.get('natural')

        if natural == 'tree_row':
            if args.type != 'all' and args.type != 'tree_row':
                continue
            feature_type = 'tree_row'
        elif natural == 'wood':
            if args.type != 'all' and args.type != 'wood':
                continue
            feature_type = 'wood'
        else:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if len(coords) < 2:
            continue

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        features.append({
            'id': way.id,
            'type': feature_type,
            'species': way.tags.get('species'),
            'species_common': way.tags.get('species:common'),
            'genus': way.tags.get('genus'),
            'leaf_type': way.tags.get('leaf_type'),
            'leaf_cycle': way.tags.get('leaf_cycle'),
            'name': way.tags.get('name'),
            'lat': centroid_lat,
            'lon': centroid_lon,
            'geometry_type': 'LineString' if feature_type == 'tree_row' else 'Polygon',
            'coordinates': coords
        })

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nTrees and Vegetation: {args.input}")
        print("=" * 60)
        print(f"Total: {len(features)}")

        print("\nBy type:")
        by_type = {}
        for f in features:
            t = f['type']
            by_type[t] = by_type.get(t, 0) + 1
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        with_species = sum(1 for f in features if f.get('species'))
        with_genus = sum(1 for f in features if f.get('genus'))
        print(f"\nWith species: {with_species}")
        print(f"With genus: {with_genus}")

        # Top species
        species_counts = {}
        for f in features:
            s = f.get('species') or f.get('species_common')
            if s:
                species_counts[s] = species_counts.get(s, 0) + 1

        if species_counts:
            print("\nTop species:")
            for s, count in sorted(species_counts.items(), key=lambda x: -x[1])[:10]:
                print(f"  {s}: {count}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'geojson':
        geojson_features = []
        for f in features:
            if f['geometry_type'] == 'Point':
                geom = {"type": "Point", "coordinates": [f['lon'], f['lat']]}
            elif f['geometry_type'] == 'LineString':
                geom = {"type": "LineString", "coordinates": f.get('coordinates', [])}
            else:
                coords = f.get('coordinates', [])
                if coords and coords[0] != coords[-1]:
                    coords.append(coords[0])
                geom = {"type": "Polygon", "coordinates": [coords]}

            props = {k: v for k, v in f.items()
                     if k not in ['lat', 'lon', 'coordinates', 'geometry_type']}
            geojson_features.append({"type": "Feature", "geometry": geom, "properties": props})

        output = {"type": "FeatureCollection", "features": geojson_features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_str = json.dumps([{k: v for k, v in f.items() if k != 'coordinates'}
                                  for f in features], indent=2)

    elif args.format == 'csv':
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'type', 'species', 'genus', 'leaf_type', 'height', 'lat', 'lon'])
        for f in features:
            writer.writerow([f['id'], f['type'], f.get('species'), f.get('genus'),
                           f.get('leaf_type'), f.get('height'), f['lat'], f['lon']])
        output_str = buffer.getvalue()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(features)} tree features to: {args.output}")
    else:
        print(output_str)

    return 0
