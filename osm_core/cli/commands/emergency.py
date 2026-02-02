"""Emergency command - extract emergency services and facilities."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


EMERGENCY_TYPES = {
    'services': frozenset({
        'ambulance_station', 'fire_station', 'police', 'mountain_rescue',
        'water_rescue', 'air_rescue', 'coast_guard', 'rescue_station'
    }),
    'medical': frozenset({
        'hospital', 'clinic', 'doctors', 'pharmacy', 'defibrillator',
        'first_aid_kit', 'emergency_ward'
    }),
    'infrastructure': frozenset({
        'fire_hydrant', 'fire_extinguisher', 'fire_alarm', 'fire_hose',
        'emergency_phone', 'phone', 'siren', 'assembly_point',
        'access_point', 'landing_site'
    }),
    'safety': frozenset({
        'life_ring', 'lifeguard', 'lifeguard_tower', 'safety_shower',
        'eye_wash', 'emergency_ward_entrance'
    })
}


def setup_parser(subparsers):
    """Setup the emergency subcommand parser."""
    parser = subparsers.add_parser(
        'emergency',
        help='Extract emergency services and facilities',
        description='Extract emergency-related features from OSM data'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--type', '-t',
        action='append',
        help='Filter by type (e.g., fire_hydrant, defibrillator)'
    )
    parser.add_argument(
        '--category', '-c',
        choices=list(EMERGENCY_TYPES.keys()),
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
    parser.add_argument(
        '--include-amenity',
        action='store_true',
        help='Include amenity=hospital, police, fire_station'
    )

    parser.set_defaults(func=run)
    return parser


def run(args):
    """Execute the emergency command."""
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
            if cat in EMERGENCY_TYPES:
                allowed_types.update(EMERGENCY_TYPES[cat])

    # Amenity types to include
    emergency_amenities = {'hospital', 'clinic', 'pharmacy', 'police', 'fire_station'}

    # Collect features
    features = []

    def process_element(elem, lon, lat, coords=None):
        emergency_type = elem.tags.get('emergency')
        amenity = elem.tags.get('amenity')

        # Check for emergency tag
        if emergency_type:
            if allowed_types and emergency_type not in allowed_types:
                return
            feature_type = emergency_type
            source = 'emergency'
        # Check for relevant amenities
        elif args.include_amenity and amenity in emergency_amenities:
            if allowed_types and amenity not in allowed_types:
                return
            feature_type = amenity
            source = 'amenity'
        else:
            return

        # Get additional info
        phone = elem.tags.get('phone') or elem.tags.get('contact:phone')
        operator = elem.tags.get('operator')
        opening_hours = elem.tags.get('opening_hours')
        wheelchair = elem.tags.get('wheelchair')

        features.append({
            'id': elem.id,
            'osm_type': 'node' if coords is None else 'way',
            'emergency_type': feature_type,
            'source_tag': source,
            'name': elem.tags.get('name'),
            'operator': operator,
            'phone': phone,
            'opening_hours': opening_hours,
            'wheelchair': wheelchair,
            'lon': lon,
            'lat': lat,
            'coords': coords,
            'tags': elem.tags
        })

    # Process nodes
    for node in nodes:
        process_element(node, float(node.lon), float(node.lat))

    # Process ways
    for way in ways:
        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        process_element(way, centroid_lon, centroid_lat, coords)

    elapsed = time.time() - start_time

    # Stats mode
    if args.stats:
        print(f"\nEmergency Features: {args.input}")
        print("=" * 50)
        print(f"Total features: {len(features)}")

        by_type = {}
        for f in features:
            t = f['emergency_type']
            by_type[t] = by_type.get(t, 0) + 1

        print(f"\nBy type:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        # By category
        print(f"\nBy category:")
        for cat, types in EMERGENCY_TYPES.items():
            count = sum(by_type.get(t, 0) for t in types)
            if count:
                print(f"  {cat}: {count}")

        # Operators
        operators = {}
        for f in features:
            op = f.get('operator')
            if op:
                operators[op] = operators.get(op, 0) + 1

        if operators:
            print(f"\nTop operators:")
            for op, count in sorted(operators.items(), key=lambda x: -x[1])[:5]:
                print(f"  {op}: {count}")

        # Wheelchair accessible
        accessible = sum(1 for f in features if f.get('wheelchair') == 'yes')
        if accessible:
            print(f"\nWheelchair accessible: {accessible}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # No output
    if not args.output:
        print(f"Found {len(features)} emergency features")
        for f in features[:10]:
            name = f.get('name') or f.get('operator') or '(unnamed)'
            print(f"  {f['emergency_type']}: {name}")
        if len(features) > 10:
            print(f"  ... and {len(features) - 10} more")
        return 0

    # Generate output
    if args.format == 'geojson':
        geojson_features = []
        for f in features:
            if f.get('coords') and len(f['coords']) > 2:
                is_closed = f['coords'][0] == f['coords'][-1]
                if is_closed:
                    geom = {"type": "Polygon", "coordinates": [f['coords']]}
                else:
                    geom = {"type": "LineString", "coordinates": f['coords']}
            else:
                geom = {"type": "Point", "coordinates": [f['lon'], f['lat']]}

            geojson_features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "id": f['id'],
                    "osm_type": f['osm_type'],
                    "emergency_type": f['emergency_type'],
                    "name": f.get('name'),
                    "operator": f.get('operator'),
                    "phone": f.get('phone'),
                    "opening_hours": f.get('opening_hours'),
                    "wheelchair": f.get('wheelchair')
                }
            })
        output = {"type": "FeatureCollection", "features": geojson_features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        # Remove coords for cleaner JSON output
        output_features = []
        for f in features:
            clean = {k: v for k, v in f.items() if k != 'coords' and k != 'tags'}
            output_features.append(clean)
        output_str = json.dumps(output_features, indent=2)

    elif args.format == 'csv':
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'osm_type', 'emergency_type', 'name', 'operator', 'phone', 'lat', 'lon'])
        for f in features:
            writer.writerow([f['id'], f['osm_type'], f['emergency_type'], f.get('name', ''),
                           f.get('operator', ''), f.get('phone', ''), f['lat'], f['lon']])
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nEmergency extraction complete:")
    print(f"  Features: {len(features)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
