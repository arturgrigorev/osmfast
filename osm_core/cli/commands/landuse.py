"""Landuse command - extract land use/cover."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser
from ...utils.geo_utils import calculate_polygon_area


LANDUSE_CATEGORIES = {
    'residential': ['residential', 'apartments', 'houses'],
    'commercial': ['commercial', 'retail', 'office'],
    'industrial': ['industrial', 'warehouse', 'port'],
    'agricultural': ['farmland', 'orchard', 'vineyard', 'meadow', 'farmyard'],
    'recreation': ['recreation_ground', 'park', 'playground', 'sports_centre'],
    'institutional': ['education', 'institutional', 'religious', 'cemetery'],
    'natural': ['forest', 'grass', 'wood', 'scrub', 'heath'],
    'infrastructure': ['railway', 'highway', 'parking'],
    'other': ['construction', 'brownfield', 'greenfield', 'landfill', 'quarry']
}


def get_landuse_category(value):
    """Get category for landuse value."""
    for cat, values in LANDUSE_CATEGORIES.items():
        if value in values:
            return cat
    return 'other'


def setup_parser(subparsers):
    """Setup the landuse subcommand parser."""
    parser = subparsers.add_parser(
        'landuse',
        help='Extract land use/cover data',
        description='Extract land use and land cover polygons'
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
        '--category',
        choices=list(LANDUSE_CATEGORIES.keys()) + ['all'],
        default='all',
        help='Filter by category'
    )
    parser.add_argument(
        '--min-area',
        type=float,
        default=0,
        help='Minimum area in square meters'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only'
    )

    parser.set_defaults(func=run)
    return parser


def run(args):
    """Execute the landuse command."""
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

    for way in ways:
        landuse = way.tags.get('landuse')
        if not landuse:
            continue

        category = get_landuse_category(landuse)
        if args.category != 'all' and category != args.category:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if len(coords) < 3:
            continue

        area = calculate_polygon_area(coords)
        if area < args.min_area:
            continue

        features.append({
            'id': way.id,
            'landuse': landuse,
            'category': category,
            'name': way.tags.get('name'),
            'area_sqm': round(area, 1),
            'area_ha': round(area / 10000, 2),
            'coordinates': coords
        })

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nLand Use Statistics: {args.input}")
        print("=" * 60)
        print(f"Total parcels: {len(features)}")
        total_area = sum(f['area_sqm'] for f in features)
        print(f"Total area: {total_area/1000000:.2f} km²")

        print("\nBy category:")
        by_cat = {}
        for f in features:
            c = f['category']
            if c not in by_cat:
                by_cat[c] = {'count': 0, 'area': 0}
            by_cat[c]['count'] += 1
            by_cat[c]['area'] += f['area_sqm']

        for cat, data in sorted(by_cat.items(), key=lambda x: -x[1]['area']):
            pct = 100 * data['area'] / total_area if total_area > 0 else 0
            print(f"  {cat}: {data['count']} parcels, {data['area']/10000:.1f} ha ({pct:.1f}%)")

        print("\nBy landuse type:")
        by_type = {}
        for f in features:
            t = f['landuse']
            if t not in by_type:
                by_type[t] = {'count': 0, 'area': 0}
            by_type[t]['count'] += 1
            by_type[t]['area'] += f['area_sqm']

        for t, data in sorted(by_type.items(), key=lambda x: -x[1]['area'])[:15]:
            print(f"  {t}: {data['count']} parcels, {data['area']/10000:.1f} ha")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'geojson':
        geojson_features = []
        for f in features:
            coords = f['coordinates']
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            geojson_features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {
                    "id": f['id'],
                    "landuse": f['landuse'],
                    "category": f['category'],
                    "name": f['name'],
                    "area_sqm": f['area_sqm'],
                    "area_ha": f['area_ha']
                }
            })
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
        writer.writerow(['id', 'landuse', 'category', 'name', 'area_sqm', 'area_ha'])
        for f in features:
            writer.writerow([f['id'], f['landuse'], f['category'], f['name'],
                           f['area_sqm'], f['area_ha']])
        output_str = buffer.getvalue()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(features)} landuse parcels to: {args.output}")
    else:
        print(output_str)

    return 0
