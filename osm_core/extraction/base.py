"""Base classes for feature extraction.

Provides abstract base classes that eliminate code duplication across
different feature extractors (amenities, highways, buildings).
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional, Set

from osm_core.models.elements import OSMNode, OSMWay
from osm_core.models.features import SemanticFeature


class BaseExtractor(ABC):
    """Abstract base class for feature extractors."""

    def __init__(self, important_tags: Set[str], valid_types: Set[str]):
        """Initialize extractor.

        Args:
            important_tags: Set of tag keys to include in properties
            valid_types: Set of valid feature subtypes to extract
        """
        self.important_tags = important_tags
        self.valid_types = valid_types

    def extract_properties(self, tags: Dict[str, str],
                           exclude_key: str,
                           include_all: bool = False,
                           tag_filter: Set[str] = None) -> Dict[str, str]:
        """Extract relevant properties from tags.

        Args:
            tags: Element tags
            exclude_key: Tag key to exclude (the main feature key)
            include_all: If True, include all tags; otherwise only important tags
            tag_filter: Optional custom set of tags to include (overrides include_all)

        Returns:
            Dict of properties
        """
        if tag_filter is not None:
            return {k: v for k, v in tags.items()
                    if k in tag_filter and k != exclude_key}
        if include_all:
            return {k: v for k, v in tags.items() if k != exclude_key}
        return {k: v for k, v in tags.items()
                if k in self.important_tags and k != exclude_key}

    @abstractmethod
    def extract(self, elements, node_coords: Optional[Dict] = None) -> List[SemanticFeature]:
        """Extract features from elements.

        Args:
            elements: List of OSM elements
            node_coords: Optional dict mapping node IDs to coordinates

        Returns:
            List of extracted SemanticFeature objects
        """
        pass


class NodeExtractor(BaseExtractor):
    """Base extractor for node-based features (e.g., amenities)."""

    def __init__(self, tag_key: str, valid_types: Set[str],
                 important_tags: Set[str]):
        """Initialize node extractor.

        Args:
            tag_key: Main tag key to filter by (e.g., 'amenity')
            valid_types: Set of valid tag values
            important_tags: Set of important property tags
        """
        super().__init__(important_tags, valid_types)
        self.tag_key = tag_key

    def extract(self, nodes: List[OSMNode],
                node_coords: Optional[Dict] = None,
                include_all_tags: bool = False,
                tag_filter: Set[str] = None) -> List[SemanticFeature]:
        """Extract features from nodes.

        Args:
            nodes: List of OSMNode objects
            node_coords: Unused (nodes have their own coords)
            include_all_tags: Include all tags in properties
            tag_filter: Optional custom set of tags to include

        Returns:
            List of SemanticFeature objects
        """
        features = []

        for node in nodes:
            if self.tag_key in node.tags and node.tags[self.tag_key] in self.valid_types:
                feature = SemanticFeature(
                    id=node.id,
                    feature_type=self.tag_key,
                    feature_subtype=node.tags[self.tag_key],
                    name=node.tags.get('name'),
                    geometry_type='point',
                    coordinates=[node.lon, node.lat],
                    properties=self.extract_properties(node.tags, self.tag_key, include_all_tags, tag_filter)
                )
                features.append(feature)

        return features


class WayExtractor(BaseExtractor):
    """Base extractor for way-based features (e.g., highways, buildings)."""

    def __init__(self, tag_key: str, valid_types: Set[str],
                 important_tags: Set[str],
                 geometry_type: str = 'line',
                 min_coords: int = 2):
        """Initialize way extractor.

        Args:
            tag_key: Main tag key to filter by (e.g., 'highway')
            valid_types: Set of valid tag values
            important_tags: Set of important property tags
            geometry_type: Default geometry type ('line' or 'polygon')
            min_coords: Minimum coordinate count for valid geometry
        """
        super().__init__(important_tags, valid_types)
        self.tag_key = tag_key
        self.geometry_type = geometry_type
        self.min_coords = min_coords

    def build_coordinates(self, way: OSMWay,
                          node_coords: Dict[str, Tuple[float, float]]) -> List[List[float]]:
        """Build coordinate list from way nodes.

        Args:
            way: OSMWay object
            node_coords: Dict mapping node IDs to (lat, lon) tuples

        Returns:
            List of [lon, lat] coordinates
        """
        coordinates = []
        for node_id in way.node_refs:
            if node_id in node_coords:
                lat, lon = node_coords[node_id]
                coordinates.append([lon, lat])
        return coordinates

    def extract(self, ways: List[OSMWay],
                node_coords: Dict[str, Tuple[float, float]],
                include_all_tags: bool = False,
                tag_filter: Set[str] = None) -> List[SemanticFeature]:
        """Extract features from ways.

        Args:
            ways: List of OSMWay objects
            node_coords: Dict mapping node IDs to (lat, lon) tuples
            include_all_tags: Include all tags in properties
            tag_filter: Optional custom set of tags to include

        Returns:
            List of SemanticFeature objects
        """
        features = []

        for way in ways:
            if self.tag_key in way.tags and way.tags[self.tag_key] in self.valid_types:
                coords = self.build_coordinates(way, node_coords)

                if len(coords) >= self.min_coords:
                    feature = self._create_feature(way, coords, include_all_tags, tag_filter)
                    features.append(feature)

        return features

    def _create_feature(self, way: OSMWay,
                        coords: List[List[float]],
                        include_all_tags: bool = False,
                        tag_filter: Set[str] = None) -> SemanticFeature:
        """Create a feature from a way. Override in subclasses for custom logic.

        Args:
            way: OSMWay object
            coords: List of [lon, lat] coordinates
            include_all_tags: Include all tags in properties
            tag_filter: Optional custom set of tags to include

        Returns:
            SemanticFeature object
        """
        return SemanticFeature(
            id=way.id,
            feature_type=self.tag_key,
            feature_subtype=way.tags[self.tag_key],
            name=way.tags.get('name'),
            geometry_type=self.geometry_type,
            coordinates=coords,
            properties=self.extract_properties(way.tags, self.tag_key, include_all_tags, tag_filter)
        )
