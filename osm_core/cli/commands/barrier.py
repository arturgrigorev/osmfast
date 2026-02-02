"""Barrier command - extract barriers (fences, walls, gates)."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


BARRIER_TYPES = {
    'linear': frozenset({
        'fence', 'wall', 'hedge', 'retaining_wall', 'guard_rail',
        'handrail', 'kerb', 'city_wall', 'ditch', 'cable_barrier'
    }),
    'access': frozenset({
        'gate', 'lift_gate', 'swing_gate', 'toll_booth', 'border_control',
        'entrance', 'cattle_grid', 'stile', 'turnstile', 'kissing_gate',
        'full-height_turnstile', 'sally_port'
    }),
    'blocking': frozenset({
        'bollard', 'block', 'jersey_barrier', 'planter', 'log',
        'chain', 'rope', 'debris', 'tank_trap'
    }),
    'traffic': frozenset({
        'bump', 'hump', 'table', 'cushion', 'rumble_strip',
        'chicane', 'island', 'kerb'
    })
}


def setup_parser(subparsers):
    """Setup the barrier subcommand parser."""
    parser = subparsers.add_parser(
        'barrier',
        help='Extract barriers (fences, walls, gates)',
        description='Extract barrier features from OSM data'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--type', '-t',
        action='append',
        help='Filter by barrier type (fence, wall, gate, etc.)'
    )
    parser.add_argument(
        '--category', '-c',
        choices=list(BARRIER_TYPES.keys()),
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
    """Execute the barrier command."""
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
            if cat in BARRIER_TYPES:
                allowed_types.update(BARRIER_TYPES[cat])

    features = []

    # Process nodes (point barriers like bollards, gates)
    for node in nodes:
        barrier_type = node.tags.get('barrier')
        if not barrier_type:
            continue
        if allowed_types and barrier_type not in allowed_types:
            continue

        features.append({
            'id': node.id,
            'osm_type': 'node',
            'barrier': barrier_type,
            'name': node.tags.get('name'),
            'material': node.tags.get('material'),
            'height': node.tags.get('height'),
            'access': node.tags.get('access'),
            'bicycle': node.tags.get('bicycle'),
            'foot': node.tags.get('foot'),
            'lon': float(node.lon),
            'lat': float(node.lat),
            'length_m': None,
            'tags': node.tags
        })

    # Process ways (linear barriers like fences, walls)
    for way in ways:
        barrier_type = way.tags.get('barrier')
        if not barrier_type:
            continue
        if allowed_types and barrier_type not in allowed_types:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue

        # Calculate length
        length = 0
        for i in range(len(coords) - 1):
            length += haversine_distance(coords[i][0], coords[i][1],
                                        coords[i+1][0], coords[i+1][1])

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        features.append({
            'id': way.id,
            'osm_type': 'way',
            'barrier': barrier_type,
            'name': way.tags.get('name'),
            'material': way.tags.get('material'),
            'height': way.tags.get('height'),
            'access': way.tags.get('access'),
            'bicycle': way.tags.get('bicycle'),
            'foot': way.tags.get('foot'),
            'lon': centroid_lon,
            'lat': centroid_lat,
            'length_m': round(length, 1),
            'coords': coords,
            'tags': way.tags
        })

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nBarrier Features: {args.input}")
        print("=" * 50)
        print(f"Total: {len(features)}")

        by_type = {}
        for f in features:
            t = f['barrier']
            by_type[t] = by_type.get(t, 0) + 1

        print(f"\nBy type:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        linear = [f for f in features if f.get('length_m')]
        if linear:
            total_length = sum(f['length_m'] for f in linear)
            print(f"\nLinear barriers:")
            print(f"  Count: {len(linear)}")
            print(f"  Total length: {total_length/1000:.1f} km")

        materials = {}
        for f in features:
            mat = f.get('material')
            if mat:
                materials[mat] = materials.get(mat, 0) + 1

        if materials:
            print(f"\nMaterials:")
            for m, count in sorted(materials.items(), key=lambda x: -x[1])[:10]:
                print(f"  {m}: {count}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    if not args.output:
        print(f"Found {len(features)} barriers")
        for f in features[:10]:
            length = f" ({f['length_m']:.0f}m)" if f.get('length_m') else ""
            print(f"  {f['barrier']}{length}")
        if len(features) > 10:
            print(f"  ... and {len(features) - 10} more")
        return 0

    if args.format == 'geojson':
        geojson_features = []
        for f in features:
            if f.get('coords') and len(f['coords']) > 1:
                geom = {"type": "LineString", "coordinates": f['coords']}
            else:
                geom = {"type": "Point", "coordinates": [f['lon'], f['lat']]}

            geojson_features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "id": f['id'], "osm_type": f['osm_type'],
                    "barrier": f['barrier'], "material": f.get('material'),
                    "height": f.get('height'), "length_m": f.get('length_m'),
                    "access": f.get('access')
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
        writer.writerow(['id', 'osm_type', 'barrier', 'material', 'height', 'length_m', 'lat', 'lon'])
        for f in features:
            writer.writerow([f['id'], f['osm_type'], f['barrier'], f.get('material', ''),
                           f.get('height', ''), f.get('length_m', ''), f['lat'], f['lon']])
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nBarrier extraction complete:")
    print(f"  Features: {len(features)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
