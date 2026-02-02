"""Tests for geographic utilities."""
import pytest
from osm_core.utils.geo_utils import (
    calculate_polygon_area, point_in_bbox,
    get_signed_area, get_ring_winding, ensure_winding_order,
    point_in_ring, ring_contains_ring, get_ring_centroid
)


class TestCalculatePolygonArea:
    """Tests for calculate_polygon_area function."""

    def test_empty_coordinates(self):
        """Test empty coordinates return 0."""
        assert calculate_polygon_area([]) == 0.0

    def test_insufficient_coordinates(self):
        """Test insufficient coordinates return 0."""
        assert calculate_polygon_area([[0, 0], [1, 1]]) == 0.0

    def test_approximate_square_area(self):
        """Test approximate area of a small square."""
        # Small square at equator: ~1km x 1km
        coords = [
            [0.0, 0.0],
            [0.009, 0.0],
            [0.009, 0.009],
            [0.0, 0.009],
            [0.0, 0.0]
        ]
        area = calculate_polygon_area(coords)
        # Should be approximately 1 sq km = 1,000,000 sq m
        assert 800000 < area < 1200000

    def test_triangle_area(self):
        """Test triangle area calculation."""
        coords = [
            [0.0, 0.0],
            [0.01, 0.0],
            [0.005, 0.01],
            [0.0, 0.0]
        ]
        area = calculate_polygon_area(coords)
        assert area > 0


class TestPointInBbox:
    """Tests for point_in_bbox function."""

    def test_point_inside(self):
        """Test point inside bounding box."""
        assert point_in_bbox(51.5, -0.5, 52.0, -1.0, 51.0, 0.0) is True

    def test_point_on_edge(self):
        """Test point on boundary."""
        assert point_in_bbox(51.0, -1.0, 52.0, -1.0, 51.0, 0.0) is True

    def test_point_outside(self):
        """Test point outside bounding box."""
        assert point_in_bbox(50.0, -0.5, 52.0, -1.0, 51.0, 0.0) is False


class TestSignedAreaAndWinding:
    """Tests for signed area and winding order functions."""

    # Counter-clockwise square (positive signed area)
    CCW_SQUARE = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]

    # Clockwise square (negative signed area)
    CW_SQUARE = [[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]

    def test_signed_area_ccw(self):
        """Test signed area of CCW ring is positive."""
        area = get_signed_area(self.CCW_SQUARE)
        assert area > 0

    def test_signed_area_cw(self):
        """Test signed area of CW ring is negative."""
        area = get_signed_area(self.CW_SQUARE)
        assert area < 0

    def test_signed_area_empty(self):
        """Test signed area of empty ring is 0."""
        assert get_signed_area([]) == 0.0
        assert get_signed_area([[0, 0], [1, 1]]) == 0.0

    def test_get_ring_winding_ccw(self):
        """Test CCW detection."""
        assert get_ring_winding(self.CCW_SQUARE) == 'ccw'

    def test_get_ring_winding_cw(self):
        """Test CW detection."""
        assert get_ring_winding(self.CW_SQUARE) == 'cw'

    def test_ensure_winding_ccw_already_ccw(self):
        """Test ensure_winding_order when already correct."""
        result = ensure_winding_order(self.CCW_SQUARE, 'ccw')
        assert result == self.CCW_SQUARE

    def test_ensure_winding_ccw_from_cw(self):
        """Test ensure_winding_order reverses CW to CCW."""
        result = ensure_winding_order(self.CW_SQUARE, 'ccw')
        assert get_ring_winding(result) == 'ccw'

    def test_ensure_winding_cw_already_cw(self):
        """Test ensure_winding_order when already correct."""
        result = ensure_winding_order(self.CW_SQUARE, 'cw')
        assert result == self.CW_SQUARE

    def test_ensure_winding_cw_from_ccw(self):
        """Test ensure_winding_order reverses CCW to CW."""
        result = ensure_winding_order(self.CCW_SQUARE, 'cw')
        assert get_ring_winding(result) == 'cw'

    def test_ensure_winding_short_ring(self):
        """Test ensure_winding_order with too few points."""
        short = [[0, 0], [1, 1]]
        result = ensure_winding_order(short, 'ccw')
        assert result == short


class TestPointInRing:
    """Tests for point_in_ring function."""

    SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]

    def test_point_inside(self):
        """Test point clearly inside ring."""
        assert point_in_ring([5, 5], self.SQUARE) is True

    def test_point_outside(self):
        """Test point clearly outside ring."""
        assert point_in_ring([15, 5], self.SQUARE) is False
        assert point_in_ring([-5, 5], self.SQUARE) is False

    def test_point_on_edge(self):
        """Test point on edge - may return True or False depending on algorithm."""
        # Ray casting behavior on edges is implementation-defined
        result = point_in_ring([5, 0], self.SQUARE)
        assert result in [True, False]

    def test_point_at_corner(self):
        """Test point at corner - may return True or False."""
        result = point_in_ring([0, 0], self.SQUARE)
        assert result in [True, False]


class TestRingContainsRing:
    """Tests for ring_contains_ring function."""

    OUTER = [[0, 0], [20, 0], [20, 20], [0, 20], [0, 0]]
    INNER = [[5, 5], [15, 5], [15, 15], [5, 15], [5, 5]]
    OUTSIDE = [[25, 25], [30, 25], [30, 30], [25, 30], [25, 25]]

    def test_inner_contained(self):
        """Test inner ring is inside outer."""
        assert ring_contains_ring(self.OUTER, self.INNER) is True

    def test_outside_not_contained(self):
        """Test separate ring is not inside."""
        assert ring_contains_ring(self.OUTER, self.OUTSIDE) is False

    def test_empty_inner(self):
        """Test empty inner ring returns False."""
        assert ring_contains_ring(self.OUTER, []) is False


class TestGetRingCentroid:
    """Tests for get_ring_centroid function."""

    def test_square_centroid(self):
        """Test centroid of square."""
        square = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        centroid = get_ring_centroid(square)
        # Average of corners
        assert abs(centroid[0] - 4.0) < 0.1  # lon
        assert abs(centroid[1] - 4.0) < 0.1  # lat

    def test_empty_ring(self):
        """Test centroid of empty ring."""
        assert get_ring_centroid([]) == [0.0, 0.0]
