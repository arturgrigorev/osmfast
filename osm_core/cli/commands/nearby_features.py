"""Nearby command - find features near other features."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the nearby subcommand parser."""
    parser = subparsers.add_parser(
        'nearby',
        help='Find features near other features',
        description='Find target features within radius of source features'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '--source',
        required=True,
        help='Source features filter (e.g., amenity=hospital)'
    )
    parser.add_argument(
        '--target',
        required=True,
        help='Target features filter (e.g., amenity=pharmacy)'
    )
    parser.add_argument(
        '--radius', '-r',
        required=True,
        help='Search radius (e.g., 500m, 1km)'
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


def parse_filter(filter_str):
    """Parse filter string."""
    if '=' not in filter_str:
        return filter_str, '*'
    key, value = filter_str.split('=', 1)
    return key.strip(), value.strip()


def matches_filter(tags, key, value):
    """Check if tags match filter."""
    if key not in tags:
        return False
    if value == '*':
        return True
    if ',' in value:
        return tags[key] in [v.strip() for v in value.split(',')]
    return tags[key] == value


def parse_radius(radius_str):
    """Parse radius string to meters."""
    radius_str = radius_str.strip().lower()
    if radius_str.endswith('km'):
        return float(radius_str[:-2]) * 1000
    elif radius_str.endswith('m'):
        return float(radius_str[:-1])
    else:
        return float(radius_str)


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
    """Execute the nearby command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    try:
        radius = parse_radius(args.radius)
    except ValueError:
        print(f"Error: Invalid radius format: {args.radius}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse filters
    source_key, source_value = parse_filter(args.source)
    target_key, target_value = parse_filter(args.target)

    # Parse file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    node_coords = {}
    for node in nodes:
        node_coords[node.id] = [float(node.lon), float(node.lat)]

    # Collect source and target features
    sources = []
    targets = []

    for node in nodes:
        if matches_filter(node.tags, source_key, source_value):
            sources.append({
                'id': node.id,
                'type': 'node',
                'name': node.tags.get('name'),
                'lat': float(node.lat),
                'lon': float(node.lon),
                'tags': node.tags
            })
        if matches_filter(node.tags, target_key, target_value):
            targets.append({
                'id': node.id,
                'type': 'node',
                'name': node.tags.get('name'),
                'lat': float(node.lat),
                'lon': float(node.lon),
                'tags': node.tags
            })

    for way in ways:
        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if not coords:
            continue
        centroid_lon = sum(c[0] for c in coords) / len(coords)
        centroid_lat = sum(c[1] for c in coords) / len(coords)

        if matches_filter(way.tags, source_key, source_value):
            sources.append({
                'id': way.id,
                'type': 'way',
                'name': way.tags.get('name'),
                'lat': centroid_lat,
                'lon': centroid_lon,
                'tags': way.tags
            })
        if matches_filter(way.tags, target_key, target_value):
            targets.append({
                'id': way.id,
                'type': 'way',
                'name': way.tags.get('name'),
                'lat': centroid_lat,
                'lon': centroid_lon,
                'tags': way.tags
            })

    # Find nearby pairs
    pairs = []
    for source in sources:
        nearby_targets = []
        for target in targets:
            dist = haversine_distance(source['lon'], source['lat'],
                                     target['lon'], target['lat'])
            if dist <= radius:
                nearby_targets.append({
                    'target': target,
                    'distance_m': round(dist, 1)
                })

        # Sort by distance
        nearby_targets.sort(key=lambda x: x['distance_m'])

        pairs.append({
            'source': source,
            'nearby_count': len(nearby_targets),
            'nearby': nearby_targets
        })

    elapsed = time.time() - start_time

    if args.stats:
        print(f"\nNearby Analysis: {args.input}")
        print("=" * 60)
        print(f"Source filter: {args.source}")
        print(f"Target filter: {args.target}")
        print(f"Radius: {args.radius}")
        print(f"\nSources: {len(sources)}")
        print(f"Targets: {len(targets)}")

        total_nearby = sum(p['nearby_count'] for p in pairs)
        sources_with_nearby = sum(1 for p in pairs if p['nearby_count'] > 0)

        print(f"\nResults:")
        print(f"  Total pairs found: {total_nearby}")
        print(f"  Sources with nearby targets: {sources_with_nearby} ({100*sources_with_nearby//max(len(sources),1)}%)")

        if pairs:
            avg_nearby = total_nearby / len(pairs)
            max_nearby = max(p['nearby_count'] for p in pairs)
            print(f"  Average nearby per source: {avg_nearby:.1f}")
            print(f"  Maximum nearby: {max_nearby}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'geojson':
        features = []
        for pair in pairs:
            source = pair['source']
            # Add source point
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [source['lon'], source['lat']]},
                "properties": {
                    "role": "source",
                    "id": source['id'],
                    "name": source['name'],
                    "nearby_count": pair['nearby_count']
                }
            })
            # Add lines to nearby targets
            for nearby in pair['nearby']:
                target = nearby['target']
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [source['lon'], source['lat']],
                            [target['lon'], target['lat']]
                        ]
                    },
                    "properties": {
                        "source_id": source['id'],
                        "source_name": source['name'],
                        "target_id": target['id'],
                        "target_name": target['name'],
                        "distance_m": nearby['distance_m']
                    }
                })

        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    elif args.format == 'json':
        output_str = json.dumps(pairs, indent=2, default=str)

    elif args.format == 'csv':
        import csv
        import io
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['source_id', 'source_name', 'target_id', 'target_name', 'distance_m'])
        for pair in pairs:
            source = pair['source']
            for nearby in pair['nearby']:
                target = nearby['target']
                writer.writerow([source['id'], source['name'], target['id'],
                               target['name'], nearby['distance_m']])
        output_str = buffer.getvalue()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved results to: {args.output}")
    else:
        print(output_str)

    return 0
