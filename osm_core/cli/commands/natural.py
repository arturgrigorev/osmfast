"""Natural command - extract natural features."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


NATURAL_TYPES = {
    'landform': frozenset({
        'peak', 'hill', 'volcano', 'valley', 'ridge', 'saddle', 'cliff',
        'cave_entrance', 'rock', 'stone', 'scree', 'sinkhole', 'arch'
    }),
    'vegetation': frozenset({
        'wood', 'tree', 'tree_row', 'scrub', 'heath', 'grassland', 'fell',
        'tundra', 'bare_rock', 'shingle'
    }),
    'water': frozenset({
        'water', 'bay', 'strait', 'spring', 'hot_spring', 'geyser',
        'wetland', 'glacier', 'reef'
    }),
    'coastal': frozenset({
        'beach', 'coastline', 'shoal', 'cape', 'peninsula', 'isthmus'
    })
}


def setup_parser(subparsers):
    """Setup the natural subcommand parser."""
    parser = subparsers.add_parser(
        'natural',
        help='Extract natural features',
        description='Extract natural features (peaks, caves, beaches, etc.)'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--type', '-t',
        action='append',
        help='Filter by natural type (e.g., peak, beach)'
    )
    parser.add_argument(
        '--category', '-c',
        choices=list(NATURAL_TYPES.keys()),
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
    """Execute the natural command."""
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
            if cat in NATURAL_TYPES:
                allowed_types.update(NATURAL_TYPES[cat])

    # Collect features
    features = []

    # Process nodes
    for node in nodes:
        natural_type = node.tags.get('natural')
        if not natural_type:
            continue

        if allowed_types and natural_type not in allowed_types:
            continue

        ele = node.tags.get('ele')
        try:
            elevation = float(ele) if ele else None
        except ValueError:
            elevation = None

        features.append({
            'id': node.id,
            'type': 'node',
            'natural': natural_type,
            'name': node.tags.get('name'),
            'elevation': elevation,
            'lon': float(node.lon),
            'lat': float(node.lat),
            'tags': node.tags
        })

    # Process ways
    for way in ways:
        natural_type = way.tags.get('natural')
        if not natural_type:
            continue

        if allowed_types and natural_type not in allowed_types:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue

        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        features.append({
            'id': way.id,
            'type': 'way',
            'natural': natural_type,
            'name': way.tags.get('name'),
            'elevation': None,
            'lon': centroid_lon,
            'lat': centroid_lat,
            'coords': coords,
            'tags': way.tags
        })

    elapsed = time.time() - start_time

    # Stats mode
    if args.stats:
        print(f"\nNatural Features: {args.input}")
        print("=" * 50)
        print(f"Total features: {len(features)}")

        by_type = {}
        for f in features:
            t = f['natural']
            by_type[t] = by_type.get(t, 0) + 1

        print(f"\nBy type:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        # Elevation stats for peaks
        peaks = [f for f in features if f['natural'] == 'peak' and f.get('elevation')]
        if peaks:
            elevations = [p['elevation'] for p in peaks]
            print(f"\nPeak elevations:")
            print(f"  Highest: {max(elevations):.0f}m")
            print(f"  Lowest: {min(elevations):.0f}m")
            print(f"  Average: {sum(elevations)/len(elevations):.0f}m")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # No output
    if not args.output:
        print(f"Found {len(features)} natural features")
        for f in features[:10]:
            name = f.get('name') or '(unnamed)'
            ele_str = f" ({f['elevation']:.0f}m)" if f.get('elevation') else ""
            print(f"  {f['natural']}: {name}{ele_str}")
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
                    "osm_type": f['type'],
                    "natural": f['natural'],
                    "name": f.get('name'),
                    "elevation": f.get('elevation')
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
        writer.writerow(['id', 'osm_type', 'natural', 'name', 'elevation', 'lat', 'lon'])
        for f in features:
            writer.writerow([f['id'], f['type'], f['natural'], f.get('name', ''),
                           f.get('elevation', ''), f['lat'], f['lon']])
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nNatural extraction complete:")
    print(f"  Features: {len(features)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
