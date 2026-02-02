#!/usr/bin/env python3
"""
OSMStats - OSM File Statistics and Analysis Tool
Compatible with osmosis osmstats functionality for validating OSM extracts.

Usage: python osmstats.py <osm_file>
"""

import os
import sys
import re
import time
import xml.sax
from collections import defaultdict, Counter
from typing import Dict, Any, List, Set, Tuple
from dataclasses import dataclass


@dataclass
class OSMStats:
    """Statistics for an OSM file."""
    nodes: int = 0
    ways: int = 0
    relations: int = 0
    total_elements: int = 0
    
    # Tag statistics
    unique_keys: Set[str] = None
    unique_values: Set[str] = None
    key_usage: Dict[str, int] = None
    popular_tags: List[Tuple[str, int]] = None
    
    # Geographic bounds
    min_lat: float = 90.0
    max_lat: float = -90.0
    min_lon: float = 180.0
    max_lon: float = -180.0
    
    # Element type breakdowns
    node_tags: Dict[str, int] = None
    way_tags: Dict[str, int] = None
    highway_types: Dict[str, int] = None
    amenity_types: Dict[str, int] = None
    building_types: Dict[str, int] = None
    
    # File metadata
    file_size: int = 0
    processing_time: float = 0.0
    
    def __post_init__(self):
        if self.unique_keys is None:
            self.unique_keys = set()
        if self.unique_values is None:
            self.unique_values = set()
        if self.key_usage is None:
            self.key_usage = defaultdict(int)
        if self.popular_tags is None:
            self.popular_tags = []
        if self.node_tags is None:
            self.node_tags = defaultdict(int)
        if self.way_tags is None:
            self.way_tags = defaultdict(int)
        if self.highway_types is None:
            self.highway_types = defaultdict(int)
        if self.amenity_types is None:
            self.amenity_types = defaultdict(int)
        if self.building_types is None:
            self.building_types = defaultdict(int)


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
            self.stats.min_lat = min(self.stats.min_lat, lat)
            self.stats.max_lat = max(self.stats.max_lat, lat)
            self.stats.min_lon = min(self.stats.min_lon, lon)
            self.stats.max_lon = max(self.stats.max_lon, lon)
            
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
            
            if key and value:
                self.current_tags[key] = value
                self.stats.unique_keys.add(key)
                self.stats.unique_values.add(value)
                self.stats.key_usage[key] += 1
                
                # Track specific tag categories
                if key == 'highway':
                    self.stats.highway_types[value] += 1
                elif key == 'amenity':
                    self.stats.amenity_types[value] += 1
                elif key == 'building':
                    self.stats.building_types[value] += 1
    
    def endElement(self, name):
        if name in ['node', 'way', 'relation']:
            # Store tag statistics for this element
            if self.current_element == 'node' and self.current_tags:
                for key in self.current_tags:
                    self.stats.node_tags[key] += 1
            elif self.current_element == 'way' and self.current_tags:
                for key in self.current_tags:
                    self.stats.way_tags[key] += 1
            
            self.current_element = None
            self.current_tags = {}


def analyze_osm_file(file_path: str) -> OSMStats:
    """Analyze an OSM file and return comprehensive statistics."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"OSM file not found: {file_path}")
    
    start_time = time.time()
    
    # Get file size
    file_size = os.path.getsize(file_path)
    
    # Parse file with SAX
    handler = OSMStatsHandler()
    parser = xml.sax.make_parser()
    parser.setContentHandler(handler)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            parser.parse(f)
    except xml.sax.SAXException as e:
        print(f"Warning: XML parsing error: {e}")
        # Try with error recovery
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Clean up common XML issues
                content = re.sub(r'&(?![a-zA-Z0-9#];)', '&amp;', content)
                parser.parseString(content)
        except Exception as e2:
            raise RuntimeError(f"Failed to parse OSM file: {e2}")
    
    processing_time = time.time() - start_time
    
    # Finalize statistics
    stats = handler.stats
    stats.total_elements = stats.nodes + stats.ways + stats.relations
    stats.file_size = file_size
    stats.processing_time = processing_time
    
    # Generate popular tags list
    stats.popular_tags = sorted(stats.key_usage.items(), key=lambda x: x[1], reverse=True)[:20]
    
    return stats


def print_detailed_stats(stats: OSMStats, file_path: str):
    """Print detailed statistics in osmosis osmstats format."""
    print("=" * 80)
    print(f"OSM File Statistics: {os.path.basename(file_path)}")
    print("=" * 80)
    print()
    
    # Basic element counts
    print("ELEMENT COUNTS:")
    print("-" * 40)
    print(f"Nodes:      {stats.nodes:>10,}")
    print(f"Ways:       {stats.ways:>10,}")  
    print(f"Relations:  {stats.relations:>10,}")
    print(f"Total:      {stats.total_elements:>10,}")
    print()
    
    # File information
    print("FILE INFORMATION:")
    print("-" * 40)
    print(f"File size:  {stats.file_size:>10,} bytes ({stats.file_size/1024/1024:.2f} MB)")
    print(f"Processing: {stats.processing_time:>10.3f} seconds")
    print(f"Rate:       {stats.total_elements/stats.processing_time:>10.1f} elements/sec")
    print()
    
    # Geographic bounds
    if stats.nodes > 0:
        print("GEOGRAPHIC BOUNDS:")
        print("-" * 40)
        print(f"Latitude:   {stats.min_lat:>10.6f} to {stats.max_lat:>10.6f}")
        print(f"Longitude:  {stats.min_lon:>10.6f} to {stats.max_lon:>10.6f}")
        center_lat = (stats.min_lat + stats.max_lat) / 2
        center_lon = (stats.min_lon + stats.max_lon) / 2
        print(f"Center:     {center_lat:>10.6f}, {center_lon:>10.6f}")
        
        # Calculate bounding box suggestions
        lat_range = stats.max_lat - stats.min_lat
        lon_range = stats.max_lon - stats.min_lon
        
        # 20% center area
        center_20_lat_margin = lat_range * 0.4  # 40% margin on each side = 20% center
        center_20_lon_margin = lon_range * 0.4
        center_20_top = center_lat + (lat_range * 0.1)  # 10% above center
        center_20_bottom = center_lat - (lat_range * 0.1)  # 10% below center
        center_20_left = center_lon - (lon_range * 0.1)  # 10% left of center
        center_20_right = center_lon + (lon_range * 0.1)  # 10% right of center
        
        print()
        print("BOUNDING BOX SUGGESTIONS:")
        print("-" * 40)
        print(f"Full area:  --bounding-box {stats.max_lat:.6f} {stats.min_lon:.6f} {stats.min_lat:.6f} {stats.max_lon:.6f}")
        print(f"Center 20%: --bounding-box {center_20_top:.6f} {center_20_left:.6f} {center_20_bottom:.6f} {center_20_right:.6f}")
        print(f"Center 50%: --bounding-box {center_lat + lat_range*0.125:.6f} {center_lon - lon_range*0.125:.6f} {center_lat - lat_range*0.125:.6f} {center_lon + lon_range*0.125:.6f}")
        print()
    
    # Tag statistics
    print("TAG STATISTICS:")
    print("-" * 40)
    print(f"Unique keys:   {len(stats.unique_keys):>8,}")
    print(f"Unique values: {len(stats.unique_values):>8,}")
    print(f"Total tags:    {sum(stats.key_usage.values()):>8,}")
    print()
    
    # Popular tags
    if stats.popular_tags:
        print("MOST POPULAR TAGS:")
        print("-" * 40)
        for tag, count in stats.popular_tags[:15]:
            print(f"{tag:.<30} {count:>8,}")
        print()
    
    # Highway types
    if stats.highway_types:
        print("HIGHWAY TYPES:")
        print("-" * 40)
        total_highways = sum(stats.highway_types.values())
        for highway_type, count in sorted(stats.highway_types.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = (count / total_highways) * 100
            print(f"{highway_type:.<25} {count:>6,} ({percentage:>5.1f}%)")
        print(f"{'Total highways':.<25} {total_highways:>6,}")
        print()
    
    # Amenity types
    if stats.amenity_types:
        print("AMENITY TYPES:")
        print("-" * 40)
        total_amenities = sum(stats.amenity_types.values())
        for amenity_type, count in sorted(stats.amenity_types.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = (count / total_amenities) * 100
            print(f"{amenity_type:.<25} {count:>6,} ({percentage:>5.1f}%)")
        print(f"{'Total amenities':.<25} {total_amenities:>6,}")
        print()
    
    # Building types
    if stats.building_types:
        print("BUILDING TYPES:")
        print("-" * 40)
        total_buildings = sum(stats.building_types.values())
        for building_type, count in sorted(stats.building_types.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = (count / total_buildings) * 100
            print(f"{building_type:.<25} {count:>6,} ({percentage:>5.1f}%)")
        print(f"{'Total buildings':.<25} {total_buildings:>6,}")
        print()
    
    # Element tag distribution
    print("TAG DISTRIBUTION:")
    print("-" * 40)
    
    if stats.node_tags:
        top_node_tags = sorted(stats.node_tags.items(), key=lambda x: x[1], reverse=True)[:5]
        print("Top node tags:")
        for tag, count in top_node_tags:
            print(f"  {tag}: {count:,}")
    
    if stats.way_tags:
        top_way_tags = sorted(stats.way_tags.items(), key=lambda x: x[1], reverse=True)[:5]
        print("Top way tags:")
        for tag, count in top_way_tags:
            print(f"  {tag}: {count:,}")
    
    print()
    print("=" * 80)


def print_summary_stats(stats: OSMStats, file_path: str):
    """Print brief summary statistics."""
    print(f"File: {os.path.basename(file_path)}")
    print(f"Elements: {stats.nodes:,} nodes, {stats.ways:,} ways, {stats.relations:,} relations")
    print(f"Tags: {len(stats.unique_keys):,} unique keys, {sum(stats.key_usage.values()):,} total tags")
    if stats.nodes > 0:
        print(f"Bounds: {stats.min_lat:.4f},{stats.min_lon:.4f} to {stats.max_lat:.4f},{stats.max_lon:.4f}")
    print(f"Size: {stats.file_size/1024/1024:.2f} MB, processed in {stats.processing_time:.3f}s")


def main():
    """Main CLI interface for osmstats."""
    if len(sys.argv) < 2:
        print("Usage: python osmstats.py <osm_file> [--summary]")
        print("       python osmstats.py <osm_file> --detailed")
        print()
        print("Examples:")
        print("  python osmstats.py map.osm")
        print("  python osmstats.py filtered.osm --detailed")
        print("  python osmstats.py extract.osm --summary")
        sys.exit(1)
    
    file_path = sys.argv[1]
    detailed = '--detailed' in sys.argv or len(sys.argv) == 2
    summary = '--summary' in sys.argv
    
    try:
        print(f"Analyzing OSM file: {file_path}")
        stats = analyze_osm_file(file_path)
        print()
        
        if summary:
            print_summary_stats(stats, file_path)
        else:
            print_detailed_stats(stats, file_path)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()