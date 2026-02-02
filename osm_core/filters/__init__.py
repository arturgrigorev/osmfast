"""OSM filtering system with Osmosis-compatible functionality."""

from osm_core.filters.base import FilterRule
from osm_core.filters.osm_filter import OSMFilter, TagFilter, BoundingBoxFilter, UsedNodeTracker
from osm_core.filters.semantic_categories import (
    ALL_AMENITY_TYPES, HIGHWAY_TYPES, BUILDING_TYPES, IMPORTANT_TAGS
)

__all__ = [
    'FilterRule', 'OSMFilter', 'TagFilter', 'BoundingBoxFilter', 'UsedNodeTracker',
    'ALL_AMENITY_TYPES', 'HIGHWAY_TYPES', 'BUILDING_TYPES', 'IMPORTANT_TAGS',
]
