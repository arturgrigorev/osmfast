"""Amenity command - extract amenities with filtering."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


# Common amenity categories
AMENITY_CATEGORIES = {
    'food': frozenset({
        'restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'food_court',
        'ice_cream', 'biergarten', 'nightclub'
    }),
    'education': frozenset({
        'school', 'university', 'college', 'kindergarten', 'library',
        'language_school', 'music_school', 'driving_school', 'training'
    }),
    'health': frozenset({
        'hospital', 'clinic', 'doctors', 'dentist', 'pharmacy', 'veterinary',
        'nursing_home', 'social_facility'
    }),
    'transport': frozenset({
        'parking', 'fuel', 'bus_station', 'taxi', 'car_rental', 'car_wash',
        'bicycle_parking', 'bicycle_rental', 'charging_station', 'ferry_terminal'
    }),
    'finance': frozenset({
        'bank', 'atm', 'bureau_de_change', 'money_transfer'
    }),
    'public': frozenset({
        'townhall', 'courthouse', 'police', 'fire_station', 'post_office',
        'community_centre', 'social_centre', 'prison'
    }),
    'worship': frozenset({
        'place_of_worship'
    }),
    'entertainment': frozenset({
        'cinema', 'theatre', 'casino', 'arts_centre', 'studio'
    }),
    'service': frozenset({
        'toilets', 'shower', 'drinking_water', 'telephone', 'bench',
        'waste_basket', 'recycling', 'vending_machine', 'photo_booth'
    })
}


def setup_parser(subparsers):
    """Setup the amenity subcommand parser."""
    parser = subparsers.add_parser(
        'amenity',
        help='Extract amenities with filtering',
        description='Extract amenity nodes and ways from OSM data'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--type', '-t',
        action='append',
        help='Filter by amenity type (e.g., restaurant, school). Can be repeated.'
    )
    parser.add_argument(
        '--category', '-c',
        choices=list(AMENITY_CATEGORIES.keys()),
        action='append',
        help='Filter by category (food, education, health, etc.)'
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
        help='List all amenity types found in file'
    )

    parser.set_defaults(func=run)
    return parser


def run(args):
    """Execute the amenity command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse the file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Build node coordinate lookup
    node_coords = {}
    for node in nodes:
        node_coords[node.id] = (float(node.lon), float(node.lat))

    # Build filter set
    allowed_types = set()
    if args.type:
        allowed_types.update(args.type)
    if args.category:
        for cat in args.category:
            if cat in AMENITY_CATEGORIES:
                allowed_types.update(AMENITY_CATEGORIES[cat])

    # Collect amenities
    amenities = []
    type_counts = {}

    # Process nodes
    for node in nodes:
        amenity_type = node.tags.get('amenity')
        if not amenity_type:
            continue

        type_counts[amenity_type] = type_counts.get(amenity_type, 0) + 1

        if allowed_types and amenity_type not in allowed_types:
            continue

        amenities.append({
            'id': node.id,
            'type': 'node',
            'amenity': amenity_type,
            'name': node.tags.get('name'),
            'lon': float(node.lon),
            'lat': float(node.lat),
            'tags': node.tags
        })

    # Process ways
    for way in ways:
        amenity_type = way.tags.get('amenity')
        if not amenity_type:
            continue

        type_counts[amenity_type] = type_counts.get(amenity_type, 0) + 1

        if allowed_types and amenity_type not in allowed_types:
            continue

        # Calculate centroid
        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        amenities.append({
            'id': way.id,
            'type': 'way',
            'amenity': amenity_type,
            'name': way.tags.get('name'),
            'lon': centroid_lon,
            'lat': centroid_lat,
            'coords': coords,
            'tags': way.tags
        })

    elapsed = time.time() - start_time

    # List types mode
    if args.list_types:
        print(f"\nAmenity types in {args.input}:")
        print("=" * 50)
        for amenity_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"  {amenity_type}: {count}")
        print(f"\nTotal types: {len(type_counts)}")
        print(f"Total amenities: {sum(type_counts.values())}")
        return 0

    # Stats mode
    if args.stats:
        print(f"\nAmenity Statistics: {args.input}")
        print("=" * 50)
        print(f"Total amenities: {len(amenities)}")

        # By type
        by_type = {}
        for a in amenities:
            t = a['amenity']
            by_type[t] = by_type.get(t, 0) + 1

        print(f"\nBy type:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1])[:20]:
            print(f"  {t}: {count}")

        # Named vs unnamed
        named = sum(1 for a in amenities if a.get('name'))
        print(f"\nNamed: {named} ({100*named/max(len(amenities),1):.1f}%)")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # Generate output
    if not args.output:
        print(f"Found {len(amenities)} amenities")
        for a in amenities[:10]:
            name = a.get('name') or '(unnamed)'
            print(f"  {a['amenity']}: {name} ({a['lat']:.6f}, {a['lon']:.6f})")
        if len(amenities) > 10:
            print(f"  ... and {len(amenities) - 10} more")
        return 0

    if args.format == 'geojson':
        features = []
        for a in amenities:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [a['lon'], a['lat']]
                },
                "properties": {
                    "id": a['id'],
                    "osm_type": a['type'],
                    "amenity": a['amenity'],
                    "name": a.get('name'),
                    **{k: v for k, v in a['tags'].items() if k not in ('amenity', 'name')}
                }
            })
        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_str = json.dumps(amenities, indent=2)

    elif args.format == 'csv':
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'osm_type', 'amenity', 'name', 'lat', 'lon'])
        for a in amenities:
            writer.writerow([a['id'], a['type'], a['amenity'], a.get('name', ''),
                           a['lat'], a['lon']])
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nAmenity extraction complete:")
    print(f"  Amenities: {len(amenities)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
