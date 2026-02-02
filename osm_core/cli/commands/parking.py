"""Parking command - extract parking facilities."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser
from ...utils.geo_utils import calculate_polygon_area


def setup_parser(subparsers):
    """Setup the parking subcommand parser."""
    parser = subparsers.add_parser(
        'parking',
        help='Extract parking facilities',
        description='Extract parking lots, garages, and spaces'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv'],
        default='geojson',
        help='Output format (default: geojson)'
    )
    parser.add_argument(
        '--type',
        choices=['surface', 'underground', 'multi-storey', 'rooftop', 'all'],
        default='all',
        help='Parking type'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only'
    )

    parser.set_defaults(func=run)
    return parser


def run(args):
    """Execute the parking command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    node_coords = {}
    for node in nodes:
        node_coords[node.id] = [float(node.lon), float(node.lat)]

    features = []

    # Extract parking nodes
    for node in nodes:
        if node.tags.get('amenity') != 'parking':
            continue

        parking_type = node.tags.get('parking', 'surface')
        if args.type != 'all' and parking_type != args.type:
            continue

        features.append({
            'id': node.id,
            'element_type': 'node',
            'parking': parking_type,
            'name': node.tags.get('name'),
            'access': node.tags.get('access'),
            'fee': node.tags.get('fee'),
            'capacity': node.tags.get('capacity'),
            'operator': node.tags.get('operator'),
            'surface': node.tags.get('surface'),
            'covered': node.tags.get('covered'),
            'lat': float(node.lat),
            'lon': float(node.lon),
            'geometry_type': 'Point'
        })

    # Extract parking ways
    for way in ways:
        if way.tags.get('amenity') != 'parking':
            continue

        parking_type = way.tags.get('parking', 'surface')
        if args.type != 'all' and parking_type != args.type:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if len(coords) < 3:
            continue

        area = calculate_polygon_area(coords)
        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        # Estimate capacity if not provided
        capacity = way.tags.get('capacity')
        if not capacity and area > 0:
            # Rough estimate: 25 sqm per parking space
            capacity = f"~{int(area / 25)}"

        features.append({
            'id': way.id,
            'element_type': 'way',
            'parking': parking_type,
            'name': way.tags.get('name'),
            'access': way.tags.get('access'),
            'fee': way.tags.get('fee'),
            'capacity': capacity,
            'operator': way.tags.get('operator'),
            'surface': way.tags.get('surface'),
            'covered': way.tags.get('covered'),
            'area_sqm': round(area, 1),
            'lat': centroid_lat,
            'lon': centroid_lon,
            'geometry_type': 'Polygon',
            'coordinates': coords
        })

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nParking Facilities: {args.input}")
        print("=" * 60)
        print(f"Total: {len(features)}")

        total_area = sum(f.get('area_sqm', 0) for f in features)
        print(f"Total area: {total_area:,.0f} m² ({total_area/10000:.2f} ha)")

        print("\nBy type:")
        by_type = {}
        for f in features:
            t = f['parking']
            by_type[t] = by_type.get(t, 0) + 1
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count}")

        with_capacity = sum(1 for f in features if f['capacity'])
        with_fee = sum(1 for f in features if f['fee'])
        print(f"\nWith capacity: {with_capacity}")
        print(f"With fee info: {with_fee}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'geojson':
        geojson_features = []
        for f in features:
            if f['geometry_type'] == 'Point':
                geom = {"type": "Point", "coordinates": [f['lon'], f['lat']]}
            else:
                coords = f.get('coordinates', [])
                if coords and coords[0] != coords[-1]:
                    coords.append(coords[0])
                geom = {"type": "Polygon", "coordinates": [coords]}

            props = {k: v for k, v in f.items()
                     if k not in ['lat', 'lon', 'coordinates', 'geometry_type']}
            geojson_features.append({"type": "Feature", "geometry": geom, "properties": props})

        output = {"type": "FeatureCollection", "features": geojson_features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_str = json.dumps([{k: v for k, v in f.items() if k != 'coordinates'}
                                  for f in features], indent=2)

    elif args.format == 'csv':
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['id', 'parking', 'name', 'access', 'fee', 'capacity',
                        'area_sqm', 'lat', 'lon'])
        for f in features:
            writer.writerow([f['id'], f['parking'], f['name'], f['access'], f['fee'],
                           f['capacity'], f.get('area_sqm', ''), f['lat'], f['lon']])
        output_str = buffer.getvalue()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(features)} parking facilities to: {args.output}")
    else:
        print(output_str)

    return 0
