"""Historic command - extract historic sites and monuments."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


HISTORIC_TYPES = {
    'monument': frozenset({
        'monument', 'memorial', 'statue', 'bust', 'stone', 'plaque',
        'milestone', 'boundary_stone'
    }),
    'building': frozenset({
        'castle', 'manor', 'palace', 'fort', 'tower', 'city_gate',
        'church', 'monastery', 'mosque', 'temple', 'synagogue',
        'ruins', 'archaeological_site'
    }),
    'military': frozenset({
        'battlefield', 'bomb_crater', 'bunker', 'cannon', 'tank',
        'aircraft', 'ship', 'wreck'
    }),
    'industrial': frozenset({
        'mine', 'quarry', 'adit', 'mine_shaft', 'locomotive', 'railway_car',
        'mill', 'charcoal_pile', 'kiln', 'lime_kiln'
    }),
    'other': frozenset({
        'tomb', 'grave', 'cemetery', 'gallows', 'pillory', 'wayside_cross',
        'wayside_shrine', 'yes'
    })
}


def setup_parser(subparsers):
    """Setup the historic subcommand parser."""
    parser = subparsers.add_parser(
        'historic',
        help='Extract historic sites and monuments',
        description='Extract historic features from OSM data'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--type', '-t',
        action='append',
        help='Filter by historic type (e.g., castle, monument)'
    )
    parser.add_argument(
        '--category', '-c',
        choices=list(HISTORIC_TYPES.keys()),
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
        '--heritage',
        action='store_true',
        help='Include heritage protected sites'
    )

    parser.set_defaults(func=run)
    return parser


def run(args):
    """Execute the historic command."""
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
            if cat in HISTORIC_TYPES:
                allowed_types.update(HISTORIC_TYPES[cat])

    # Collect features
    features = []

    def process_element(elem, lon, lat, coords=None):
        historic_type = elem.tags.get('historic')
        has_heritage = 'heritage' in elem.tags or 'heritage:operator' in elem.tags

        if not historic_type:
            if args.heritage and has_heritage:
                historic_type = 'heritage_site'
            else:
                return

        if allowed_types and historic_type not in allowed_types:
            return

        # Get additional info
        start_date = elem.tags.get('start_date') or elem.tags.get('year')
        architect = elem.tags.get('architect')
        heritage = elem.tags.get('heritage') or elem.tags.get('heritage:operator')
        wikipedia = elem.tags.get('wikipedia')

        features.append({
            'id': elem.id,
            'type': 'node' if coords is None else 'way',
            'historic': historic_type,
            'name': elem.tags.get('name'),
            'description': elem.tags.get('description'),
            'start_date': start_date,
            'architect': architect,
            'heritage': heritage,
            'wikipedia': wikipedia,
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
        print(f"\nHistoric Features: {args.input}")
        print("=" * 50)
        print(f"Total features: {len(features)}")

        by_type = {}
        for f in features:
            t = f['historic']
            by_type[t] = by_type.get(t, 0) + 1

        print(f"\nBy type:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        # Heritage sites
        heritage_count = sum(1 for f in features if f.get('heritage'))
        if heritage_count:
            print(f"\nHeritage protected: {heritage_count}")

        # With dates
        dated = sum(1 for f in features if f.get('start_date'))
        if dated:
            print(f"With dates: {dated}")

        # Wikipedia links
        wiki = sum(1 for f in features if f.get('wikipedia'))
        if wiki:
            print(f"Wikipedia articles: {wiki}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # No output
    if not args.output:
        print(f"Found {len(features)} historic features")
        for f in features[:10]:
            name = f.get('name') or '(unnamed)'
            date_str = f" ({f['start_date']})" if f.get('start_date') else ""
            print(f"  {f['historic']}: {name}{date_str}")
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
                    "historic": f['historic'],
                    "name": f.get('name'),
                    "description": f.get('description'),
                    "start_date": f.get('start_date'),
                    "heritage": f.get('heritage'),
                    "wikipedia": f.get('wikipedia')
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
        writer.writerow(['id', 'osm_type', 'historic', 'name', 'start_date', 'heritage', 'lat', 'lon'])
        for f in features:
            writer.writerow([f['id'], f['type'], f['historic'], f.get('name', ''),
                           f.get('start_date', ''), f.get('heritage', ''), f['lat'], f['lon']])
        output_str = buffer.getvalue()

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output_str)

    print(f"\nHistoric extraction complete:")
    print(f"  Features: {len(features)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
