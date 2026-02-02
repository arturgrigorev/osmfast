"""Healthcare command - extract health facilities."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


HEALTHCARE_TYPES = {
    'hospital': frozenset({'hospital', 'clinic'}),
    'doctor': frozenset({'doctors', 'doctor', 'general_practitioner'}),
    'specialist': frozenset({
        'dentist', 'optometrist', 'physiotherapist', 'psychologist',
        'psychiatrist', 'podiatrist', 'chiropractor', 'dermatologist',
        'cardiologist', 'neurologist', 'gynecologist', 'urologist',
        'pediatrician', 'geriatrician', 'oncologist', 'radiologist'
    }),
    'pharmacy': frozenset({'pharmacy', 'chemist'}),
    'emergency': frozenset({'emergency', 'urgent_care'}),
    'other': frozenset({
        'nursing_home', 'hospice', 'blood_donation', 'dialysis',
        'rehabilitation', 'laboratory', 'sample_collection', 'vaccination_centre'
    })
}


def setup_parser(subparsers):
    """Setup the healthcare subcommand parser."""
    parser = subparsers.add_parser(
        'healthcare',
        help='Extract health facilities',
        description='Extract hospitals, clinics, pharmacies, doctors'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--type', '-t',
        action='append',
        help='Filter by type (hospital, pharmacy, dentist, etc.)'
    )
    parser.add_argument(
        '--category', '-c',
        choices=list(HEALTHCARE_TYPES.keys()),
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
        '--emergency-only',
        action='store_true',
        help='Only show facilities with emergency services'
    )

    parser.set_defaults(func=run)
    return parser


def run(args):
    """Execute the healthcare command."""
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
            if cat in HEALTHCARE_TYPES:
                allowed_types.update(HEALTHCARE_TYPES[cat])

    features = []

    def process_element(elem, lon, lat, coords=None):
        # Check multiple tags for healthcare
        healthcare_type = elem.tags.get('healthcare')
        amenity = elem.tags.get('amenity')

        facility_type = None
        if healthcare_type:
            facility_type = healthcare_type
        elif amenity in ('hospital', 'clinic', 'doctors', 'dentist', 'pharmacy', 'veterinary'):
            facility_type = amenity

        if not facility_type:
            return

        if allowed_types and facility_type not in allowed_types:
            return

        has_emergency = elem.tags.get('emergency') == 'yes'
        if args.emergency_only and not has_emergency:
            return

        specialty = elem.tags.get('healthcare:speciality') or elem.tags.get('health_specialty:type')

        features.append({
            'id': elem.id,
            'osm_type': 'node' if coords is None else 'way',
            'healthcare_type': facility_type,
            'name': elem.tags.get('name'),
            'operator': elem.tags.get('operator'),
            'specialty': specialty,
            'emergency': has_emergency,
            'wheelchair': elem.tags.get('wheelchair'),
            'opening_hours': elem.tags.get('opening_hours'),
            'phone': elem.tags.get('phone') or elem.tags.get('contact:phone'),
            'website': elem.tags.get('website'),
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
        print(f"\nHealthcare Facilities: {args.input}")
        print("=" * 50)
        print(f"Total: {len(features)}")

        by_type = {}
        for f in features:
            t = f['healthcare_type']
            by_type[t] = by_type.get(t, 0) + 1

        print(f"\nBy type:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        emergency_count = sum(1 for f in features if f.get('emergency'))
        wheelchair = sum(1 for f in features if f.get('wheelchair') == 'yes')

        print(f"\nAccessibility:")
        print(f"  Emergency services: {emergency_count}")
        print(f"  Wheelchair accessible: {wheelchair}")

        specialties = {}
        for f in features:
            spec = f.get('specialty')
            if spec:
                for s in spec.split(';'):
                    s = s.strip()
                    specialties[s] = specialties.get(s, 0) + 1

        if specialties:
            print(f"\nSpecialties:")
            for s, count in sorted(specialties.items(), key=lambda x: -x[1])[:10]:
                print(f"  {s}: {count}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    if not args.output:
        print(f"Found {len(features)} healthcare facilities")
        for f in features[:10]:
            name = f.get('name') or '(unnamed)'
            emergency = " [EMERGENCY]" if f.get('emergency') else ""
            print(f"  {f['healthcare_type']}: {name}{emergency}")
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
                    "healthcare_type": f['healthcare_type'], "name": f.get('name'),
                    "operator": f.get('operator'), "specialty": f.get('specialty'),
                    "emergency": f.get('emergency'), "wheelchair": f.get('wheelchair'),
                    "phone": f.get('phone')
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
        writer.writerow(['id', 'osm_type', 'healthcare_type', 'name', 'operator', 'emergency', 'lat', 'lon', 'phone'])
        for f in features:
            writer.writerow([f['id'], f['osm_type'], f['healthcare_type'], f.get('name', ''),
                           f.get('operator', ''), f.get('emergency', ''), f['lat'], f['lon'], f.get('phone', '')])
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nHealthcare extraction complete:")
    print(f"  Facilities: {len(features)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
