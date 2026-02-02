"""
OSM Core - Shared module for OSMFast and OSMStats.

This package provides high-performance OpenStreetMap data processing
with semantic feature extraction and Osmosis-compatible filtering.
"""

__version__ = "2.0.0"

# Data models
from osm_core.models.elements import OSMNode, OSMWay, OSMRelation
from osm_core.models.features import SemanticFeature
from osm_core.models.statistics import OSMStats

# Filtering
from osm_core.filters.base import FilterRule
from osm_core.filters.osm_filter import OSMFilter, TagFilter, BoundingBoxFilter, UsedNodeTracker
from osm_core.filters.semantic_categories import (
    ALL_AMENITY_TYPES, HIGHWAY_TYPES, BUILDING_TYPES, IMPORTANT_TAGS
)

# Parsing
from osm_core.parsing.mmap_parser import UltraFastOSMParser
from osm_core.parsing.pattern_cache import OptimizedPatternCache

# Extraction
from osm_core.extraction.feature_extractor import SemanticFilters

# Main API
from osm_core.api import OSMFast

__all__ = [
    # Version
    '__version__',
    # Models
    'OSMNode', 'OSMWay', 'OSMRelation', 'SemanticFeature', 'OSMStats',
    # Filters
    'FilterRule', 'OSMFilter', 'TagFilter', 'BoundingBoxFilter', 'UsedNodeTracker',
    # Categories
    'ALL_AMENITY_TYPES', 'HIGHWAY_TYPES', 'BUILDING_TYPES', 'IMPORTANT_TAGS',
    # Parsing
    'UltraFastOSMParser', 'OptimizedPatternCache',
    # Extraction
    'SemanticFilters',
    # API
    'OSMFast',
]
