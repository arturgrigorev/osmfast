"""Tests for distance CLI commands."""
import json
import pytest
from argparse import Namespace

from osm_core.cli.commands import distance_matrix, nearest, nearest_road


class TestDistanceMatrixCommand:
    """Tests for distance-matrix command."""

    def test_distance_matrix_basic(self, road_network_osm):
        """Test basic distance matrix calculation."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            points="-33.900,151.200;-33.901,151.200",
            mode="drive",
            metric="both",
            format="text"
        )
        result = distance_matrix.run(args)
        assert result == 0

    def test_distance_matrix_json(self, road_network_osm, tmp_path):
        """Test distance matrix with JSON output."""
        output_file = tmp_path / "matrix.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            points="-33.900,151.200;-33.901,151.200;-33.902,151.200",
            mode="drive",
            metric="both",
            format="json"
        )
        result = distance_matrix.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert "distance_matrix_m" in data
        assert "time_matrix_s" in data
        assert len(data["distance_matrix_m"]) == 3

    def test_distance_matrix_csv(self, road_network_osm):
        """Test distance matrix with CSV output."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            points="-33.900,151.200;-33.901,151.200",
            mode="drive",
            metric="both",
            format="csv"
        )
        result = distance_matrix.run(args)
        assert result == 0

    def test_distance_matrix_walk(self, road_network_osm):
        """Test distance matrix with walk mode."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            points="-33.900,151.200;-33.901,151.200",
            mode="walk",
            metric="both",
            format="text"
        )
        result = distance_matrix.run(args)
        assert result == 0

    def test_distance_matrix_invalid_points(self, road_network_osm):
        """Test distance matrix with invalid points."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            points="invalid",
            mode="drive",
            metric="both",
            format="text"
        )
        result = distance_matrix.run(args)
        assert result == 1


class TestNearestCommand:
    """Tests for nearest command."""

    def test_nearest_basic(self, road_network_osm):
        """Test finding nearest features."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.900,
            lon=151.200,
            filter="amenity=*",
            count=5,
            max_distance=None,
            format="text"
        )
        result = nearest.run(args)
        assert result == 0

    def test_nearest_json(self, road_network_osm, tmp_path):
        """Test nearest with JSON output."""
        output_file = tmp_path / "nearest.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            lat=-33.900,
            lon=151.200,
            filter="amenity=*",
            count=5,
            max_distance=None,
            format="json"
        )
        result = nearest.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Output format is GeoJSON FeatureCollection when output file specified
        assert data["type"] == "FeatureCollection"
        assert "features" in data

    def test_nearest_geojson(self, road_network_osm, tmp_path):
        """Test nearest with GeoJSON output."""
        output_file = tmp_path / "nearest.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            lat=-33.900,
            lon=151.200,
            filter="shop=*",
            count=5,
            max_distance=None,
            format="geojson"
        )
        result = nearest.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"

    def test_nearest_with_max_distance(self, road_network_osm):
        """Test nearest with max distance filter."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.900,
            lon=151.200,
            filter="amenity=*",
            count=5,
            max_distance=100,
            format="text"
        )
        result = nearest.run(args)
        assert result == 0

    def test_nearest_no_results(self, road_network_osm):
        """Test nearest when no features match."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.900,
            lon=151.200,
            filter="nonexistent=tag",
            count=5,
            max_distance=None,
            format="text"
        )
        result = nearest.run(args)
        assert result == 0  # Should succeed but with empty results


class TestNearestRoadCommand:
    """Tests for nearest-road command."""

    def test_nearest_road_basic(self, road_network_osm):
        """Test snapping point to nearest road."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.9005,
            lon=151.2005,
            mode="all",
            format="text"
        )
        result = nearest_road.run(args)
        assert result == 0

    def test_nearest_road_json(self, road_network_osm, tmp_path):
        """Test nearest road with JSON output."""
        output_file = tmp_path / "snapped.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            lat=-33.9005,
            lon=151.2005,
            mode="all",
            format="json"
        )
        result = nearest_road.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Output format is GeoJSON FeatureCollection when output file specified
        assert data["type"] == "FeatureCollection"
        assert "features" in data

    def test_nearest_road_geojson(self, road_network_osm, tmp_path):
        """Test nearest road with GeoJSON output."""
        output_file = tmp_path / "snapped.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            lat=-33.9005,
            lon=151.2005,
            mode="all",
            format="geojson"
        )
        result = nearest_road.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"

    def test_nearest_road_drive_mode(self, road_network_osm):
        """Test snapping to drive-accessible roads only."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.9005,
            lon=151.2005,
            mode="drive",
            format="text"
        )
        result = nearest_road.run(args)
        assert result == 0

    def test_nearest_road_walk_mode(self, road_network_osm):
        """Test snapping to walk-accessible roads only."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.9005,
            lon=151.2005,
            mode="walk",
            format="text"
        )
        result = nearest_road.run(args)
        assert result == 0
