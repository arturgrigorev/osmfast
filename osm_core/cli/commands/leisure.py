"""Leisure command - extract parks, playgrounds, sports facilities."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


LEISURE_CATEGORIES = {
    'parks': frozenset({
        'park', 'garden', 'nature_reserve', 'dog_park'
    }),
    'sports': frozenset({
        'pitch', 'sports_centre', 'stadium', 'track', 'golf_course',
        'swimming_pool', 'ice_rink', 'fitness_centre', 'horse_riding'
    }),
    'recreation': frozenset({
        'playground', 'fitness_station', 'disc_golf_course', 'miniature_golf',
        'water_park', 'beach_resort', 'amusement_arcade'
    }),
    'culture': frozenset({
        'marina', 'bandstand', 'dance', 'hackerspace'
    })
}


def setup_parser(subparsers):
    """Setup the leisure subcommand parser."""
    parser = subparsers.add_parser(
        'leisure',
        help='Extract parks, playgrounds, sports',
        description='Extract leisure features from OSM data'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--type', '-t',
        action='append',
        help='Filter by leisure type (e.g., park, playground)'
    )
    parser.add_argument(
        '--category', '-c',
        choices=list(LEISURE_CATEGORIES.keys()),
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
    """Calculate polygon area in square meters using shoelace formula."""
    if len(coords) < 3:
        return 0

    # Convert to radians and approximate meters
    R = 6371000
    lat_avg = sum(c[1] for c in coords) / len(coords)
    lon_scale = math.cos(math.radians(lat_avg))

    area = 0
    n = len(coords)
    for i in range(n):
        j = (i + 1) % n
        x1 = math.radians(coords[i][0]) * lon_scale * R
        y1 = math.radians(coords[i][1]) * R
        x2 = math.radians(coords[j][0]) * lon_scale * R
        y2 = math.radians(coords[j][1]) * R
        area += x1 * y2 - x2 * y1

    return abs(area) / 2


def run(args):
    """Execute the leisure command."""
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
            if cat in LEISURE_CATEGORIES:
                allowed_types.update(LEISURE_CATEGORIES[cat])

    # Collect features
    features = []

    # Process nodes
    for node in nodes:
        leisure_type = node.tags.get('leisure')
        if not leisure_type:
            continue

        if allowed_types and leisure_type not in allowed_types:
            continue

        features.append({
            'id': node.id,
            'type': 'node',
            'leisure': leisure_type,
            'name': node.tags.get('name'),
            'sport': node.tags.get('sport'),
            'lon': float(node.lon),
            'lat': float(node.lat),
            'area_sqm': None,
            'tags': node.tags
        })

    # Process ways
    for way in ways:
        leisure_type = way.tags.get('leisure')
        if not leisure_type:
            continue

        if allowed_types and leisure_type not in allowed_types:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        # Calculate area for closed ways
        is_closed = len(coords) > 2 and coords[0] == coords[-1]
        area = calculate_area(coords) if is_closed else None

        features.append({
            'id': way.id,
            'type': 'way',
            'leisure': leisure_type,
            'name': way.tags.get('name'),
            'sport': way.tags.get('sport'),
            'lon': centroid_lon,
            'lat': centroid_lat,
            'area_sqm': round(area, 1) if area else None,
            'coords': coords,
            'tags': way.tags
        })

    elapsed = time.time() - start_time

    # Stats mode
    if args.stats:
        print(f"\nLeisure Statistics: {args.input}")
        print("=" * 50)
        print(f"Total features: {len(features)}")

        by_type = {}
        for f in features:
            t = f['leisure']
            by_type[t] = by_type.get(t, 0) + 1

        print(f"\nBy type:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        # Sports
        sports = {}
        for f in features:
            sport = f.get('sport')
            if sport:
                for s in sport.split(';'):
                    s = s.strip()
                    sports[s] = sports.get(s, 0) + 1

        if sports:
            print(f"\nSports:")
            for s, count in sorted(sports.items(), key=lambda x: -x[1])[:10]:
                print(f"  {s}: {count}")

        # Area stats
        areas = [f['area_sqm'] for f in features if f.get('area_sqm')]
        if areas:
            print(f"\nArea statistics:")
            print(f"  Total area: {sum(areas)/10000:.1f} hectares")
            print(f"  Largest: {max(areas)/10000:.2f} ha")
            print(f"  Average: {sum(areas)/len(areas)/10000:.2f} ha")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # No output
    if not args.output:
        print(f"Found {len(features)} leisure features")
        for f in features[:10]:
            name = f.get('name') or '(unnamed)'
            area_str = f" ({f['area_sqm']/10000:.2f} ha)" if f.get('area_sqm') else ""
            print(f"  {f['leisure']}: {name}{area_str}")
        if len(features) > 10:
            print(f"  ... and {len(features) - 10} more")
        return 0

    # Generate output
    if args.format == 'geojson':
        geojson_features = []
        for f in features:
            if f.get('coords') and len(f['coords']) > 2 and f['coords'][0] == f['coords'][-1]:
                geom = {"type": "Polygon", "coordinates": [f['coords']]}
            else:
                geom = {"type": "Point", "coordinates": [f['lon'], f['lat']]}

            geojson_features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "id": f['id'],
                    "osm_type": f['type'],
                    "leisure": f['leisure'],
                    "name": f.get('name'),
                    "sport": f.get('sport'),
                    "area_sqm": f.get('area_sqm')
                }
            })
        output = {"type": "FeatureCollection", "features": geojson_features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_str = json.dumps(features, indent=2, default=str)

    elif args.format == 'csv':
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'osm_type', 'leisure', 'name', 'sport', 'lat', 'lon', 'area_sqm'])
        for f in features:
            writer.writerow([f['id'], f['type'], f['leisure'], f.get('name', ''),
                           f.get('sport', ''), f['lat'], f['lon'], f.get('area_sqm', '')])
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nLeisure extraction complete:")
    print(f"  Features: {len(features)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
