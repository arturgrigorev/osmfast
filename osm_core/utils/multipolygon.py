"""Multipolygon geometry assembly from OSM relations.

Handles the complex task of assembling multipolygon geometries from
OSM relation members, including ring building and hole assignment.
"""
from typing import List, Dict, Tuple, Optional, Any

from osm_core.models.elements import OSMRelation, OSMWay
from osm_core.utils.geo_utils import (
    ensure_winding_order, ring_contains_ring, get_ring_centroid
)


class MultipolygonAssembler:
    """Assembles multipolygon geometry from OSM relation members.

    Handles:
    - Collecting outer and inner member ways
    - Building closed rings from way segments (joining end-to-end if needed)
    - Assigning inner rings (holes) to their containing outer rings
    - Applying RFC 7946 winding order rules
    """

    def __init__(self, ways: Dict[str, OSMWay],
                 node_coords: Dict[str, Tuple[float, float]]):
        """Initialize with way and node data.

        Args:
            ways: Dict mapping way IDs to OSMWay objects
            node_coords: Dict mapping node IDs to (lat, lon) tuples
        """
        self.ways = ways
        self.node_coords = node_coords
        self._way_coords_cache: Dict[str, List[List[float]]] = {}

    def get_way_coordinates(self, way_id: str) -> Optional[List[List[float]]]:
        """Get coordinates for a way, with caching.

        Args:
            way_id: OSM way ID

        Returns:
            List of [lon, lat] coordinates, or None if way not found
        """
        if way_id in self._way_coords_cache:
            return self._way_coords_cache[way_id]

        way = self.ways.get(way_id)
        if not way:
            return None

        coords = []
        for node_id in way.node_refs:
            if node_id in self.node_coords:
                lat, lon = self.node_coords[node_id]
                coords.append([lon, lat])  # GeoJSON format

        if coords:
            self._way_coords_cache[way_id] = coords

        return coords if coords else None

    def assemble(self, relation: OSMRelation) -> Optional[Dict[str, Any]]:
        """Assemble multipolygon geometry from relation.

        Args:
            relation: OSM multipolygon relation

        Returns:
            GeoJSON geometry dict (Polygon or MultiPolygon), or None on failure
        """
        if relation.tags.get('type') != 'multipolygon':
            return None

        # Collect outer and inner member ways
        outer_members = relation.get_members_by_role('outer')
        inner_members = relation.get_members_by_role('inner')

        # Also check for empty role (sometimes used for outer)
        for member in relation.members:
            if member.get('type') == 'way' and member.get('role') == '':
                outer_members.append(member)

        # Build rings from ways
        outer_rings = self._build_rings(outer_members)
        inner_rings = self._build_rings(inner_members)

        if not outer_rings:
            return None

        # Assign holes to outer rings
        polygons = self._assign_holes(outer_rings, inner_rings)

        # Apply RFC 7946 winding order
        for polygon in polygons:
            # Exterior ring: counter-clockwise
            polygon[0] = ensure_winding_order(polygon[0], 'ccw')
            # Interior rings (holes): clockwise
            for i in range(1, len(polygon)):
                polygon[i] = ensure_winding_order(polygon[i], 'cw')

        # Return appropriate geometry type
        if len(polygons) == 1:
            return {"type": "Polygon", "coordinates": polygons[0]}
        else:
            return {"type": "MultiPolygon", "coordinates": polygons}

    def _build_rings(self, way_members: List[Dict]) -> List[List[List[float]]]:
        """Build closed rings from way members, joining if necessary.

        Ways in a multipolygon may need to be joined end-to-end to form
        complete closed rings.

        Args:
            way_members: List of member dicts with 'ref' keys

        Returns:
            List of ring coordinate arrays
        """
        if not way_members:
            return []

        # Get coordinates for each way
        way_coords = []
        for member in way_members:
            if member.get('type') != 'way':
                continue
            coords = self.get_way_coordinates(member['ref'])
            if coords and len(coords) >= 2:
                way_coords.append(coords)

        if not way_coords:
            return []

        # Try to build closed rings
        rings = []
        used = set()

        for i, coords in enumerate(way_coords):
            if i in used:
                continue

            # Check if this way is already a closed ring
            if self._is_closed(coords):
                rings.append(coords)
                used.add(i)
                continue

            # Try to build a ring by joining ways
            ring = list(coords)
            used.add(i)

            # Keep trying to extend the ring
            changed = True
            while changed and not self._is_closed(ring):
                changed = False
                for j, other_coords in enumerate(way_coords):
                    if j in used:
                        continue

                    joined = self._try_join(ring, other_coords)
                    if joined:
                        ring = joined
                        used.add(j)
                        changed = True
                        break

            if self._is_closed(ring):
                rings.append(ring)

        return rings

    def _is_closed(self, coords: List[List[float]]) -> bool:
        """Check if a coordinate ring is closed.

        Args:
            coords: Ring coordinates

        Returns:
            True if first and last coordinates match
        """
        if len(coords) < 3:
            return False

        first = coords[0]
        last = coords[-1]

        # Allow small tolerance for floating point comparison
        return (abs(first[0] - last[0]) < 1e-9 and
                abs(first[1] - last[1]) < 1e-9)

    def _try_join(self, ring: List[List[float]],
                  other: List[List[float]]) -> Optional[List[List[float]]]:
        """Try to join another way segment to the ring.

        Args:
            ring: Current ring being built
            other: Way segment to potentially join

        Returns:
            Joined ring if successful, None otherwise
        """
        if not ring or not other:
            return None

        ring_start = ring[0]
        ring_end = ring[-1]
        other_start = other[0]
        other_end = other[-1]

        tolerance = 1e-9

        def coords_match(a: List[float], b: List[float]) -> bool:
            return abs(a[0] - b[0]) < tolerance and abs(a[1] - b[1]) < tolerance

        # Try different join configurations
        if coords_match(ring_end, other_start):
            # ring end connects to other start
            return ring + other[1:]
        elif coords_match(ring_end, other_end):
            # ring end connects to other end (reverse other)
            return ring + list(reversed(other))[1:]
        elif coords_match(ring_start, other_end):
            # other end connects to ring start
            return other[:-1] + ring
        elif coords_match(ring_start, other_start):
            # other start connects to ring start (reverse other)
            return list(reversed(other))[:-1] + ring

        return None

    def _assign_holes(self, outer_rings: List[List[List[float]]],
                      inner_rings: List[List[List[float]]]) -> List[List[List[List[float]]]]:
        """Assign inner rings (holes) to their containing outer rings.

        Args:
            outer_rings: List of outer ring coordinate arrays
            inner_rings: List of inner ring coordinate arrays

        Returns:
            List of polygons, each polygon is [outer_ring, hole1, hole2, ...]
        """
        # Initialize each polygon with just its outer ring
        polygons = [[outer] for outer in outer_rings]

        # Assign each inner ring to the smallest containing outer
        for inner in inner_rings:
            containing_idx = None
            containing_area = float('inf')

            inner_centroid = get_ring_centroid(inner)

            for i, outer in enumerate(outer_rings):
                if ring_contains_ring(outer, inner):
                    # Calculate approximate area to find smallest containing ring
                    from osm_core.utils.geo_utils import get_signed_area
                    area = abs(get_signed_area(outer))
                    if area < containing_area:
                        containing_area = area
                        containing_idx = i

            if containing_idx is not None:
                polygons[containing_idx].append(inner)

        return polygons


def assemble_multipolygon(relation: OSMRelation,
                          ways: Dict[str, OSMWay],
                          node_coords: Dict[str, Tuple[float, float]]) -> Optional[Dict[str, Any]]:
    """Convenience function to assemble a multipolygon.

    Args:
        relation: OSM multipolygon relation
        ways: Dict mapping way IDs to OSMWay objects
        node_coords: Dict mapping node IDs to (lat, lon) tuples

    Returns:
        GeoJSON geometry dict or None
    """
    assembler = MultipolygonAssembler(ways, node_coords)
    return assembler.assemble(relation)
