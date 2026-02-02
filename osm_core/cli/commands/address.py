"""Address command - extract address data."""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


def setup_parser(subparsers):
    """Setup the address subcommand parser."""
    parser = subparsers.add_parser(
        'address',
        help='Extract address data',
        description='Extract structured address information from OSM'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument(
        '-f', '--format',
        choices=['csv', 'json', 'geojson'],
        default='csv',
        help='Output format (default: csv)'
    )
    parser.add_argument(
        '--complete-only',
        action='store_true',
        help='Only addresses with street and housenumber'
    )
    parser.add_argument(
        '--include-pois',
        action='store_true',
        help='Include POI names with addresses'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics only'
    )

    parser.set_defaults(func=run)
    return parser


def extract_address(element, element_type, lat=None, lon=None):
    """Extract address from element tags."""
    tags = element.tags

    # Check for address tags
    has_addr = any(k.startswith('addr:') for k in tags)
    if not has_addr:
        return None

    addr = {
        'id': element.id,
        'type': element_type,
        'housenumber': tags.get('addr:housenumber'),
        'housename': tags.get('addr:housename'),
        'street': tags.get('addr:street'),
        'unit': tags.get('addr:unit'),
        'city': tags.get('addr:city'),
        'suburb': tags.get('addr:suburb'),
        'postcode': tags.get('addr:postcode'),
        'state': tags.get('addr:state'),
        'country': tags.get('addr:country'),
        'full': tags.get('addr:full'),
        'name': tags.get('name'),
        'lat': lat,
        'lon': lon
    }

    return addr


def run(args):
    """Execute the address command."""
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

    addresses = []

    # Extract from nodes
    for node in nodes:
        addr = extract_address(node, 'node', float(node.lat), float(node.lon))
        if addr:
            addresses.append(addr)

    # Extract from ways
    for way in ways:
        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if coords:
            centroid_lon = sum(c[0] for c in coords) / len(coords)
            centroid_lat = sum(c[1] for c in coords) / len(coords)
            addr = extract_address(way, 'way', centroid_lat, centroid_lon)
            if addr:
                addresses.append(addr)

    # Apply filters
    if args.complete_only:
        addresses = [a for a in addresses if a['street'] and a['housenumber']]

    if not args.include_pois:
        # Keep name only for address display
        pass

    elapsed = time.time() - start_time

    # Stats mode
    if args.stats:
        print(f"\nAddress Statistics: {args.input}")
        print("=" * 60)
        print(f"Total addresses: {len(addresses)}")

        with_street = sum(1 for a in addresses if a['street'])
        with_number = sum(1 for a in addresses if a['housenumber'])
        with_postcode = sum(1 for a in addresses if a['postcode'])
        with_city = sum(1 for a in addresses if a['city'])
        complete = sum(1 for a in addresses if a['street'] and a['housenumber'])

        print(f"\nCompleteness:")
        print(f"  With street: {with_street} ({100*with_street//max(len(addresses),1)}%)")
        print(f"  With housenumber: {with_number} ({100*with_number//max(len(addresses),1)}%)")
        print(f"  With postcode: {with_postcode} ({100*with_postcode//max(len(addresses),1)}%)")
        print(f"  With city: {with_city} ({100*with_city//max(len(addresses),1)}%)")
        print(f"  Complete (street+number): {complete} ({100*complete//max(len(addresses),1)}%)")

        # Top streets
        streets = {}
        for a in addresses:
            if a['street']:
                streets[a['street']] = streets.get(a['street'], 0) + 1

        print(f"\nTop streets:")
        for street, count in sorted(streets.items(), key=lambda x: -x[1])[:10]:
            print(f"  {street}: {count}")

        print(f"\nTime: {elapsed:.3f}s")
        return 0

    # Generate output
    if args.format == 'csv':
        import io
        buffer = io.StringIO()
        fieldnames = ['id', 'type', 'housenumber', 'street', 'unit', 'city',
                      'suburb', 'postcode', 'state', 'country', 'name', 'lat', 'lon']
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(addresses)
        output_str = buffer.getvalue()

    elif args.format == 'json':
        output_str = json.dumps(addresses, indent=2)

    elif args.format == 'geojson':
        features = []
        for a in addresses:
            if a['lat'] and a['lon']:
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [a['lon'], a['lat']]
                    },
                    "properties": {k: v for k, v in a.items() if k not in ['lat', 'lon']}
                })
        output = {"type": "FeatureCollection", "features": features}
        output_str = json.dumps(output, indent=2)

    # Output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"Saved {len(addresses)} addresses to: {args.output}")
    else:
        print(output_str)

    print(f"\nAddresses extracted: {len(addresses)}", file=sys.stderr)
    print(f"Time: {elapsed:.3f}s", file=sys.stderr)

    return 0
