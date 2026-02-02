"""Food command - detailed food and drink extraction."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


FOOD_AMENITIES = frozenset({
    'restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'biergarten',
    'food_court', 'ice_cream', 'nightclub'
})

CUISINE_CATEGORIES = {
    'asian': frozenset({
        'asian', 'chinese', 'japanese', 'korean', 'thai', 'vietnamese',
        'indian', 'indonesian', 'malaysian', 'filipino', 'sushi', 'ramen',
        'noodle', 'curry', 'dim_sum'
    }),
    'european': frozenset({
        'italian', 'french', 'german', 'spanish', 'greek', 'portuguese',
        'polish', 'russian', 'british', 'irish', 'mediterranean', 'pizza',
        'pasta'
    }),
    'american': frozenset({
        'american', 'mexican', 'tex-mex', 'brazilian', 'peruvian',
        'burger', 'steak', 'bbq', 'barbecue', 'southern'
    }),
    'middle_eastern': frozenset({
        'middle_eastern', 'turkish', 'lebanese', 'persian', 'arabic',
        'kebab', 'falafel', 'shawarma'
    }),
    'fast_food': frozenset({
        'burger', 'pizza', 'chicken', 'sandwich', 'fish_and_chips',
        'hot_dog', 'donut', 'bagel'
    }),
    'other': frozenset({
        'international', 'regional', 'seafood', 'vegetarian', 'vegan',
        'organic', 'breakfast', 'brunch', 'coffee_shop', 'cake', 'dessert'
    })
}


def setup_parser(subparsers):
    """Setup the food subcommand parser."""
    parser = subparsers.add_parser(
        'food',
        help='Extract food and drink places',
        description='Extract restaurants, cafes, bars with cuisine details'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--type', '-t',
        action='append',
        help='Filter by type (restaurant, cafe, bar, etc.)'
    )
    parser.add_argument(
        '--cuisine', '-c',
        action='append',
        help='Filter by cuisine (italian, chinese, etc.)'
    )
    parser.add_argument(
        '--cuisine-category',
        choices=list(CUISINE_CATEGORIES.keys()),
        action='append',
        help='Filter by cuisine category'
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
    """Execute the food command."""
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

    allowed_types = set(args.type) if args.type else None
    allowed_cuisines = set()
    if args.cuisine:
        allowed_cuisines.update(c.lower() for c in args.cuisine)
    if args.cuisine_category:
        for cat in args.cuisine_category:
            if cat in CUISINE_CATEGORIES:
                allowed_cuisines.update(CUISINE_CATEGORIES[cat])

    features = []

    def process_element(elem, lon, lat, coords=None):
        amenity = elem.tags.get('amenity')
        if amenity not in FOOD_AMENITIES:
            return

        if allowed_types and amenity not in allowed_types:
            return

        cuisine = elem.tags.get('cuisine', '')
        cuisines = [c.strip().lower() for c in cuisine.split(';')] if cuisine else []

        if allowed_cuisines:
            if not any(c in allowed_cuisines for c in cuisines):
                return

        features.append({
            'id': elem.id,
            'osm_type': 'node' if coords is None else 'way',
            'amenity': amenity,
            'name': elem.tags.get('name'),
            'cuisine': cuisine,
            'opening_hours': elem.tags.get('opening_hours'),
            'phone': elem.tags.get('phone') or elem.tags.get('contact:phone'),
            'website': elem.tags.get('website'),
            'wheelchair': elem.tags.get('wheelchair'),
            'outdoor_seating': elem.tags.get('outdoor_seating'),
            'takeaway': elem.tags.get('takeaway'),
            'delivery': elem.tags.get('delivery'),
            'lon': lon,
            'lat': lat,
            'tags': elem.tags
        })

    for node in nodes:
        process_element(node, float(node.lon), float(node.lat))

    for way in ways:
        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue
        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)
        process_element(way, centroid_lon, centroid_lat, coords)

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nFood & Drink: {args.input}")
        print("=" * 50)
        print(f"Total: {len(features)}")

        by_type = {}
        for f in features:
            t = f['amenity']
            by_type[t] = by_type.get(t, 0) + 1

        print(f"\nBy type:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        cuisines = {}
        for f in features:
            for c in f.get('cuisine', '').split(';'):
                c = c.strip()
                if c:
                    cuisines[c] = cuisines.get(c, 0) + 1

        if cuisines:
            print(f"\nTop cuisines:")
            for c, count in sorted(cuisines.items(), key=lambda x: -x[1])[:15]:
                print(f"  {c}: {count}")

        takeaway = sum(1 for f in features if f.get('takeaway') == 'yes')
        delivery = sum(1 for f in features if f.get('delivery') == 'yes')
        outdoor = sum(1 for f in features if f.get('outdoor_seating') == 'yes')

        print(f"\nServices:")
        print(f"  Takeaway: {takeaway}")
        print(f"  Delivery: {delivery}")
        print(f"  Outdoor seating: {outdoor}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    if not args.output:
        print(f"Found {len(features)} food/drink places")
        for f in features[:10]:
            name = f.get('name') or '(unnamed)'
            cuisine = f" ({f['cuisine']})" if f.get('cuisine') else ""
            print(f"  {f['amenity']}: {name}{cuisine}")
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
                    "amenity": f['amenity'], "name": f.get('name'),
                    "cuisine": f.get('cuisine'), "opening_hours": f.get('opening_hours'),
                    "phone": f.get('phone'), "wheelchair": f.get('wheelchair'),
                    "takeaway": f.get('takeaway'), "delivery": f.get('delivery')
                }
            })
        output = {"type": "FeatureCollection", "features": geojson_features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_str = json.dumps([{k: v for k, v in f.items() if k != 'tags'} for f in features], indent=2)

    elif args.format == 'csv':
        import csv, io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'osm_type', 'amenity', 'name', 'cuisine', 'lat', 'lon', 'opening_hours', 'phone'])
        for f in features:
            writer.writerow([f['id'], f['osm_type'], f['amenity'], f.get('name', ''),
                           f.get('cuisine', ''), f['lat'], f['lon'],
                           f.get('opening_hours', ''), f.get('phone', '')])
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nFood extraction complete:")
    print(f"  Places: {len(features)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
