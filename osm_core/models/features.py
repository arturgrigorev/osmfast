"""Semantic feature data model."""
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Union


@dataclass
class SemanticFeature:
    """Semantic feature extracted from OSM data.

    Represents a categorized geographic feature with geometry and properties.
    Supports conversion to GeoJSON format.
    """
    id: str
    feature_type: str  # 'amenity', 'highway', 'building', etc.
    feature_subtype: str  # 'restaurant', 'primary', 'residential', etc.
    name: Optional[str]
    geometry_type: str  # 'point', 'line', 'polygon'
    coordinates: Union[List[float], List[List[float]]]  # [lon, lat] or [[lon, lat], ...]
    properties: Dict[str, str]

    def to_geojson_feature(self) -> Dict[str, Any]:
        """Convert to GeoJSON Feature.

        Returns:
            GeoJSON Feature dict with appropriate geometry type
        """
        if self.geometry_type == 'point':
            geometry = {
                "type": "Point",
                "coordinates": self.coordinates
            }
        elif self.geometry_type == 'line':
            geometry = {
                "type": "LineString",
                "coordinates": self.coordinates
            }
        else:  # polygon
            geometry = {
                "type": "Polygon",
                "coordinates": [self.coordinates]
            }

        return {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id": self.id,
                "category": self.feature_type,
                "subcategory": self.feature_subtype,
                "name": self.name,
                **self.properties
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a simple dictionary representation.

        Returns:
            Dict with all feature attributes
        """
        return {
            'id': self.id,
            'feature_type': self.feature_type,
            'feature_subtype': self.feature_subtype,
            'name': self.name,
            'geometry_type': self.geometry_type,
            'coordinates': self.coordinates,
            'properties': self.properties
        }
