"""Roads command - extract road network with attributes."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


# Road classification
MAJOR_ROADS = frozenset({
    'motorway', 'motorway_link', 'trunk', 'trunk_link',
    'primary', 'primary_link', 'secondary', 'secondary_link'
})

MINOR_ROADS = frozenset({
    'tertiary', 'tertiary_link', 'residential', 'unclassified',
    'living_street', 'service', 'road'
})

PATHS = frozenset({
    'footway', 'cycleway', 'path', 'pedestrian', 'track',
    'bridleway', 'steps', 'corridor'
})


def setup_parser(subparsers):
    """Setup the roads subcommand parser."""
    parser = subparsers.add_parser(
        'roads',
        help='Extract road network with attributes',
        description='Extract road network with length, lanes, surface, and other attributes'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    parser.add_argument(
        '-f', '--format',
        choices=['geojson', 'json', 'csv'],
        default='geojson',
        help='Output format (default: geojson)'
    )
    parser.add_argument(
        '--class',
        dest='road_class',
        choices=['major', 'minor', 'path', 'all'],
        default='all',
        help='Filter by road class'
    )
    parser.add_argument(
        '--type',
        dest='highway_type',
        help='Filter by highway type (e.g., primary, residential)'
    )
    parser.add_argument(
        '--min-length',
        type=float,
        default=0,
        help='Minimum segment length in meters'
    )
    parser.add_argument(
        '--named-only',
        action='store_true',
        help='Only roads with names'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only, no export'
    )

    parser.set_defaults(func=run)
    return parser


def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate distance between two points in meters."""
    R = 6371000  # Earth radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def calculate_way_length(coords):
    """Calculate total length of a way in meters."""
    if len(coords) < 2:
        return 0

    total = 0
    for i in range(len(coords) - 1):
        total += haversine_distance(
            coords[i][0], coords[i][1],
            coords[i + 1][0], coords[i + 1][1]
        )
    return total


def parse_speed(value):
    """Parse maxspeed value to km/h."""
    if not value:
        return None

    value = str(value).strip().lower()

    # Handle mph
    if 'mph' in value:
        try:
            return int(float(value.replace('mph', '').strip()) * 1.60934)
        except ValueError:
            return None

    # Handle km/h or plain number
    value = value.replace('km/h', '').replace('kmh', '').strip()

    try:
        return int(float(value))
    except ValueError:
        return None


def parse_width(value):
    """Parse width value to meters."""
    if not value:
        return None

    value = str(value).strip().lower()

    if value.endswith('m'):
        value = value[:-1].strip()

    try:
        return float(value)
    except ValueError:
        return None


def classify_road(highway_type):
    """Classify road into major/minor/path."""
    if highway_type in MAJOR_ROADS:
        return 'major'
    elif highway_type in MINOR_ROADS:
        return 'minor'
    elif highway_type in PATHS:
        return 'path'
    return 'other'


def extract_road_data(way, node_coords):
    """Extract road data from a way."""
    tags = way.tags
    highway_type = tags.get('highway')

    if not highway_type:
        return None

    # Get coordinates
    coords = []
    for ref in way.node_refs:
        if ref in node_coords:
            coords.append(node_coords[ref])

    if len(coords) < 2:
        return None

    # Calculate length
    length = calculate_way_length(coords)

    # Parse lanes
    lanes = None
    if 'lanes' in tags:
        try:
            lanes = int(tags['lanes'])
        except ValueError:
            pass

    # Parse other attributes
    width = parse_width(tags.get('width'))
    maxspeed = parse_speed(tags.get('maxspeed'))

    # Boolean attributes
    oneway = tags.get('oneway') in ('yes', '1', 'true', '-1')
    lit = tags.get('lit') in ('yes', '1', 'true')

    return {
        'id': way.id,
        'highway': highway_type,
        'road_class': classify_road(highway_type),
        'name': tags.get('name'),
        'ref': tags.get('ref'),  # Road number (e.g., A1, M25)
        'lanes': lanes,
        'width_m': width,
        'surface': tags.get('surface'),
        'maxspeed_kmh': maxspeed,
        'oneway': oneway,
        'lit': lit,
        'sidewalk': tags.get('sidewalk'),
        'cycleway': tags.get('cycleway'),
        'length_m': round(length, 1),
        'coordinates': coords,
        'tags': tags
    }


def run(args):
    """Execute the roads command."""
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

    # Extract roads
    roads = []

    for way in ways:
        if 'highway' not in way.tags:
            continue

        road = extract_road_data(way, node_coords)

        if road is None:
            continue

        # Apply filters
        if args.road_class != 'all':
            if road['road_class'] != args.road_class:
                continue

        if args.highway_type:
            if road['highway'] != args.highway_type:
                continue

        if args.min_length > 0:
            if road['length_m'] < args.min_length:
                continue

        if args.named_only:
            if not road['name']:
                continue

        roads.append(road)

    elapsed = time.time() - start_time

    # Stats mode
    if args.stats:
        total_length = sum(r['length_m'] for r in roads)
        with_name = sum(1 for r in roads if r['name'])
        with_surface = sum(1 for r in roads if r['surface'])
        with_lanes = sum(1 for r in roads if r['lanes'])

        print(f"\nRoad Network Statistics: {args.input}")
        print("=" * 60)
        print(f"Total segments: {len(roads)}")
        print(f"Total length: {total_length/1000:.1f} km")
        print(f"With name: {with_name} ({100*with_name//max(len(roads),1)}%)")
        print(f"With surface: {with_surface} ({100*with_surface//max(len(roads),1)}%)")
        print(f"With lanes: {with_lanes} ({100*with_lanes//max(len(roads),1)}%)")

        # Length by class
        print(f"\nBy road class:")
        for cls in ['major', 'minor', 'path', 'other']:
            cls_roads = [r for r in roads if r['road_class'] == cls]
            cls_length = sum(r['length_m'] for r in cls_roads)
            if cls_roads:
                print(f"  {cls}: {len(cls_roads)} segments, {cls_length/1000:.1f} km")

        # Length by type
        print(f"\nBy highway type:")
        types = {}
        for r in roads:
            t = r['highway']
            if t not in types:
                types[t] = {'count': 0, 'length': 0}
            types[t]['count'] += 1
            types[t]['length'] += r['length_m']

        for t, data in sorted(types.items(), key=lambda x: -x[1]['length'])[:10]:
            print(f"  {t}: {data['count']} segments, {data['length']/1000:.1f} km")

        # Surface breakdown
        surfaces = {}
        for r in roads:
            s = r['surface'] or 'unknown'
            surfaces[s] = surfaces.get(s, 0) + r['length_m']

        print(f"\nBy surface:")
        for s, length in sorted(surfaces.items(), key=lambda x: -x[1])[:8]:
            print(f"  {s}: {length/1000:.1f} km")

        print(f"\nProcessing time: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'geojson':
        output = {
            "type": "FeatureCollection",
            "features": []
        }

        for r in roads:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": r['coordinates']
                },
                "properties": {
                    "id": r['id'],
                    "highway": r['highway'],
                    "road_class": r['road_class'],
                    "name": r['name'],
                    "ref": r['ref'],
                    "lanes": r['lanes'],
                    "width_m": r['width_m'],
                    "surface": r['surface'],
                    "maxspeed_kmh": r['maxspeed_kmh'],
                    "oneway": r['oneway'],
                    "lit": r['lit'],
                    "length_m": r['length_m']
                }
            }
            output["features"].append(feature)

        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_data = []
        for r in roads:
            output_data.append({
                'id': r['id'],
                'highway': r['highway'],
                'road_class': r['road_class'],
                'name': r['name'],
                'ref': r['ref'],
                'lanes': r['lanes'],
                'width_m': r['width_m'],
                'surface': r['surface'],
                'maxspeed_kmh': r['maxspeed_kmh'],
                'oneway': r['oneway'],
                'lit': r['lit'],
                'length_m': r['length_m']
            })
        output_str = json.dumps(output_data, indent=2)

    elif args.format == 'csv':
        import csv
        import io

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            'id', 'highway', 'road_class', 'name', 'ref', 'lanes',
            'width_m', 'surface', 'maxspeed_kmh', 'oneway', 'lit', 'length_m'
        ])

        for r in roads:
            writer.writerow([
                r['id'], r['highway'], r['road_class'], r['name'], r['ref'],
                r['lanes'], r['width_m'], r['surface'], r['maxspeed_kmh'],
                r['oneway'], r['lit'], r['length_m']
            ])

        output_str = buffer.getvalue()

    # Write output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(roads)} road segments to: {args.output}")
    else:
        print(output_str)

    total_km = sum(r['length_m'] for r in roads) / 1000
    print(f"\nRoads extracted: {len(roads)} ({total_km:.1f} km)", file=sys.stderr)
    print(f"Time: {elapsed:.3f}s", file=sys.stderr)

    return 0
