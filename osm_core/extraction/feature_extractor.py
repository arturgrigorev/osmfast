"""Semantic feature extractors.

Specialized extractors for amenities, highways, and buildings.
"""
from typing import List, Dict, Tuple

from osm_core.models.elements import OSMNode, OSMWay
from osm_core.models.features import SemanticFeature
from osm_core.extraction.base import NodeExtractor, WayExtractor
from osm_core.filters.semantic_categories import (
    ALL_AMENITY_TYPES, HIGHWAY_TYPES, BUILDING_TYPES, IMPORTANT_TAGS
)
from osm_core.utils.geo_utils import calculate_polygon_area


class AmenityExtractor(NodeExtractor):
    """Extracts amenity features from nodes."""

    def __init__(self):
        super().__init__('amenity', ALL_AMENITY_TYPES, IMPORTANT_TAGS)


class HighwayExtractor(WayExtractor):
    """Extracts highway features from ways."""

    def __init__(self):
        super().__init__('highway', HIGHWAY_TYPES, IMPORTANT_TAGS,
                         geometry_type='line', min_coords=2)


class BuildingExtractor(WayExtractor):
    """Extracts building polygon features with area calculation."""

    def __init__(self):
        super().__init__('building', BUILDING_TYPES, IMPORTANT_TAGS,
                         geometry_type='polygon', min_coords=3)

    def _create_feature(self, way: OSMWay,
                        coords: List[List[float]],
                        include_all_tags: bool = False,
                        tag_filter: set = None) -> SemanticFeature:
        """Create building feature with area calculation.

        Args:
            way: OSMWay object
            coords: List of [lon, lat] coordinates
            include_all_tags: Include all tags in properties
            tag_filter: Optional custom set of tags to include

        Returns:
            SemanticFeature with building-specific properties
        """
        # Check if polygon is closed
        is_closed = (len(way.node_refs) > 3 and
                     way.node_refs[0] == way.node_refs[-1])

        # Close polygon if not already closed
        if not is_closed and len(coords) >= 3:
            coords = coords + [coords[0]]

        # Calculate area
        area = calculate_polygon_area(coords)

        # Build properties
        properties = self.extract_properties(way.tags, 'building', include_all_tags, tag_filter)
        properties['area_sqm'] = f"{area:.2f}"
        properties['node_count'] = str(len(way.node_refs))
        properties['is_closed'] = str(is_closed)

        # Determine geometry type
        geometry_type = 'polygon' if len(coords) >= 4 else 'line'

        return SemanticFeature(
            id=way.id,
            feature_type='building',
            feature_subtype=way.tags['building'],
            name=way.tags.get('name'),
            geometry_type=geometry_type,
            coordinates=coords,
            properties=properties
        )


class SemanticFilters:
    """High-performance semantic filtering for different feature types.

    This class provides a unified interface for extracting all semantic
    features (amenities, highways, buildings) from parsed OSM data.
    """

    def __init__(self):
        """Initialize with default extractors."""
        self.amenity_extractor = AmenityExtractor()
        self.highway_extractor = HighwayExtractor()
        self.building_extractor = BuildingExtractor()

        # Expose category sets for backward compatibility
        self.amenity_types = ALL_AMENITY_TYPES
        self.highway_types = HIGHWAY_TYPES
        self.building_types = BUILDING_TYPES
        self.important_tags = IMPORTANT_TAGS

    def extract_amenities(self, nodes: List[OSMNode],
                           include_all_tags: bool = False,
                           tag_filter: set = None) -> List[SemanticFeature]:
        """Extract amenity features from nodes.

        Args:
            nodes: List of OSMNode objects
            include_all_tags: Include all tags in properties
            tag_filter: Optional custom set of tags to include

        Returns:
            List of amenity SemanticFeature objects
        """
        return self.amenity_extractor.extract(nodes, include_all_tags=include_all_tags, tag_filter=tag_filter)

    def extract_highways(self, ways: List[OSMWay],
                         node_coords: Dict[str, Tuple[float, float]],
                         include_all_tags: bool = False,
                         tag_filter: set = None) -> List[SemanticFeature]:
        """Extract highway features from ways.

        Args:
            ways: List of OSMWay objects
            node_coords: Dict mapping node IDs to (lat, lon) tuples
            include_all_tags: Include all tags in properties
            tag_filter: Optional custom set of tags to include

        Returns:
            List of highway SemanticFeature objects
        """
        return self.highway_extractor.extract(ways, node_coords, include_all_tags, tag_filter)

    def extract_buildings(self, ways: List[OSMWay],
                          node_coords: Dict[str, Tuple[float, float]],
                          include_all_tags: bool = False,
                          tag_filter: set = None) -> List[SemanticFeature]:
        """Extract building features from ways.

        Args:
            ways: List of OSMWay objects
            node_coords: Dict mapping node IDs to (lat, lon) tuples
            include_all_tags: Include all tags in properties
            tag_filter: Optional custom set of tags to include

        Returns:
            List of building SemanticFeature objects
        """
        return self.building_extractor.extract(ways, node_coords, include_all_tags, tag_filter)

    def extract_all_features(self, nodes: List[OSMNode], ways: List[OSMWay],
                             node_coords: Dict[str, Tuple[float, float]],
                             include_all_tags: bool = False,
                             tag_filter: set = None) -> Dict[str, List[SemanticFeature]]:
        """Extract all semantic features efficiently.

        Args:
            nodes: List of OSMNode objects
            ways: List of OSMWay objects
            node_coords: Dict mapping node IDs to (lat, lon) tuples
            include_all_tags: Include all tags in properties
            tag_filter: Optional custom set of tags to include

        Returns:
            Dict with 'amenities', 'highways', 'buildings' lists
        """
        return {
            'amenities': self.extract_amenities(nodes, include_all_tags, tag_filter),
            'highways': self.extract_highways(ways, node_coords, include_all_tags, tag_filter),
            'buildings': self.extract_buildings(ways, node_coords, include_all_tags, tag_filter)
        }
