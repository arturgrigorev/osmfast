"""Tests for routing CLI commands."""
import json
import pytest
from argparse import Namespace

from osm_core.cli.commands import route, route_multi, directions, alternatives


class TestRouteCommand:
    """Tests for route command."""

    def test_route_basic(self, road_network_osm):
        """Test basic routing between two points."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 0

    def test_route_json_output(self, road_network_osm, tmp_path):
        """Test route with JSON output."""
        output_file = tmp_path / "route.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format="json"
        )
        result = route.run(args)
        assert result == 0
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        # Output format is GeoJSON FeatureCollection when output file specified
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) >= 1

    def test_route_geojson_output(self, road_network_osm, tmp_path):
        """Test route with GeoJSON output."""
        output_file = tmp_path / "route.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format="geojson"
        )
        result = route.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) >= 1

    def test_route_walk_mode(self, road_network_osm):
        """Test routing with walk mode."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="walk",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 0

    def test_route_bike_mode(self, road_network_osm):
        """Test routing with bike mode."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="bike",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 0

    def test_route_optimize_distance(self, road_network_osm):
        """Test routing optimized for distance."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            optimize="distance",
            format="text"
        )
        result = route.run(args)
        assert result == 0

    def test_route_invalid_coords(self, road_network_osm):
        """Test routing with invalid coordinates."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="invalid",
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 1

    def test_route_missing_file(self, tmp_path):
        """Test routing with missing file."""
        args = Namespace(
            input=str(tmp_path / "nonexistent.osm"),
            output=None,
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 1

    def test_route_no_path(self, disconnected_network_osm):
        """Test routing when no path exists."""
        args = Namespace(
            input=str(disconnected_network_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.910,151.210",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 1


class TestRouteMultiCommand:
    """Tests for route-multi command."""

    def test_route_multi_basic(self, road_network_osm):
        """Test multi-waypoint routing."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            waypoints="-33.900,151.200;-33.901,151.200;-33.902,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route_multi.run(args)
        assert result == 0

    def test_route_multi_json(self, road_network_osm, tmp_path):
        """Test multi-waypoint routing with JSON output."""
        output_file = tmp_path / "route_multi.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            waypoints="-33.900,151.200;-33.901,151.200;-33.902,151.200",
            mode="drive",
            optimize="time",
            format="json"
        )
        result = route_multi.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert "legs" in data
        assert "total_distance_m" in data
        assert len(data["legs"]) == 2

    def test_route_multi_invalid_waypoints(self, road_network_osm):
        """Test with invalid waypoints format."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            waypoints="invalid",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route_multi.run(args)
        assert result == 1


class TestDirectionsCommand:
    """Tests for directions command."""

    def test_directions_basic(self, road_network_osm):
        """Test basic turn-by-turn directions."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            format="text"
        )
        result = directions.run(args)
        assert result == 0

    def test_directions_json(self, road_network_osm, tmp_path):
        """Test directions with JSON output."""
        output_file = tmp_path / "directions.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            format="json"
        )
        result = directions.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert "instructions" in data
        assert "total_distance_m" in data


class TestAlternativesCommand:
    """Tests for alternatives command."""

    def test_alternatives_basic(self, road_network_osm):
        """Test finding alternative routes."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            count=3,
            format="text"
        )
        result = alternatives.run(args)
        assert result == 0

    def test_alternatives_json(self, road_network_osm, tmp_path):
        """Test alternatives with JSON output."""
        output_file = tmp_path / "alternatives.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            count=2,
            format="json"
        )
        result = alternatives.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Output format is GeoJSON FeatureCollection when output file specified
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) >= 1
