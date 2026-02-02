"""Bbox command - calculate and manipulate bounding boxes."""
import argparse
import json
import math
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the bbox subcommand parser."""
    parser = subparsers.add_parser(
        'bbox',
        help='Calculate and manipulate bounding boxes',
        description='Calculate bounding box of OSM data or manipulate existing bbox'
    )

    parser.add_argument('input', nargs='?', help='Input OSM file (optional for --from-* options)')
    parser.add_argument('-o', '--output', help='Output file')

    # Bbox sources
    source_group = parser.add_argument_group('bbox source')
    source_group.add_argument(
        '--from-coords',
        nargs=4,
        type=float,
        metavar=('MIN_LON', 'MIN_LAT', 'MAX_LON', 'MAX_LAT'),
        help='Create bbox from coordinates'
    )
    source_group.add_argument(
        '--from-center',
        nargs=2,
        type=float,
        metavar=('LAT', 'LON'),
        help='Create bbox from center point (use with --radius)'
    )
    source_group.add_argument(
        '--radius',
        type=float,
        help='Radius in meters for --from-center'
    )

    # Modifications
    mod_group = parser.add_argument_group('modifications')
    mod_group.add_argument(
        '--buffer',
        type=float,
        help='Add buffer around bbox (in meters)'
    )
    mod_group.add_argument(
        '--expand',
        type=float,
        help='Expand bbox by percentage (e.g., 10 for 10%%)'
    )
    mod_group.add_argument(
        '--round',
        type=int,
        help='Round coordinates to N decimal places'
    )

    # Output options
    output_group = parser.add_argument_group('output options')
    output_group.add_argument(
        '-f', '--format',
        choices=['text', 'json', 'geojson', 'osm', 'overpass'],
        default='text',
        help='Output format (default: text)'
    )
    output_group.add_argument(
        '--copy',
        action='store_true',
        help='Copy bbox to clipboard (if pyperclip available)'
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


def meters_to_degrees_lat(meters):
    """Convert meters to degrees latitude."""
    return meters / 111320


def meters_to_degrees_lon(meters, lat):
    """Convert meters to degrees longitude at given latitude."""
    return meters / (111320 * math.cos(math.radians(lat)))


def run(args):
    """Execute the bbox command."""
    start_time = time.time()

    bbox = None  # [min_lon, min_lat, max_lon, max_lat]

    # Source 1: From coordinates
    if args.from_coords:
        bbox = args.from_coords

    # Source 2: From center + radius
    elif args.from_center:
        if not args.radius:
            print("Error: --radius required with --from-center", file=sys.stderr)
            return 1

        lat, lon = args.from_center
        radius = args.radius

        lat_delta = meters_to_degrees_lat(radius)
        lon_delta = meters_to_degrees_lon(radius, lat)

        bbox = [lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta]

    # Source 3: From OSM file
    elif args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: File not found: {args.input}", file=sys.stderr)
            return 1

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(input_path))

        if not nodes:
            print("Error: No nodes found in file", file=sys.stderr)
            return 1

        lats = [float(n.lat) for n in nodes]
        lons = [float(n.lon) for n in nodes]
        bbox = [min(lons), min(lats), max(lons), max(lats)]

    else:
        print("Error: Provide input file or use --from-coords/--from-center", file=sys.stderr)
        return 1

    # Apply modifications
    if args.buffer:
        center_lat = (bbox[1] + bbox[3]) / 2
        lat_buffer = meters_to_degrees_lat(args.buffer)
        lon_buffer = meters_to_degrees_lon(args.buffer, center_lat)
        bbox = [
            bbox[0] - lon_buffer,
            bbox[1] - lat_buffer,
            bbox[2] + lon_buffer,
            bbox[3] + lat_buffer
        ]

    if args.expand:
        factor = args.expand / 100
        lat_span = bbox[3] - bbox[1]
        lon_span = bbox[2] - bbox[0]
        bbox = [
            bbox[0] - lon_span * factor / 2,
            bbox[1] - lat_span * factor / 2,
            bbox[2] + lon_span * factor / 2,
            bbox[3] + lat_span * factor / 2
        ]

    if args.round is not None:
        bbox = [round(x, args.round) for x in bbox]

    # Calculate dimensions
    center_lat = (bbox[1] + bbox[3]) / 2
    center_lon = (bbox[0] + bbox[2]) / 2
    width_m = haversine_distance(bbox[0], center_lat, bbox[2], center_lat)
    height_m = haversine_distance(center_lon, bbox[1], center_lon, bbox[3])

    elapsed = time.time() - start_time

    # Generate output
    if args.format == 'text':
        output_str = f"""Bounding Box
============
Min (SW): {bbox[1]:.6f}, {bbox[0]:.6f}
Max (NE): {bbox[3]:.6f}, {bbox[2]:.6f}
Center:   {center_lat:.6f}, {center_lon:.6f}
Size:     {width_m/1000:.2f} km × {height_m/1000:.2f} km

Formats:
  [min_lon, min_lat, max_lon, max_lat]: [{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]
  osmfast: --bbox {bbox[3]} {bbox[0]} {bbox[1]} {bbox[2]}
  overpass: ({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]})
"""

    elif args.format == 'json':
        output = {
            'bbox': bbox,
            'min_lon': bbox[0],
            'min_lat': bbox[1],
            'max_lon': bbox[2],
            'max_lat': bbox[3],
            'center': [center_lon, center_lat],
            'width_m': round(width_m, 1),
            'height_m': round(height_m, 1)
        }
        output_str = json.dumps(output, indent=2)

    elif args.format == 'geojson':
        output = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [bbox[0], bbox[1]],
                    [bbox[2], bbox[1]],
                    [bbox[2], bbox[3]],
                    [bbox[0], bbox[3]],
                    [bbox[0], bbox[1]]
                ]]
            },
            "properties": {
                "bbox": bbox,
                "center": [center_lon, center_lat],
                "width_m": round(width_m, 1),
                "height_m": round(height_m, 1)
            }
        }
        output_str = json.dumps(output, indent=2)

    elif args.format == 'osm':
        # osmosis/osmium bbox format
        output_str = f"--bbox {bbox[3]},{bbox[0]},{bbox[1]},{bbox[2]}"

    elif args.format == 'overpass':
        # Overpass API bbox format
        output_str = f"({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]})"

    # Output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Bbox written to {args.output}")
    else:
        print(output_str)

    # Copy to clipboard
    if args.copy:
        try:
            import pyperclip
            clip_text = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
            pyperclip.copy(clip_text)
            print(f"\nCopied to clipboard: {clip_text}")
        except ImportError:
            print("\nNote: Install pyperclip for clipboard support", file=sys.stderr)

    return 0
