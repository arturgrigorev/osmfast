"""Shop command - extract shops with categories."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


# Shop categories
SHOP_CATEGORIES = {
    'food': frozenset({
        'supermarket', 'convenience', 'grocery', 'bakery', 'butcher',
        'greengrocer', 'deli', 'cheese', 'seafood', 'alcohol', 'wine',
        'beverages', 'coffee', 'tea', 'confectionery', 'chocolate', 'pastry'
    }),
    'clothing': frozenset({
        'clothes', 'fashion', 'boutique', 'shoes', 'jewelry', 'watches',
        'bag', 'leather', 'tailor', 'fabric'
    }),
    'electronics': frozenset({
        'electronics', 'computer', 'mobile_phone', 'hifi', 'appliance',
        'electrical', 'camera'
    }),
    'health': frozenset({
        'pharmacy', 'chemist', 'medical_supply', 'optician', 'hearing_aids',
        'herbalist', 'nutrition_supplements'
    }),
    'home': frozenset({
        'furniture', 'kitchen', 'bed', 'bathroom_furnishing', 'carpet',
        'curtain', 'interior_decoration', 'houseware', 'antiques'
    }),
    'diy': frozenset({
        'doityourself', 'hardware', 'paint', 'glaziery', 'garden_centre',
        'trade', 'building_materials'
    }),
    'sports': frozenset({
        'sports', 'outdoor', 'bicycle', 'fishing', 'hunting', 'golf',
        'scuba_diving', 'swimming_pool'
    }),
    'beauty': frozenset({
        'beauty', 'cosmetics', 'hairdresser', 'perfumery', 'tattoo'
    }),
    'car': frozenset({
        'car', 'car_parts', 'car_repair', 'tyres', 'motorcycle'
    }),
    'other': frozenset({
        'gift', 'toys', 'games', 'books', 'newsagent', 'stationery',
        'pet', 'florist', 'variety_store', 'second_hand', 'charity', 'kiosk'
    })
}


def setup_parser(subparsers):
    """Setup the shop subcommand parser."""
    parser = subparsers.add_parser(
        'shop',
        help='Extract shops with categories',
        description='Extract shops from OSM data'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--type', '-t',
        action='append',
        help='Filter by shop type (e.g., supermarket, bakery)'
    )
    parser.add_argument(
        '--category', '-c',
        choices=list(SHOP_CATEGORIES.keys()),
        action='append',
        help='Filter by category (food, clothing, electronics, etc.)'
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
    parser.add_argument(
        '--list-types',
        action='store_true',
        help='List all shop types found'
    )

    parser.set_defaults(func=run)
    return parser


def run(args):
    """Execute the shop command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse the file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Build node coordinates
    node_coords = {}
    for node in nodes:
        node_coords[node.id] = (float(node.lon), float(node.lat))

    # Build filter set
    allowed_types = set()
    if args.type:
        allowed_types.update(args.type)
    if args.category:
        for cat in args.category:
            if cat in SHOP_CATEGORIES:
                allowed_types.update(SHOP_CATEGORIES[cat])

    # Collect shops
    shops = []
    type_counts = {}

    # Process nodes
    for node in nodes:
        shop_type = node.tags.get('shop')
        if not shop_type:
            continue

        type_counts[shop_type] = type_counts.get(shop_type, 0) + 1

        if allowed_types and shop_type not in allowed_types:
            continue

        shops.append({
            'id': node.id,
            'type': 'node',
            'shop': shop_type,
            'name': node.tags.get('name'),
            'brand': node.tags.get('brand'),
            'opening_hours': node.tags.get('opening_hours'),
            'lon': float(node.lon),
            'lat': float(node.lat),
            'tags': node.tags
        })

    # Process ways
    for way in ways:
        shop_type = way.tags.get('shop')
        if not shop_type:
            continue

        type_counts[shop_type] = type_counts.get(shop_type, 0) + 1

        if allowed_types and shop_type not in allowed_types:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        shops.append({
            'id': way.id,
            'type': 'way',
            'shop': shop_type,
            'name': way.tags.get('name'),
            'brand': way.tags.get('brand'),
            'opening_hours': way.tags.get('opening_hours'),
            'lon': centroid_lon,
            'lat': centroid_lat,
            'tags': way.tags
        })

    elapsed = time.time() - start_time

    # List types mode
    if args.list_types:
        print(f"\nShop types in {args.input}:")
        print("=" * 50)
        for shop_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"  {shop_type}: {count}")
        print(f"\nTotal types: {len(type_counts)}")
        return 0

    # Stats mode
    if args.stats:
        print(f"\nShop Statistics: {args.input}")
        print("=" * 50)
        print(f"Total shops: {len(shops)}")

        by_type = {}
        for s in shops:
            t = s['shop']
            by_type[t] = by_type.get(t, 0) + 1

        print(f"\nTop shop types:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1])[:15]:
            print(f"  {t}: {count}")

        # Brands
        brands = {}
        for s in shops:
            brand = s.get('brand')
            if brand:
                brands[brand] = brands.get(brand, 0) + 1

        if brands:
            print(f"\nTop brands:")
            for brand, count in sorted(brands.items(), key=lambda x: -x[1])[:10]:
                print(f"  {brand}: {count}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # No output specified
    if not args.output:
        print(f"Found {len(shops)} shops")
        for s in shops[:10]:
            name = s.get('name') or s.get('brand') or '(unnamed)'
            print(f"  {s['shop']}: {name}")
        if len(shops) > 10:
            print(f"  ... and {len(shops) - 10} more")
        return 0

    # Generate output
    if args.format == 'geojson':
        features = []
        for s in shops:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [s['lon'], s['lat']]
                },
                "properties": {
                    "id": s['id'],
                    "osm_type": s['type'],
                    "shop": s['shop'],
                    "name": s.get('name'),
                    "brand": s.get('brand'),
                    "opening_hours": s.get('opening_hours')
                }
            })
        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_str = json.dumps(shops, indent=2)

    elif args.format == 'csv':
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'osm_type', 'shop', 'name', 'brand', 'lat', 'lon', 'opening_hours'])
        for s in shops:
            writer.writerow([s['id'], s['type'], s['shop'], s.get('name', ''),
                           s.get('brand', ''), s['lat'], s['lon'], s.get('opening_hours', '')])
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nShop extraction complete:")
    print(f"  Shops: {len(shops)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
