"""Sport command - extract sports facilities and venues."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


SPORT_TYPES = {
    'ball': frozenset({
        'soccer', 'football', 'basketball', 'tennis', 'volleyball',
        'baseball', 'cricket', 'rugby', 'hockey', 'handball', 'netball',
        'badminton', 'squash', 'table_tennis', 'golf', 'bowling'
    }),
    'water': frozenset({
        'swimming', 'diving', 'water_polo', 'surfing', 'sailing',
        'rowing', 'canoeing', 'kayaking', 'kitesurfing', 'windsurfing',
        'scuba_diving', 'fishing'
    }),
    'fitness': frozenset({
        'fitness', 'gym', 'yoga', 'pilates', 'crossfit', 'weightlifting',
        'bodybuilding', 'aerobics', 'dance'
    }),
    'cycling': frozenset({
        'cycling', 'bmx', 'mountain_biking', 'motocross'
    }),
    'athletics': frozenset({
        'athletics', 'running', 'marathon', 'triathlon', 'long_jump',
        'high_jump', 'shot_put', 'javelin', 'discus'
    }),
    'combat': frozenset({
        'boxing', 'wrestling', 'judo', 'karate', 'taekwondo',
        'martial_arts', 'fencing', 'aikido', 'kendo'
    }),
    'winter': frozenset({
        'skiing', 'ice_skating', 'ice_hockey', 'curling', 'snowboarding',
        'cross_country_skiing', 'biathlon'
    }),
    'other': frozenset({
        'climbing', 'bouldering', 'horse_racing', 'equestrian',
        'skateboarding', 'archery', 'shooting', 'paragliding'
    })
}


def setup_parser(subparsers):
    """Setup the sport subcommand parser."""
    parser = subparsers.add_parser(
        'sport',
        help='Extract sports facilities',
        description='Extract sports venues, pitches, and facilities'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--sport', '-s',
        action='append',
        help='Filter by sport (soccer, tennis, swimming, etc.)'
    )
    parser.add_argument(
        '--category', '-c',
        choices=list(SPORT_TYPES.keys()),
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


def calculate_area(coords):
    """Calculate polygon area in square meters."""
    if len(coords) < 3:
        return 0
    R = 6371000
    lat_avg = sum(c[1] for c in coords) / len(coords)
    lon_scale = math.cos(math.radians(lat_avg))
    area = 0
    n = len(coords)
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = math.radians(coords[i][0]) * lon_scale * R, math.radians(coords[i][1]) * R
        x2, y2 = math.radians(coords[j][0]) * lon_scale * R, math.radians(coords[j][1]) * R
        area += x1 * y2 - x2 * y1
    return abs(area) / 2


def run(args):
    """Execute the sport command."""
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

    allowed_sports = set()
    if args.sport:
        allowed_sports.update(s.lower() for s in args.sport)
    if args.category:
        for cat in args.category:
            if cat in SPORT_TYPES:
                allowed_sports.update(SPORT_TYPES[cat])

    features = []

    def process_element(elem, lon, lat, coords=None):
        sport = elem.tags.get('sport')
        leisure = elem.tags.get('leisure')

        # Must have sport tag or be a sports-related leisure
        if not sport and leisure not in ('pitch', 'sports_centre', 'stadium', 'track', 'swimming_pool', 'fitness_centre', 'golf_course'):
            return

        sports_list = [s.strip().lower() for s in sport.split(';')] if sport else []

        if allowed_sports:
            if not any(s in allowed_sports for s in sports_list):
                return

        area = None
        if coords and len(coords) > 2 and coords[0] == coords[-1]:
            area = calculate_area(coords)

        features.append({
            'id': elem.id,
            'osm_type': 'node' if coords is None else 'way',
            'sport': sport,
            'leisure': leisure,
            'name': elem.tags.get('name'),
            'surface': elem.tags.get('surface'),
            'lit': elem.tags.get('lit'),
            'covered': elem.tags.get('covered'),
            'access': elem.tags.get('access'),
            'operator': elem.tags.get('operator'),
            'area_sqm': round(area, 1) if area else None,
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
        print(f"\nSports Facilities: {args.input}")
        print("=" * 50)
        print(f"Total: {len(features)}")

        sports = {}
        for f in features:
            sport = f.get('sport')
            if sport:
                for s in sport.split(';'):
                    s = s.strip()
                    sports[s] = sports.get(s, 0) + 1

        print(f"\nBy sport:")
        for s, count in sorted(sports.items(), key=lambda x: -x[1])[:20]:
            print(f"  {s}: {count}")

        by_leisure = {}
        for f in features:
            l = f.get('leisure')
            if l:
                by_leisure[l] = by_leisure.get(l, 0) + 1

        if by_leisure:
            print(f"\nBy facility type:")
            for l, count in sorted(by_leisure.items(), key=lambda x: -x[1]):
                print(f"  {l}: {count}")

        lit = sum(1 for f in features if f.get('lit') == 'yes')
        covered = sum(1 for f in features if f.get('covered') == 'yes')

        print(f"\nAmenities:")
        print(f"  Lit: {lit}")
        print(f"  Covered: {covered}")

        areas = [f['area_sqm'] for f in features if f.get('area_sqm')]
        if areas:
            print(f"\nArea statistics:")
            print(f"  Total: {sum(areas)/10000:.1f} ha")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    if not args.output:
        print(f"Found {len(features)} sports facilities")
        for f in features[:10]:
            name = f.get('name') or f.get('sport') or f.get('leisure') or '(unnamed)'
            sport = f" ({f['sport']})" if f.get('sport') else ""
            print(f"  {f.get('leisure', 'facility')}: {name}{sport}")
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
                    "sport": f.get('sport'), "leisure": f.get('leisure'),
                    "name": f.get('name'), "surface": f.get('surface'),
                    "lit": f.get('lit'), "area_sqm": f.get('area_sqm')
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
        writer.writerow(['id', 'osm_type', 'sport', 'leisure', 'name', 'surface', 'lat', 'lon', 'area_sqm'])
        for f in features:
            writer.writerow([f['id'], f['osm_type'], f.get('sport', ''), f.get('leisure', ''),
                           f.get('name', ''), f.get('surface', ''), f['lat'], f['lon'], f.get('area_sqm', '')])
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nSport extraction complete:")
    print(f"  Facilities: {len(features)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
