#!/usr/bin/env python3
"""
OSMFast - Ultra-High Performance OpenStreetMap Data Extractor

This is the CLI entry point. The implementation is in the osm_core package.

Usage:
    osmfast extract map.osm features.json
    osmfast merge file1.osm file2.osm -o combined.osm
    osmfast stats map.osm
    osmfast filter --accept-ways highway=* city.osm -o roads.osm

For more information, run: osmfast --help
"""
import sys

# Re-export public API for backward compatibility
from osm_core import (
    # Version
    __version__,
    # Models
    OSMNode,
    OSMWay,
    OSMRelation,
    SemanticFeature,
    OSMStats,
    # Filters
    FilterRule,
    OSMFilter,
    TagFilter,
    BoundingBoxFilter,
    UsedNodeTracker,
    # Categories
    ALL_AMENITY_TYPES,
    HIGHWAY_TYPES,
    BUILDING_TYPES,
    IMPORTANT_TAGS,
    # Parsing
    UltraFastOSMParser,
    OptimizedPatternCache,
    # Extraction
    SemanticFilters,
    # API
    OSMFast,
)

# Re-export CLI entry point
from osm_core.cli.main import main


def cli_main():
    """CLI entry point for setuptools."""
    sys.exit(main())


if __name__ == "__main__":
    cli_main()
