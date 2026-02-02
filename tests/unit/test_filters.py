"""Tests for filter classes."""
import pytest
from osm_core.filters.base import FilterRule
from osm_core.filters.osm_filter import (
    OSMFilter, TagFilter, BoundingBoxFilter, UsedNodeTracker
)


class TestFilterRule:
    """Tests for FilterRule class."""

    def test_exact_match(self):
        """Test exact value matching."""
        rule = FilterRule("accept", "nodes", "amenity", "restaurant")
        assert rule.matches("nodes", {"amenity": "restaurant"}) is True
        assert rule.matches("nodes", {"amenity": "cafe"}) is False

    def test_wildcard_match(self):
        """Test wildcard value matching."""
        rule = FilterRule("accept", "ways", "highway", "*")
        assert rule.matches("ways", {"highway": "primary"}) is True
        assert rule.matches("ways", {"highway": "residential"}) is True
        assert rule.matches("ways", {"building": "yes"}) is False

    def test_element_type_mismatch(self):
        """Test element type filtering."""
        rule = FilterRule("accept", "nodes", "amenity", "*")
        assert rule.matches("ways", {"amenity": "restaurant"}) is False

    def test_multiple_values(self):
        """Test multiple value matching."""
        rule = FilterRule("accept", "ways", "highway", None, ["primary", "secondary"])
        assert rule.matches("ways", {"highway": "primary"}) is True
        assert rule.matches("ways", {"highway": "secondary"}) is True
        assert rule.matches("ways", {"highway": "tertiary"}) is False


class TestTagFilter:
    """Tests for TagFilter class."""

    def test_accept_rule(self):
        """Test accept rule."""
        tag_filter = TagFilter()
        tag_filter.add_accept("nodes", "amenity", "restaurant")

        assert tag_filter.matches("nodes", {"amenity": "restaurant"}) is True
        # Non-matching elements should be rejected when accept rules exist
        assert tag_filter.matches("nodes", {"amenity": "cafe"}) is False

    def test_reject_overrides_accept(self):
        """Test that reject rules override accept."""
        tag_filter = TagFilter()
        tag_filter.add_accept("ways", "highway", "*")
        tag_filter.add_reject("ways", "highway", "footway")

        assert tag_filter.matches("ways", {"highway": "primary"}) is True
        assert tag_filter.matches("ways", {"highway": "footway"}) is False


class TestBoundingBoxFilter:
    """Tests for BoundingBoxFilter class."""

    def test_contains_inside(self):
        """Test point inside bounding box."""
        bbox = BoundingBoxFilter(top=52.0, left=-1.0, bottom=51.0, right=0.0)
        assert bbox.contains(51.5, -0.5) is True

    def test_contains_edge(self):
        """Test point on boundary."""
        bbox = BoundingBoxFilter(top=52.0, left=-1.0, bottom=51.0, right=0.0)
        assert bbox.contains(51.0, -1.0) is True

    def test_contains_outside(self):
        """Test point outside bounding box."""
        bbox = BoundingBoxFilter(top=52.0, left=-1.0, bottom=51.0, right=0.0)
        assert bbox.contains(50.0, -0.5) is False


class TestUsedNodeTracker:
    """Tests for UsedNodeTracker class."""

    def test_disabled_by_default(self):
        """Test tracker is disabled by default."""
        tracker = UsedNodeTracker()
        assert tracker.enabled is False
        assert tracker.is_used("1") is True  # All nodes pass when disabled

    def test_enabled_tracking(self):
        """Test enabled tracking."""
        from osm_core.models.elements import OSMWay

        tracker = UsedNodeTracker()
        tracker.enable()

        ways = [OSMWay(id="1", node_refs=["1", "2", "3"], tags={})]
        tracker.collect_from_ways(ways)

        assert tracker.is_used("1") is True
        assert tracker.is_used("2") is True
        assert tracker.is_used("4") is False


class TestOSMFilter:
    """Tests for OSMFilter class."""

    def test_empty_filter_includes_all(self, osm_filter):
        """Test empty filter includes everything."""
        assert osm_filter.should_include_element(
            "nodes", "1", {"amenity": "restaurant"}, 51.5, -0.1
        ) is True

    def test_global_rejection(self, osm_filter):
        """Test global element rejection."""
        osm_filter.set_global_rejection(reject_ways=True)
        assert osm_filter.should_include_element("ways", "1", {}) is False
        assert osm_filter.should_include_element("nodes", "1", {}) is True

    def test_bounding_box_filter(self, osm_filter):
        """Test bounding box filtering."""
        osm_filter.set_bounding_box(52.0, -1.0, 51.0, 0.0)

        assert osm_filter.should_include_element(
            "nodes", "1", {}, 51.5, -0.5
        ) is True
        assert osm_filter.should_include_element(
            "nodes", "2", {}, 50.0, -0.5
        ) is False

    def test_from_osmosis_args(self):
        """Test filter creation from osmosis args."""
        osm_filter = OSMFilter.from_osmosis_args(
            accept_ways=["highway=*"],
            reject_ways=["highway=footway"],
            used_node=True
        )

        assert osm_filter.used_node_mode is True
        assert len(osm_filter.rules) == 2
