"""OSM Element data models."""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional


@dataclass
class OSMNode:
    """OSM Node with location and tags.

    Represents a point feature in OpenStreetMap with latitude/longitude
    coordinates and associated tags.
    """
    id: str
    lat: float
    lon: float
    tags: Dict[str, str] = field(default_factory=dict)

    def to_geojson_feature(self) -> Dict[str, Any]:
        """Convert to GeoJSON Feature.

        Returns:
            GeoJSON Feature dict with Point geometry
        """
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.lon, self.lat]
            },
            "properties": {
                "id": self.id,
                "osm_type": "node",
                **self.tags
            }
        }


@dataclass
class OSMWay:
    """OSM Way with node references and tags.

    Represents a linear or area feature defined by an ordered list of node
    references.
    """
    id: str
    node_refs: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def nodes(self) -> List[str]:
        """Backward compatibility alias for node_refs."""
        return self.node_refs

    @property
    def is_closed(self) -> bool:
        """Check if this way forms a closed loop."""
        return (len(self.node_refs) >= 4 and
                self.node_refs[0] == self.node_refs[-1])

    @property
    def is_area(self) -> bool:
        """Check if this way represents an area (building, landuse, etc.)."""
        area_tags = {'building', 'landuse', 'natural', 'area', 'leisure',
                     'amenity', 'shop', 'tourism'}
        return self.is_closed and any(tag in self.tags for tag in area_tags)

    def to_geojson_feature(self, node_coords: Dict[str, Tuple[float, float]]) -> Dict[str, Any]:
        """Convert to GeoJSON Feature with coordinates.

        Args:
            node_coords: Dict mapping node IDs to (lat, lon) tuples

        Returns:
            GeoJSON Feature dict with LineString or Polygon geometry
        """
        coordinates = []
        for node_id in self.node_refs:
            if node_id in node_coords:
                lat, lon = node_coords[node_id]
                coordinates.append([lon, lat])  # GeoJSON uses [lon, lat]

        # Determine if it's a Polygon or LineString
        if self.is_area and len(coordinates) >= 4:
            geometry = {
                "type": "Polygon",
                "coordinates": [coordinates]
            }
        else:
            geometry = {
                "type": "LineString",
                "coordinates": coordinates
            }

        return {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id": self.id,
                "osm_type": "way",
                "node_count": len(self.node_refs),
                **self.tags
            }
        }


@dataclass
class OSMRelation:
    """OSM Relation with members and tags.

    Represents a logical grouping of elements (nodes, ways, other relations)
    with roles and associated tags.
    """
    id: str
    members: List[Dict[str, Any]] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def member_count(self) -> int:
        """Get the number of members in this relation."""
        return len(self.members)

    def get_members_by_type(self, member_type: str) -> List[Dict[str, Any]]:
        """Get all members of a specific type.

        Args:
            member_type: 'node', 'way', or 'relation'

        Returns:
            List of member dicts matching the type
        """
        return [m for m in self.members if m.get('type') == member_type]

    def get_members_by_role(self, role: str) -> List[Dict[str, Any]]:
        """Get all members with a specific role.

        Args:
            role: The role to filter by (e.g., 'outer', 'inner', 'stop')

        Returns:
            List of member dicts with the specified role
        """
        return [m for m in self.members if m.get('role') == role]
