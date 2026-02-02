"""POI command - extract points of interest with categories."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser
from ...utils.geo_utils import calculate_polygon_area


# POI category definitions
POI_CATEGORIES = {
    'food': {
        'amenity': frozenset({
            'restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'food_court',
            'ice_cream', 'biergarten', 'bakery'
        }),
        'shop': frozenset({
            'bakery', 'butcher', 'cheese', 'chocolate', 'coffee', 'confectionery',
            'convenience', 'deli', 'farm', 'frozen_food', 'greengrocer',
            'health_food', 'organic', 'pasta', 'pastry', 'seafood',
            'spices', 'tea', 'wine', 'supermarket', 'grocery'
        })
    },
    'shop': {
        'shop': frozenset({
            'supermarket', 'convenience', 'clothes', 'shoes', 'electronics',
            'hardware', 'furniture', 'department_store', 'mall', 'books',
            'toys', 'sports', 'jewelry', 'optician', 'beauty', 'cosmetics',
            'gift', 'florist', 'mobile_phone', 'computer', 'bicycle',
            'car', 'car_parts', 'tyres', 'doityourself', 'garden_centre'
        })
    },
    'health': {
        'amenity': frozenset({
            'hospital', 'clinic', 'doctors', 'dentist', 'pharmacy',
            'veterinary', 'nursing_home', 'health_centre'
        }),
        'healthcare': frozenset({
            'hospital', 'clinic', 'doctor', 'dentist', 'pharmacy',
            'physiotherapist', 'optometrist', 'laboratory'
        })
    },
    'education': {
        'amenity': frozenset({
            'school', 'university', 'college', 'kindergarten', 'library',
            'language_school', 'music_school', 'driving_school', 'childcare'
        })
    },
    'transport': {
        'amenity': frozenset({
            'bus_station', 'ferry_terminal', 'taxi', 'car_rental',
            'bicycle_rental', 'car_sharing', 'fuel', 'charging_station',
            'parking'
        }),
        'highway': frozenset({
            'bus_stop'
        }),
        'railway': frozenset({
            'station', 'halt', 'tram_stop', 'subway_entrance'
        }),
        'aeroway': frozenset({
            'aerodrome', 'terminal', 'helipad'
        })
    },
    'tourism': {
        'tourism': frozenset({
            'hotel', 'motel', 'hostel', 'guest_house', 'apartment',
            'museum', 'gallery', 'attraction', 'viewpoint', 'zoo',
            'theme_park', 'aquarium', 'artwork', 'information', 'camp_site'
        }),
        'amenity': frozenset({
            'theatre', 'cinema', 'arts_centre', 'nightclub', 'casino',
            'community_centre'
        }),
        'leisure': frozenset({
            'park', 'playground', 'stadium', 'sports_centre', 'swimming_pool',
            'golf_course', 'ice_rink', 'beach_resort'
        })
    },
    'finance': {
        'amenity': frozenset({
            'bank', 'atm', 'bureau_de_change', 'money_transfer'
        })
    },
    'service': {
        'amenity': frozenset({
            'post_office', 'police', 'fire_station', 'courthouse',
            'townhall', 'embassy', 'community_centre', 'social_facility',
            'recycling', 'waste_disposal', 'toilets', 'shower'
        }),
        'office': frozenset({
            'government', 'lawyer', 'notary', 'estate_agent', 'insurance',
            'employment_agency', 'travel_agent'
        })
    },
    'worship': {
        'amenity': frozenset({
            'place_of_worship'
        })
    }
}


def setup_parser(subparsers):
    """Setup the poi subcommand parser."""
    parser = subparsers.add_parser(
        'poi',
        help='Extract points of interest with categories',
        description='Extract POIs with predefined or custom categories'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv'],
        default='geojson',
        help='Output format (default: geojson)'
    )
    parser.add_argument(
        '-c', '--category',
        choices=list(POI_CATEGORIES.keys()) + ['all'],
        default='all',
        help='POI category to extract'
    )
    parser.add_argument(
        '--list-categories',
        action='store_true',
        help='List available categories and exit'
    )
    parser.add_argument(
        '--include-ways',
        action='store_true',
        help='Include POIs from ways (use centroid)'
    )
    parser.add_argument(
        '--named-only',
        action='store_true',
        help='Only POIs with names'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only'
    )

    parser.set_defaults(func=run)
    return parser


def get_poi_category(tags):
    """Determine POI category from tags."""
    for category, tag_defs in POI_CATEGORIES.items():
        for tag_key, valid_values in tag_defs.items():
            if tag_key in tags and tags[tag_key] in valid_values:
                return category, tag_key, tags[tag_key]
    return None, None, None


def is_poi(tags):
    """Check if element is a POI."""
    category, _, _ = get_poi_category(tags)
    return category is not None


def extract_poi_data(element, element_type, lat=None, lon=None, coords=None):
    """Extract POI data from an element."""
    tags = element.tags
    category, tag_key, tag_value = get_poi_category(tags)

    if category is None:
        return None

    # Get coordinates
    if element_type == 'node':
        poi_lat = float(element.lat)
        poi_lon = float(element.lon)
    elif coords:
        # Use centroid for ways
        poi_lon = sum(c[0] for c in coords) / len(coords)
        poi_lat = sum(c[1] for c in coords) / len(coords)
    else:
        return None

    return {
        'id': element.id,
        'type': element_type,
        'category': category,
        'subcategory': tag_value,
        'tag_key': tag_key,
        'name': tags.get('name'),
        'name_en': tags.get('name:en'),
        'brand': tags.get('brand'),
        'operator': tags.get('operator'),
        'phone': tags.get('phone') or tags.get('contact:phone'),
        'website': tags.get('website') or tags.get('contact:website'),
        'opening_hours': tags.get('opening_hours'),
        'wheelchair': tags.get('wheelchair'),
        'lat': poi_lat,
        'lon': poi_lon,
        'tags': tags
    }


def run(args):
    """Execute the poi command."""
    # List categories
    if args.list_categories:
        print("Available POI categories:\n")
        for cat, tag_defs in POI_CATEGORIES.items():
            print(f"  {cat}:")
            for tag_key, values in tag_defs.items():
                print(f"    {tag_key}: {', '.join(sorted(values)[:5])}...")
        return 0

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
    if args.include_ways:
        for node in nodes:
            node_coords[node.id] = [float(node.lon), float(node.lat)]

    pois = []
    target_category = args.category if args.category != 'all' else None

    # Extract from nodes
    for node in nodes:
        if not node.tags:
            continue

        poi = extract_poi_data(node, 'node')
        if poi is None:
            continue

        if target_category and poi['category'] != target_category:
            continue

        if args.named_only and not poi['name']:
            continue

        pois.append(poi)

    # Extract from ways
    if args.include_ways:
        for way in ways:
            if not way.tags:
                continue

            coords = []
            for ref in way.node_refs:
                if ref in node_coords:
                    coords.append(node_coords[ref])

            if len(coords) < 2:
                continue

            poi = extract_poi_data(way, 'way', coords=coords)
            if poi is None:
                continue

            if target_category and poi['category'] != target_category:
                continue

            if args.named_only and not poi['name']:
                continue

            pois.append(poi)

    elapsed = time.time() - start_time

    # Stats mode
    if args.stats:
        print(f"\nPOI Statistics: {args.input}")
        print("=" * 60)
        print(f"Total POIs: {len(pois)}")

        with_name = sum(1 for p in pois if p['name'])
        print(f"With name: {with_name} ({100*with_name//max(len(pois),1)}%)")

        # By category
        print(f"\nBy category:")
        cat_counts = {}
        for p in pois:
            cat_counts[p['category']] = cat_counts.get(p['category'], 0) + 1
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")

        # Top subcategories
        print(f"\nTop subcategories:")
        sub_counts = {}
        for p in pois:
            key = f"{p['tag_key']}={p['subcategory']}"
            sub_counts[key] = sub_counts.get(key, 0) + 1
        for sub, count in sorted(sub_counts.items(), key=lambda x: -x[1])[:15]:
            print(f"  {sub}: {count}")

        print(f"\nProcessing time: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'geojson':
        output = {
            "type": "FeatureCollection",
            "features": []
        }

        for p in pois:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [p['lon'], p['lat']]
                },
                "properties": {
                    "id": p['id'],
                    "category": p['category'],
                    "subcategory": p['subcategory'],
                    "name": p['name'],
                    "brand": p['brand'],
                    "phone": p['phone'],
                    "website": p['website'],
                    "opening_hours": p['opening_hours'],
                    "wheelchair": p['wheelchair']
                }
            }
            output["features"].append(feature)

        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_data = [
            {
                'id': p['id'],
                'category': p['category'],
                'subcategory': p['subcategory'],
                'name': p['name'],
                'brand': p['brand'],
                'lat': p['lat'],
                'lon': p['lon'],
                'phone': p['phone'],
                'website': p['website']
            }
            for p in pois
        ]
        output_str = json.dumps(output_data, indent=2)

    elif args.format == 'csv':
        import csv
        import io

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            'id', 'category', 'subcategory', 'name', 'brand',
            'lat', 'lon', 'phone', 'website', 'opening_hours'
        ])

        for p in pois:
            writer.writerow([
                p['id'], p['category'], p['subcategory'], p['name'],
                p['brand'], round(p['lat'], 7), round(p['lon'], 7),
                p['phone'], p['website'], p['opening_hours']
            ])

        output_str = buffer.getvalue()

    # Write output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(pois)} POIs to: {args.output}")
    else:
        print(output_str)

    print(f"\nPOIs extracted: {len(pois)}", file=sys.stderr)
    print(f"Time: {elapsed:.3f}s", file=sys.stderr)

    return 0
