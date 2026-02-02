"""Surface command - analyze road/path surface types."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


SURFACE_CATEGORIES = {
    'paved': frozenset({
        'asphalt', 'concrete', 'paving_stones', 'sett', 'cobblestone',
        'metal', 'wood', 'paved'
    }),
    'unpaved': frozenset({
        'unpaved', 'compacted', 'fine_gravel', 'gravel', 'pebblestone',
        'dirt', 'earth', 'mud', 'sand', 'grass', 'ground'
    }),
    'special': frozenset({
        'rubber', 'tartan', 'artificial_turf', 'clay', 'ice', 'snow'
    })
}


def setup_parser(subparsers):
    """Setup the surface subcommand parser."""
    parser = subparsers.add_parser(
        'surface',
        help='Analyze road/path surface types',
        description='Analyze and extract surface type information'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--surface', '-s',
        action='append',
        help='Filter by surface type (asphalt, gravel, etc.)'
    )
    parser.add_argument(
        '--category', '-c',
        choices=list(SURFACE_CATEGORIES.keys()),
        action='append',
        help='Filter by category (paved, unpaved, special)'
    )
    parser.add_argument(
        '--highway',
        action='append',
        help='Filter by highway type'
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
        '--unknown-only',
        action='store_true',
        help='Show only ways without surface info'
    )

    parser.set_defaults(func=run)
    return parser


def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate distance in meters."""
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat/2)**2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def run(args):
    """Execute the surface command."""
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

    allowed_surfaces = set()
    if args.surface:
        allowed_surfaces.update(args.surface)
    if args.category:
        for cat in args.category:
            if cat in SURFACE_CATEGORIES:
                allowed_surfaces.update(SURFACE_CATEGORIES[cat])

    allowed_highways = set(args.highway) if args.highway else None

    features = []
    stats_by_surface = {}
    stats_by_highway = {}

    for way in ways:
        highway = way.tags.get('highway')
        if not highway:
            continue

        if allowed_highways and highway not in allowed_highways:
            continue

        surface = way.tags.get('surface')
        smoothness = way.tags.get('smoothness')
        tracktype = way.tags.get('tracktype')

        # Handle unknown-only filter
        if args.unknown_only and surface:
            continue

        # Handle surface filters
        if not args.unknown_only:
            if allowed_surfaces and surface not in allowed_surfaces:
                continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if len(coords) < 2:
            continue

        # Calculate length
        length = 0
        for i in range(len(coords) - 1):
            length += haversine_distance(coords[i][0], coords[i][1],
                                        coords[i+1][0], coords[i+1][1])

        # Collect stats
        surface_key = surface or 'unknown'
        if surface_key not in stats_by_surface:
            stats_by_surface[surface_key] = {'count': 0, 'length': 0}
        stats_by_surface[surface_key]['count'] += 1
        stats_by_surface[surface_key]['length'] += length

        if highway not in stats_by_highway:
            stats_by_highway[highway] = {'count': 0, 'length': 0, 'with_surface': 0}
        stats_by_highway[highway]['count'] += 1
        stats_by_highway[highway]['length'] += length
        if surface:
            stats_by_highway[highway]['with_surface'] += 1

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        features.append({
            'id': way.id,
            'highway': highway,
            'surface': surface,
            'smoothness': smoothness,
            'tracktype': tracktype,
            'name': way.tags.get('name'),
            'length_m': round(length, 1),
            'lon': centroid_lon,
            'lat': centroid_lat,
            'coords': coords,
            'tags': way.tags
        })

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nSurface Analysis: {args.input}")
        print("=" * 50)
        print(f"Total ways: {len(features)}")

        total_length = sum(f['length_m'] for f in features)
        print(f"Total length: {total_length/1000:.1f} km")

        print(f"\nBy surface type:")
        for s, data in sorted(stats_by_surface.items(), key=lambda x: -x[1]['length']):
            pct = 100 * data['length'] / max(total_length, 1)
            print(f"  {s}: {data['count']} ways, {data['length']/1000:.1f} km ({pct:.1f}%)")

        print(f"\nSurface coverage by highway type:")
        for h, data in sorted(stats_by_highway.items(), key=lambda x: -x[1]['length']):
            coverage = 100 * data['with_surface'] / max(data['count'], 1)
            print(f"  {h}: {coverage:.0f}% ({data['with_surface']}/{data['count']})")

        # Category breakdown
        print(f"\nBy category:")
        for cat, surfaces in SURFACE_CATEGORIES.items():
            cat_length = sum(stats_by_surface.get(s, {}).get('length', 0) for s in surfaces)
            if cat_length > 0:
                pct = 100 * cat_length / max(total_length, 1)
                print(f"  {cat}: {cat_length/1000:.1f} km ({pct:.1f}%)")

        unknown_length = stats_by_surface.get('unknown', {}).get('length', 0)
        unknown_pct = 100 * unknown_length / max(total_length, 1)
        print(f"\nUnknown surface: {unknown_length/1000:.1f} km ({unknown_pct:.1f}%)")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    if not args.output:
        print(f"Found {len(features)} ways")
        for f in features[:10]:
            surface = f.get('surface') or 'unknown'
            name = f.get('name') or f['highway']
            print(f"  {name}: {surface} ({f['length_m']:.0f}m)")
        if len(features) > 10:
            print(f"  ... and {len(features) - 10} more")
        return 0

    if args.format == 'geojson':
        geojson_features = []
        for f in features:
            geojson_features.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": f['coords']},
                "properties": {
                    "id": f['id'], "highway": f['highway'],
                    "surface": f.get('surface'), "smoothness": f.get('smoothness'),
                    "name": f.get('name'), "length_m": f['length_m']
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
        writer.writerow(['id', 'highway', 'surface', 'smoothness', 'name', 'length_m'])
        for f in features:
            writer.writerow([f['id'], f['highway'], f.get('surface', ''),
                           f.get('smoothness', ''), f.get('name', ''), f['length_m']])
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nSurface extraction complete:")
    print(f"  Ways: {len(features)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
