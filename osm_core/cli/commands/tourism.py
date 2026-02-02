"""Tourism command - extract tourism features."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


TOURISM_TYPES = {
    'accommodation': frozenset({
        'hotel', 'motel', 'hostel', 'guest_house', 'apartment',
        'chalet', 'alpine_hut', 'wilderness_hut', 'camp_site',
        'caravan_site', 'camp_pitch'
    }),
    'attraction': frozenset({
        'attraction', 'theme_park', 'zoo', 'aquarium', 'museum',
        'gallery', 'artwork', 'viewpoint'
    }),
    'information': frozenset({
        'information', 'map', 'board', 'guidepost', 'office'
    }),
    'other': frozenset({
        'picnic_site', 'trail_riding_station', 'wine_cellar'
    })
}


def setup_parser(subparsers):
    """Setup the tourism subcommand parser."""
    parser = subparsers.add_parser(
        'tourism',
        help='Extract tourism features',
        description='Extract hotels, attractions, viewpoints, etc.'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--type', '-t',
        action='append',
        help='Filter by tourism type (e.g., hotel, viewpoint)'
    )
    parser.add_argument(
        '--category', '-c',
        choices=list(TOURISM_TYPES.keys()),
        action='append',
        help='Filter by category'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv'],
        default='geojson',
        help='Output format (default: geojson)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only'
    )

    parser.set_defaults(func=run)
    return parser


def run(args):
    """Execute the tourism command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    node_coords = {}
    for node in nodes:
        node_coords[node.id] = (float(node.lon), float(node.lat))

    allowed_types = set()
    if args.type:
        allowed_types.update(args.type)
    if args.category:
        for cat in args.category:
            if cat in TOURISM_TYPES:
                allowed_types.update(TOURISM_TYPES[cat])

    features = []

    for node in nodes:
        tourism_type = node.tags.get('tourism')
        if not tourism_type:
            continue
        if allowed_types and tourism_type not in allowed_types:
            continue

        features.append({
            'id': node.id,
            'osm_type': 'node',
            'tourism': tourism_type,
            'name': node.tags.get('name'),
            'stars': node.tags.get('stars'),
            'website': node.tags.get('website'),
            'phone': node.tags.get('phone') or node.tags.get('contact:phone'),
            'lon': float(node.lon),
            'lat': float(node.lat),
            'tags': node.tags
        })

    for way in ways:
        tourism_type = way.tags.get('tourism')
        if not tourism_type:
            continue
        if allowed_types and tourism_type not in allowed_types:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        features.append({
            'id': way.id,
            'osm_type': 'way',
            'tourism': tourism_type,
            'name': way.tags.get('name'),
            'stars': way.tags.get('stars'),
            'website': way.tags.get('website'),
            'phone': way.tags.get('phone') or way.tags.get('contact:phone'),
            'lon': centroid_lon,
            'lat': centroid_lat,
            'coords': coords,
            'tags': way.tags
        })

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nTourism Features: {args.input}")
        print("=" * 50)
        print(f"Total: {len(features)}")

        by_type = {}
        for f in features:
            t = f['tourism']
            by_type[t] = by_type.get(t, 0) + 1

        print(f"\nBy type:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        with_stars = [f for f in features if f.get('stars')]
        if with_stars:
            print(f"\nWith star rating: {len(with_stars)}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    if not args.output:
        print(f"Found {len(features)} tourism features")
        for f in features[:10]:
            name = f.get('name') or '(unnamed)'
            stars = f" ({f['stars']}*)" if f.get('stars') else ""
            print(f"  {f['tourism']}: {name}{stars}")
        if len(features) > 10:
            print(f"  ... and {len(features) - 10} more")
        return 0

    if args.format == 'geojson':
        geojson_features = []
        for f in features:
            geojson_features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [f['lon'], f['lat']]},
                "properties": {
                    "id": f['id'], "osm_type": f['osm_type'],
                    "tourism": f['tourism'], "name": f.get('name'),
                    "stars": f.get('stars'), "website": f.get('website'),
                    "phone": f.get('phone')
                }
            })
        output = {"type": "FeatureCollection", "features": geojson_features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_str = json.dumps([{k: v for k, v in f.items() if k not in ('coords', 'tags')} for f in features], indent=2)

    elif args.format == 'csv':
        import csv, io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'osm_type', 'tourism', 'name', 'stars', 'lat', 'lon', 'website'])
        for f in features:
            writer.writerow([f['id'], f['osm_type'], f['tourism'], f.get('name', ''),
                           f.get('stars', ''), f['lat'], f['lon'], f.get('website', '')])
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nTourism extraction complete:")
    print(f"  Features: {len(features)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
