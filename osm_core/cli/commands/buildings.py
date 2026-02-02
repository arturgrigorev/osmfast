"""Buildings command - extract building footprints with height data."""
import argparse
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser
from ...utils.geo_utils import calculate_polygon_area
from ..docs_loader import get_summary, get_description, get_option_help


def setup_parser(subparsers):
    """Setup the buildings subcommand parser."""
    cmd = 'buildings'
    parser = subparsers.add_parser(
        cmd,
        help=get_summary(cmd) or 'Extract building footprints with height data',
        description=get_description(cmd) or 'Extract building footprints with height estimation from levels'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help=get_option_help(cmd, '-o, --output') or 'Output file (default: stdout)')
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv'],
        default='geojson',
        help='Output format (default: geojson)'
    )
    parser.add_argument(
        '--min-height',
        type=float,
        default=0,
        help=get_option_help(cmd, '--min-height') or 'Only buildings >= N meters'
    )
    parser.add_argument(
        '--max-height',
        type=float,
        default=None,
        help=get_option_help(cmd, '--max-height') or 'Only buildings <= N meters'
    )
    parser.add_argument(
        '--floor-height',
        type=float,
        default=3.0,
        help=get_option_help(cmd, '--floor-height') or 'Meters per floor for height estimation (default: 3.0)'
    )
    parser.add_argument(
        '--no-estimate',
        action='store_true',
        help=get_option_help(cmd, '--no-estimate') or 'Do not estimate height from levels'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help=get_option_help(cmd, '--stats') or 'Show statistics only, no export'
    )
    parser.add_argument(
        '--type',
        dest='building_type',
        help=get_option_help(cmd, '--type') or 'Filter by building type (e.g., residential, commercial)'
    )

    parser.set_defaults(func=run)
    return parser


def parse_height(value):
    """Parse height value, handling units."""
    if not value:
        return None

    value = str(value).strip().lower()

    # Remove common units and convert
    if value.endswith('m'):
        value = value[:-1].strip()
    elif value.endswith('ft'):
        try:
            return float(value[:-2].strip()) * 0.3048
        except ValueError:
            return None

    try:
        return float(value)
    except ValueError:
        return None


def extract_building_data(way, node_coords, floor_height=3.0, estimate=True):
    """Extract building data from a way."""
    tags = way.tags

    # Get coordinates
    coords = []
    for ref in way.node_refs:
        if ref in node_coords:
            coords.append(node_coords[ref])

    if len(coords) < 3:
        return None

    # Calculate area
    area = calculate_polygon_area(coords)

    # Determine height
    height = None
    height_source = None

    # Try direct height tags
    for tag in ['height', 'building:height']:
        if tag in tags:
            height = parse_height(tags[tag])
            if height:
                height_source = 'measured'
                break

    # Try levels if no direct height
    levels = None
    if height is None and estimate:
        for tag in ['building:levels', 'levels']:
            if tag in tags:
                try:
                    levels = int(float(tags[tag]))
                    height = levels * floor_height
                    height_source = 'estimated'
                    break
                except ValueError:
                    pass

    # Get roof info
    roof_shape = tags.get('roof:shape', tags.get('building:roof:shape'))
    roof_height = parse_height(tags.get('roof:height'))

    return {
        'id': way.id,
        'building': tags.get('building', 'yes'),
        'name': tags.get('name'),
        'height_m': height,
        'height_source': height_source,
        'levels': levels,
        'roof_shape': roof_shape,
        'roof_height_m': roof_height,
        'area_sqm': round(area, 1) if area else None,
        'coordinates': coords,
        'tags': tags
    }


def run(args):
    """Execute the buildings command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse the file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Build node coordinate lookup
    node_coords = {}
    for node in nodes:
        node_coords[node.id] = [float(node.lon), float(node.lat)]

    # Extract buildings
    buildings = []
    estimate = not args.no_estimate

    for way in ways:
        if 'building' not in way.tags:
            continue

        # Filter by type if specified
        if args.building_type:
            if way.tags.get('building') != args.building_type:
                continue

        building = extract_building_data(
            way, node_coords,
            floor_height=args.floor_height,
            estimate=estimate
        )

        if building is None:
            continue

        # Apply height filters
        if args.min_height > 0:
            if building['height_m'] is None or building['height_m'] < args.min_height:
                continue

        if args.max_height is not None:
            if building['height_m'] is None or building['height_m'] > args.max_height:
                continue

        buildings.append(building)

    elapsed = time.time() - start_time

    # Stats mode
    if args.stats:
        with_height = sum(1 for b in buildings if b['height_m'] is not None)
        with_levels = sum(1 for b in buildings if b['levels'] is not None)
        heights = [b['height_m'] for b in buildings if b['height_m'] is not None]
        areas = [b['area_sqm'] for b in buildings if b['area_sqm'] is not None]

        print(f"\nBuilding Statistics: {args.input}")
        print("=" * 60)
        print(f"Total buildings: {len(buildings)}")
        print(f"With height data: {with_height} ({100*with_height//max(len(buildings),1)}%)")
        print(f"With levels data: {with_levels} ({100*with_levels//max(len(buildings),1)}%)")

        if heights:
            print(f"\nHeight range: {min(heights):.1f}m - {max(heights):.1f}m")
            print(f"Average height: {sum(heights)/len(heights):.1f}m")

        if areas:
            print(f"\nTotal footprint: {sum(areas):,.0f} m²")
            print(f"Average footprint: {sum(areas)/len(areas):,.1f} m²")

        # Building types breakdown
        types = {}
        for b in buildings:
            t = b['building']
            types[t] = types.get(t, 0) + 1

        print(f"\nBuilding types:")
        for t, count in sorted(types.items(), key=lambda x: -x[1])[:10]:
            print(f"  {t}: {count}")

        print(f"\nProcessing time: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'geojson':
        output = {
            "type": "FeatureCollection",
            "features": []
        }

        for b in buildings:
            coords = b['coordinates']
            if coords[0] != coords[-1]:
                coords.append(coords[0])  # Close polygon

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords]
                },
                "properties": {
                    "id": b['id'],
                    "building": b['building'],
                    "name": b['name'],
                    "height_m": b['height_m'],
                    "height_source": b['height_source'],
                    "levels": b['levels'],
                    "roof_shape": b['roof_shape'],
                    "area_sqm": b['area_sqm']
                }
            }
            output["features"].append(feature)

        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_data = []
        for b in buildings:
            output_data.append({
                'id': b['id'],
                'building': b['building'],
                'name': b['name'],
                'height_m': b['height_m'],
                'height_source': b['height_source'],
                'levels': b['levels'],
                'roof_shape': b['roof_shape'],
                'area_sqm': b['area_sqm'],
                'centroid': [
                    sum(c[0] for c in b['coordinates']) / len(b['coordinates']),
                    sum(c[1] for c in b['coordinates']) / len(b['coordinates'])
                ]
            })
        output_str = json.dumps(output_data, indent=2)

    elif args.format == 'csv':
        import csv
        import io

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            'id', 'building', 'name', 'height_m', 'height_source',
            'levels', 'roof_shape', 'area_sqm', 'centroid_lon', 'centroid_lat'
        ])

        for b in buildings:
            centroid_lon = sum(c[0] for c in b['coordinates']) / len(b['coordinates'])
            centroid_lat = sum(c[1] for c in b['coordinates']) / len(b['coordinates'])
            writer.writerow([
                b['id'], b['building'], b['name'], b['height_m'],
                b['height_source'], b['levels'], b['roof_shape'],
                b['area_sqm'], round(centroid_lon, 7), round(centroid_lat, 7)
            ])

        output_str = buffer.getvalue()

    # Write output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(buildings)} buildings to: {args.output}")
    else:
        print(output_str)

    print(f"\nBuildings extracted: {len(buildings)}", file=sys.stderr)
    print(f"Time: {elapsed:.3f}s", file=sys.stderr)

    return 0
