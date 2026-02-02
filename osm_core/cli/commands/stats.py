"""Stats command implementation."""
import json
import os
import sys
import time
import xml.sax
from collections import defaultdict, Counter
from typing import Dict, Any

from osm_core.models.statistics import OSMStats


class OSMStatsHandler(xml.sax.ContentHandler):
    """SAX handler for collecting OSM statistics."""

    def __init__(self):
        self.stats = OSMStats()
        self.current_element = None
        self.current_tags = {}

    def startElement(self, name, attrs):
        if name == 'node':
            self.stats.nodes += 1
            self.current_element = 'node'
            self.current_tags = {}

            # Update geographic bounds
            lat = float(attrs.get('lat', 0))
            lon = float(attrs.get('lon', 0))
            self.stats.update_bounds(lat, lon)

        elif name == 'way':
            self.stats.ways += 1
            self.current_element = 'way'
            self.current_tags = {}

        elif name == 'relation':
            self.stats.relations += 1
            self.current_element = 'relation'
            self.current_tags = {}

        elif name == 'tag':
            key = attrs.get('k', '')
            value = attrs.get('v', '')

            self.stats.unique_keys.add(key)
            self.stats.unique_values.add(value)
            self.stats.key_usage[key] += 1
            self.current_tags[key] = value

    def endElement(self, name):
        if name in ('node', 'way', 'relation'):
            # Process collected tags
            for key, value in self.current_tags.items():
                if self.current_element == 'node':
                    self.stats.node_tags[key] += 1
                elif self.current_element == 'way':
                    self.stats.way_tags[key] += 1

                # Track specific types
                if key == 'highway':
                    self.stats.highway_types[value] += 1
                elif key == 'amenity':
                    self.stats.amenity_types[value] += 1
                elif key == 'building':
                    self.stats.building_types[value] += 1

            self.current_element = None
            self.current_tags = {}


def analyze_osm_file(file_path: str) -> OSMStats:
    """Analyze an OSM file and return statistics.

    Args:
        file_path: Path to OSM file

    Returns:
        OSMStats object with collected statistics
    """
    start_time = time.time()

    handler = OSMStatsHandler()
    parser = xml.sax.make_parser()
    parser.setContentHandler(handler)
    parser.parse(file_path)

    stats = handler.stats
    stats.file_size = os.path.getsize(file_path)
    stats.processing_time = time.time() - start_time

    # Calculate popular tags
    stats.popular_tags = sorted(
        stats.key_usage.items(),
        key=lambda x: x[1],
        reverse=True
    )[:50]

    return stats


def cmd_stats(args) -> int:
    """Handle stats command.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    input_file = args.input_file

    if not os.path.exists(input_file):
        print(f"osmfast: error: File not found: {input_file}", file=sys.stderr)
        return 3

    # Analyze file
    stats = analyze_osm_file(input_file)

    # Output based on format
    if args.json:
        print(json.dumps(stats.to_dict(), indent=2, default=str))
    elif args.summary:
        _print_summary(stats, input_file)
    else:
        _print_detailed(stats, input_file, suggest_bbox=args.suggest_bbox)

    return 0


def _print_summary(stats: OSMStats, file_path: str) -> None:
    """Print brief summary."""
    print(f"{file_path}: {stats.nodes:,} nodes, {stats.ways:,} ways, "
          f"{stats.relations:,} relations ({stats.total_elements:,} total)")


def _print_detailed(stats: OSMStats, file_path: str,
                    suggest_bbox: bool = False) -> None:
    """Print detailed statistics."""
    print("=" * 70)
    print(f"OSM File Statistics: {file_path}")
    print("=" * 70)

    print(f"\nFile size: {stats.file_size:,} bytes")
    print(f"Processing time: {stats.processing_time:.3f}s")
    print(f"Processing rate: {stats.get_processing_rate():,.0f} elements/sec")

    print(f"\nElements:")
    print(f"  Nodes: {stats.nodes:,}")
    print(f"  Ways: {stats.ways:,}")
    print(f"  Relations: {stats.relations:,}")
    print(f"  Total: {stats.total_elements:,}")

    if stats.has_valid_bounds:
        print(f"\nGeographic Bounds:")
        print(f"  Latitude: {stats.min_lat:.6f} to {stats.max_lat:.6f}")
        print(f"  Longitude: {stats.min_lon:.6f} to {stats.max_lon:.6f}")
        center = stats.center
        print(f"  Center: {center[0]:.6f}, {center[1]:.6f}")

        if suggest_bbox:
            print(f"\nSuggested --bbox argument:")
            print(f"  --bbox {stats.max_lat:.6f} {stats.min_lon:.6f} "
                  f"{stats.min_lat:.6f} {stats.max_lon:.6f}")

    print(f"\nTag Statistics:")
    print(f"  Unique keys: {len(stats.unique_keys):,}")
    print(f"  Unique values: {len(stats.unique_values):,}")

    if stats.popular_tags:
        print(f"\nTop 10 Tag Keys:")
        for key, count in stats.popular_tags[:10]:
            print(f"  {key}: {count:,}")

    if stats.highway_types:
        print(f"\nHighway Types:")
        for htype, count in sorted(stats.highway_types.items(),
                                    key=lambda x: -x[1])[:10]:
            print(f"  {htype}: {count:,}")

    if stats.amenity_types:
        print(f"\nAmenity Types:")
        for atype, count in sorted(stats.amenity_types.items(),
                                    key=lambda x: -x[1])[:10]:
            print(f"  {atype}: {count:,}")

    if stats.building_types:
        print(f"\nBuilding Types:")
        for btype, count in sorted(stats.building_types.items(),
                                    key=lambda x: -x[1])[:10]:
            print(f"  {btype}: {count:,}")

    print("=" * 70)
