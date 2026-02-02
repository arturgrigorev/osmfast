"""Education command - extract educational facilities."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


EDUCATION_TYPES = {
    'school': frozenset({'school', 'primary', 'secondary', 'high_school'}),
    'higher': frozenset({'university', 'college'}),
    'preschool': frozenset({'kindergarten', 'childcare', 'nursery'}),
    'specialized': frozenset({
        'language_school', 'music_school', 'driving_school',
        'dance_school', 'cooking_school', 'art_school', 'surf_school'
    }),
    'other': frozenset({'library', 'training', 'research_institute'})
}


def setup_parser(subparsers):
    """Setup the education subcommand parser."""
    parser = subparsers.add_parser(
        'education',
        help='Extract educational facilities',
        description='Extract schools, universities, libraries'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--type', '-t',
        action='append',
        help='Filter by type (school, university, library, etc.)'
    )
    parser.add_argument(
        '--category', '-c',
        choices=list(EDUCATION_TYPES.keys()),
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
    """Execute the education command."""
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
            if cat in EDUCATION_TYPES:
                allowed_types.update(EDUCATION_TYPES[cat])

    # Educational amenities to look for
    edu_amenities = frozenset({
        'school', 'university', 'college', 'kindergarten', 'library',
        'language_school', 'music_school', 'driving_school', 'training'
    })

    features = []

    def process_element(elem, lon, lat, coords=None):
        amenity = elem.tags.get('amenity')
        if amenity not in edu_amenities:
            return

        if allowed_types and amenity not in allowed_types:
            return

        # Get education level if available
        isced_level = elem.tags.get('isced:level')
        grades = elem.tags.get('grades')
        capacity = elem.tags.get('capacity')

        features.append({
            'id': elem.id,
            'osm_type': 'node' if coords is None else 'way',
            'education_type': amenity,
            'name': elem.tags.get('name'),
            'operator': elem.tags.get('operator'),
            'isced_level': isced_level,
            'grades': grades,
            'capacity': capacity,
            'website': elem.tags.get('website'),
            'phone': elem.tags.get('phone') or elem.tags.get('contact:phone'),
            'wheelchair': elem.tags.get('wheelchair'),
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
        print(f"\nEducation Facilities: {args.input}")
        print("=" * 50)
        print(f"Total: {len(features)}")

        by_type = {}
        for f in features:
            t = f['education_type']
            by_type[t] = by_type.get(t, 0) + 1

        print(f"\nBy type:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        operators = {}
        for f in features:
            op = f.get('operator')
            if op:
                operators[op] = operators.get(op, 0) + 1

        if operators:
            print(f"\nTop operators:")
            for op, count in sorted(operators.items(), key=lambda x: -x[1])[:10]:
                print(f"  {op}: {count}")

        with_capacity = [f for f in features if f.get('capacity')]
        if with_capacity:
            caps = [int(f['capacity']) for f in with_capacity if f['capacity'].isdigit()]
            if caps:
                print(f"\nCapacity ({len(with_capacity)} facilities):")
                print(f"  Total: {sum(caps)}")
                print(f"  Average: {sum(caps)//len(caps)}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    if not args.output:
        print(f"Found {len(features)} education facilities")
        for f in features[:10]:
            name = f.get('name') or '(unnamed)'
            print(f"  {f['education_type']}: {name}")
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
                    "education_type": f['education_type'], "name": f.get('name'),
                    "operator": f.get('operator'), "capacity": f.get('capacity'),
                    "website": f.get('website'), "phone": f.get('phone')
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
        writer.writerow(['id', 'osm_type', 'education_type', 'name', 'operator', 'capacity', 'lat', 'lon'])
        for f in features:
            writer.writerow([f['id'], f['osm_type'], f['education_type'], f.get('name', ''),
                           f.get('operator', ''), f.get('capacity', ''), f['lat'], f['lon']])
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nEducation extraction complete:")
    print(f"  Facilities: {len(features)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
