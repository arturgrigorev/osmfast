"""OSM Statistics data model."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict


@dataclass
class OSMStats:
    """Statistics for an OSM file.

    Comprehensive statistics including element counts, tag usage,
    geographic bounds, and feature type breakdowns.
    """
    # Element counts
    nodes: int = 0
    ways: int = 0
    relations: int = 0

    # Tag statistics
    unique_keys: Set[str] = field(default_factory=set)
    unique_values: Set[str] = field(default_factory=set)
    key_usage: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    popular_tags: List[Tuple[str, int]] = field(default_factory=list)

    # Geographic bounds
    min_lat: float = 90.0
    max_lat: float = -90.0
    min_lon: float = 180.0
    max_lon: float = -180.0

    # Element type breakdowns
    node_tags: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    way_tags: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    highway_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    amenity_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    building_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # File metadata
    file_size: int = 0
    processing_time: float = 0.0

    @property
    def total_elements(self) -> int:
        """Get total number of elements."""
        return self.nodes + self.ways + self.relations

    @property
    def has_valid_bounds(self) -> bool:
        """Check if geographic bounds are valid."""
        return (self.min_lat <= self.max_lat and
                self.min_lon <= self.max_lon and
                -90 <= self.min_lat <= 90 and
                -90 <= self.max_lat <= 90 and
                -180 <= self.min_lon <= 180 and
                -180 <= self.max_lon <= 180)

    @property
    def center(self) -> Tuple[float, float]:
        """Get the center point of the bounding box."""
        if not self.has_valid_bounds:
            return (0.0, 0.0)
        return (
            (self.min_lat + self.max_lat) / 2,
            (self.min_lon + self.max_lon) / 2
        )

    @property
    def bounds(self) -> Dict[str, float]:
        """Get bounds as a dictionary."""
        return {
            'min_lat': self.min_lat,
            'max_lat': self.max_lat,
            'min_lon': self.min_lon,
            'max_lon': self.max_lon
        }

    def update_bounds(self, lat: float, lon: float) -> None:
        """Update bounds with a new coordinate.

        Args:
            lat: Latitude value
            lon: Longitude value
        """
        self.min_lat = min(self.min_lat, lat)
        self.max_lat = max(self.max_lat, lat)
        self.min_lon = min(self.min_lon, lon)
        self.max_lon = max(self.max_lon, lon)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary representation.

        Returns:
            Dict with all statistics
        """
        return {
            'elements': {
                'nodes': self.nodes,
                'ways': self.ways,
                'relations': self.relations,
                'total': self.total_elements
            },
            'bounds': self.bounds if self.has_valid_bounds else None,
            'center': self.center if self.has_valid_bounds else None,
            'tags': {
                'unique_keys': len(self.unique_keys),
                'unique_values': len(self.unique_values),
                'popular': self.popular_tags[:20] if self.popular_tags else []
            },
            'feature_types': {
                'highways': dict(self.highway_types),
                'amenities': dict(self.amenity_types),
                'buildings': dict(self.building_types)
            },
            'metadata': {
                'file_size': self.file_size,
                'processing_time': self.processing_time
            }
        }

    def get_processing_rate(self) -> float:
        """Get elements processed per second."""
        if self.processing_time <= 0:
            return 0.0
        return self.total_elements / self.processing_time
