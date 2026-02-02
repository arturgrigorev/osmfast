"""OSM Filtering system with Osmosis-compatible functionality.

This module provides a composable filtering system that supports:
- Tag-based accept/reject filtering
- Bounding box geographic filtering
- Used-node mode for including only referenced nodes
- Global element type rejection
"""
from typing import List, Dict, Set, Optional, TYPE_CHECKING

from osm_core.filters.base import FilterRule

if TYPE_CHECKING:
    from osm_core.models.elements import OSMNode, OSMWay


class TagFilter:
    """Handles tag-based filtering (accept/reject rules)."""

    def __init__(self):
        self.rules: List[FilterRule] = []

    def add_accept(self, element_type: str, key: str, value: str = '*') -> None:
        """Add an acceptance filter rule.

        Args:
            element_type: 'nodes', 'ways', or '*'
            key: OSM tag key to match
            value: Tag value or '*' for any, comma-separated for multiple
        """
        if ',' in value:
            values = [v.strip() for v in value.split(',')]
            self.rules.append(FilterRule('accept', element_type, key, None, values))
        else:
            self.rules.append(FilterRule('accept', element_type, key, value))

    def add_reject(self, element_type: str, key: str, value: str = '*') -> None:
        """Add a rejection filter rule.

        Args:
            element_type: 'nodes', 'ways', or '*'
            key: OSM tag key to match
            value: Tag value or '*' for any, comma-separated for multiple
        """
        if ',' in value:
            values = [v.strip() for v in value.split(',')]
            self.rules.append(FilterRule('reject', element_type, key, None, values))
        else:
            self.rules.append(FilterRule('reject', element_type, key, value))

    def matches(self, element_type: str, tags: Dict[str, str]) -> Optional[bool]:
        """Check if element matches filter rules.

        Args:
            element_type: 'nodes', 'ways', or 'relations'
            tags: Element's tag dictionary

        Returns:
            True if accepted, False if rejected, None if no rules for element type
        """
        if not self.rules:
            return None

        # Track if we have any accept rules for this element type
        has_accept_rules_for_type = False
        should_accept = None

        for rule in self.rules:
            # Check if this rule applies to this element type
            if rule.element_type == '*' or rule.element_type == element_type:
                if rule.action == 'accept':
                    has_accept_rules_for_type = True

            if rule.matches(element_type, tags):
                if rule.action == 'accept':
                    should_accept = True
                elif rule.action == 'reject':
                    return False  # Reject rules override accept rules

        # If we have accept rules for this type but none matched, reject
        if has_accept_rules_for_type and should_accept is None:
            return False

        return should_accept

    @property
    def has_rules(self) -> bool:
        """Check if any rules are defined."""
        return len(self.rules) > 0

    def clear(self) -> None:
        """Clear all rules."""
        self.rules.clear()


class BoundingBoxFilter:
    """Handles geographic bounding box filtering."""

    def __init__(self, top: float, left: float, bottom: float, right: float):
        """Initialize bounding box.

        Args:
            top: Maximum latitude
            left: Minimum longitude
            bottom: Minimum latitude
            right: Maximum longitude
        """
        self.top = top
        self.left = left
        self.bottom = bottom
        self.right = right

    def contains(self, lat: float, lon: float) -> bool:
        """Check if a point is within the bounding box.

        Args:
            lat: Point latitude
            lon: Point longitude

        Returns:
            True if point is within bounds
        """
        return (self.bottom <= lat <= self.top and
                self.left <= lon <= self.right)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary representation."""
        return {
            'top': self.top,
            'left': self.left,
            'bottom': self.bottom,
            'right': self.right
        }

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> 'BoundingBoxFilter':
        """Create from dictionary."""
        return cls(d['top'], d['left'], d['bottom'], d['right'])


class UsedNodeTracker:
    """Tracks nodes referenced by ways for used-node mode."""

    def __init__(self):
        self.used_nodes: Set[str] = set()
        self.enabled = False

    def enable(self) -> None:
        """Enable used-node tracking."""
        self.enabled = True

    def disable(self) -> None:
        """Disable used-node tracking."""
        self.enabled = False

    def collect_from_ways(self, ways: List['OSMWay']) -> None:
        """Collect node IDs referenced by ways.

        Args:
            ways: List of OSMWay objects
        """
        for way in ways:
            for node_id in way.node_refs:
                self.used_nodes.add(node_id)

    def is_used(self, node_id: str) -> bool:
        """Check if a node is referenced by any way.

        Args:
            node_id: Node ID to check

        Returns:
            True if node is used (or tracking disabled)
        """
        if not self.enabled:
            return True
        return node_id in self.used_nodes

    def clear(self) -> None:
        """Clear collected nodes."""
        self.used_nodes.clear()


class OSMFilter:
    """Composite filter combining tag, bbox, and element type filters.

    This class provides Osmosis-compatible filtering functionality through
    composition of specialized filter components.
    """

    def __init__(self):
        self.tag_filter = TagFilter()
        self.bbox_filter: Optional[BoundingBoxFilter] = None
        self.used_node_tracker = UsedNodeTracker()
        self.reject_ways = False
        self.reject_relations = False
        self.reject_nodes = False

    # === Backward-compatible API ===

    @property
    def rules(self) -> List[FilterRule]:
        """Get filter rules (backward compatibility)."""
        return self.tag_filter.rules

    @property
    def used_node_mode(self) -> bool:
        """Check if used-node mode is enabled."""
        return self.used_node_tracker.enabled

    @property
    def used_nodes(self) -> Set[str]:
        """Get set of used nodes."""
        return self.used_node_tracker.used_nodes

    @property
    def bounding_box(self) -> Optional[Dict[str, float]]:
        """Get bounding box as dict (backward compatibility)."""
        if self.bbox_filter:
            return self.bbox_filter.to_dict()
        return None

    def add_accept_filter(self, element_type: str, key: str, value: str = '*') -> None:
        """Add an accept filter rule (backward compatibility)."""
        self.tag_filter.add_accept(element_type, key, value)

    def add_reject_filter(self, element_type: str, key: str, value: str = '*') -> None:
        """Add a reject filter rule (backward compatibility)."""
        self.tag_filter.add_reject(element_type, key, value)

    def enable_used_node_mode(self) -> None:
        """Enable used-node mode."""
        self.used_node_tracker.enable()

    def set_global_rejection(self, reject_ways: bool = False,
                             reject_relations: bool = False,
                             reject_nodes: bool = False) -> None:
        """Set global element type rejection."""
        self.reject_ways = reject_ways
        self.reject_relations = reject_relations
        self.reject_nodes = reject_nodes

    def set_bounding_box(self, top: float, left: float,
                         bottom: float, right: float) -> None:
        """Set geographic bounding box filter."""
        self.bbox_filter = BoundingBoxFilter(top, left, bottom, right)

    def collect_used_nodes(self, ways: List['OSMWay']) -> None:
        """Collect node IDs used by filtered ways."""
        self.used_node_tracker.collect_from_ways(ways)

    # === Core filtering logic ===

    def has_active_filters(self) -> bool:
        """Check if any filters are active."""
        return (self.tag_filter.has_rules or
                self.reject_ways or
                self.reject_relations or
                self.reject_nodes or
                self.bbox_filter is not None)

    def should_include_element(self, element_type: str, element_id: str,
                               tags: Dict[str, str],
                               lat: float = None, lon: float = None) -> bool:
        """Determine if an element should be included.

        Args:
            element_type: 'nodes', 'ways', or 'relations'
            element_id: Element ID
            tags: Element tags
            lat: Latitude (for nodes)
            lon: Longitude (for nodes)

        Returns:
            True if element should be included
        """
        # Check global element type rejection
        if element_type == 'ways' and self.reject_ways:
            return False
        if element_type == 'nodes' and self.reject_nodes:
            return False
        if element_type == 'relations' and self.reject_relations:
            return False

        # Check bounding box
        if self.bbox_filter and lat is not None and lon is not None:
            if not self.bbox_filter.contains(lat, lon):
                return False

        # Check used-node mode
        if element_type == 'nodes' and not self.used_node_tracker.is_used(element_id):
            return False

        # Check tag filters
        tag_result = self.tag_filter.matches(element_type, tags)
        if tag_result is not None:
            return tag_result

        # If no tag rules, include everything not rejected by other filters
        return True

    def filter_nodes(self, nodes: List['OSMNode']) -> List['OSMNode']:
        """Filter nodes based on rules.

        Args:
            nodes: List of OSMNode objects

        Returns:
            Filtered list of nodes
        """
        return [node for node in nodes
                if self.should_include_element('nodes', node.id, node.tags,
                                                node.lat, node.lon)]

    def filter_ways(self, ways: List['OSMWay']) -> List['OSMWay']:
        """Filter ways based on rules.

        Args:
            ways: List of OSMWay objects

        Returns:
            Filtered list of ways
        """
        filtered_ways = [way for way in ways
                         if self.should_include_element('ways', way.id, way.tags)]

        # Collect used nodes if in used-node mode
        if self.used_node_tracker.enabled:
            self.used_node_tracker.collect_from_ways(filtered_ways)

        return filtered_ways

    # === Osmosis-style parsing ===

    def parse_osmosis_filter(self, filter_str: str) -> None:
        """Parse osmosis-style filter string.

        Examples:
            "highway=*" -> accept ways with any highway tag
            "highway=primary,secondary" -> accept specific values
            "reject:highway=motorway" -> reject specific value

        Args:
            filter_str: Filter string in osmosis format
        """
        parts = filter_str.split(':', 1)
        action = 'accept'
        filter_part = filter_str

        if len(parts) == 2 and parts[0] in ['accept', 'reject']:
            action, filter_part = parts

        if '=' in filter_part:
            key, value = filter_part.split('=', 1)
            if action == 'accept':
                self.add_accept_filter('*', key, value)
            else:
                self.add_reject_filter('*', key, value)

    @classmethod
    def from_osmosis_args(cls, accept_ways: List[str] = None,
                          reject_ways: List[str] = None,
                          accept_nodes: List[str] = None,
                          reject_nodes: List[str] = None,
                          used_node: bool = False,
                          reject_ways_global: bool = False,
                          reject_relations_global: bool = False,
                          reject_nodes_global: bool = False,
                          bounding_box: Dict[str, float] = None) -> 'OSMFilter':
        """Create filter from osmosis-style arguments.

        Args:
            accept_ways: List of accept filters for ways
            reject_ways: List of reject filters for ways
            accept_nodes: List of accept filters for nodes
            reject_nodes: List of reject filters for nodes
            used_node: Enable used-node mode
            reject_ways_global: Reject all ways
            reject_relations_global: Reject all relations
            reject_nodes_global: Reject all nodes
            bounding_box: Dict with top, left, bottom, right

        Returns:
            Configured OSMFilter instance
        """
        filter_obj = cls()

        if used_node:
            filter_obj.enable_used_node_mode()

        # Set global rejections
        if reject_ways_global or reject_relations_global or reject_nodes_global:
            filter_obj.set_global_rejection(
                reject_ways=reject_ways_global,
                reject_relations=reject_relations_global,
                reject_nodes=reject_nodes_global
            )

        # Set bounding box
        if bounding_box:
            filter_obj.set_bounding_box(**bounding_box)

        if accept_ways:
            for filter_str in accept_ways:
                if '=' in filter_str:
                    key, value = filter_str.split('=', 1)
                    filter_obj.add_accept_filter('ways', key, value)

        if reject_ways:
            for filter_str in reject_ways:
                if '=' in filter_str:
                    key, value = filter_str.split('=', 1)
                    filter_obj.add_reject_filter('ways', key, value)

        if accept_nodes:
            for filter_str in accept_nodes:
                if '=' in filter_str:
                    key, value = filter_str.split('=', 1)
                    filter_obj.add_accept_filter('nodes', key, value)

        if reject_nodes:
            for filter_str in reject_nodes:
                if '=' in filter_str:
                    key, value = filter_str.split('=', 1)
                    filter_obj.add_reject_filter('nodes', key, value)

        return filter_obj
