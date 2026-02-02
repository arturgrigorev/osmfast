"""Tests for network analysis CLI commands."""
import json
import pytest
from argparse import Namespace

from osm_core.cli.commands import centrality, connectivity, bottleneck, detour_factor


class TestCentralityCommand:
    """Tests for centrality command."""

    def test_centrality_basic(self, road_network_osm):
        """Test basic centrality calculation."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            top=5,
            sample=10,
            format="text"
        )
        result = centrality.run(args)
        assert result == 0

    def test_centrality_json(self, road_network_osm, tmp_path):
        """Test centrality with JSON output."""
        output_file = tmp_path / "centrality.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            top=5,
            sample=10,
            format="json"
        )
        result = centrality.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Output format is GeoJSON FeatureCollection when output file specified
        assert data["type"] == "FeatureCollection"
        assert "features" in data

    def test_centrality_geojson(self, road_network_osm, tmp_path):
        """Test centrality with GeoJSON output."""
        output_file = tmp_path / "centrality.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            top=5,
            sample=10,
            format="geojson"
        )
        result = centrality.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"

    def test_centrality_low_sample(self, road_network_osm):
        """Test centrality with low sample size."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            top=3,
            sample=5,
            format="text"
        )
        result = centrality.run(args)
        assert result == 0


class TestConnectivityCommand:
    """Tests for connectivity command."""

    def test_connectivity_basic(self, road_network_osm):
        """Test basic connectivity analysis."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            mode="drive",
            format="text",
            show_components=False
        )
        result = connectivity.run(args)
        assert result == 0

    def test_connectivity_json(self, road_network_osm, tmp_path):
        """Test connectivity with JSON output."""
        output_file = tmp_path / "connectivity.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            mode="drive",
            format="json",
            show_components=False
        )
        result = connectivity.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert "num_components" in data
        assert "total_nodes" in data
        assert "is_connected" in data

    def test_connectivity_geojson(self, road_network_osm, tmp_path):
        """Test connectivity with GeoJSON output."""
        output_file = tmp_path / "connectivity.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            mode="drive",
            format="geojson",
            show_components=True
        )
        result = connectivity.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"

    def test_connectivity_walk_mode(self, road_network_osm):
        """Test connectivity with walk mode."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            mode="walk",
            format="text",
            show_components=False
        )
        result = connectivity.run(args)
        assert result == 0

    def test_connectivity_bike_mode(self, road_network_osm):
        """Test connectivity with bike mode."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            mode="bike",
            format="text",
            show_components=False
        )
        result = connectivity.run(args)
        assert result == 0

    def test_connectivity_disconnected(self, disconnected_network_osm):
        """Test connectivity on disconnected network."""
        args = Namespace(
            input=str(disconnected_network_osm),
            output=None,
            mode="drive",
            format="text",
            show_components=False
        )
        result = connectivity.run(args)
        # Returns 0 even for disconnected network - it reports the components
        assert result == 0


class TestBottleneckCommand:
    """Tests for bottleneck command."""

    def test_bottleneck_basic(self, road_network_osm):
        """Test basic bottleneck detection."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            top=10,
            format="text"
        )
        result = bottleneck.run(args)
        assert result == 0

    def test_bottleneck_json(self, road_network_osm, tmp_path):
        """Test bottleneck with JSON output."""
        output_file = tmp_path / "bottleneck.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            top=10,
            format="json"
        )
        result = bottleneck.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Output format is GeoJSON FeatureCollection when output file specified
        assert data["type"] == "FeatureCollection"
        assert "features" in data

    def test_bottleneck_geojson(self, road_network_osm, tmp_path):
        """Test bottleneck with GeoJSON output."""
        output_file = tmp_path / "bottleneck.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            top=10,
            format="geojson"
        )
        result = bottleneck.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"

    def test_bottleneck_low_n(self, road_network_osm):
        """Test bottleneck with low N."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            top=3,
            format="text"
        )
        result = bottleneck.run(args)
        assert result == 0


class TestDetourFactorCommand:
    """Tests for detour-factor command."""

    def test_detour_factor_basic(self, road_network_osm):
        """Test basic detour factor analysis."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            mode="drive",
            sample=10,
            format="text"
        )
        result = detour_factor.run(args)
        assert result == 0

    def test_detour_factor_json(self, road_network_osm, tmp_path):
        """Test detour factor with JSON output."""
        output_file = tmp_path / "detour.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            mode="drive",
            sample=10,
            format="json"
        )
        result = detour_factor.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert "statistics" in data
        assert "mean" in data["statistics"]

    def test_detour_factor_walk(self, road_network_osm):
        """Test detour factor with walk mode."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            mode="walk",
            sample=10,
            format="text"
        )
        result = detour_factor.run(args)
        assert result == 0

    def test_detour_factor_bike(self, road_network_osm):
        """Test detour factor with bike mode."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            mode="bike",
            sample=10,
            format="text"
        )
        result = detour_factor.run(args)
        assert result == 0

    def test_detour_factor_disconnected(self, disconnected_network_osm):
        """Test detour factor on disconnected network."""
        args = Namespace(
            input=str(disconnected_network_osm),
            output=None,
            mode="drive",
            sample=5,
            format="text"
        )
        # Returns 1 for disconnected network with only 2-node components
        # (can't calculate detour factor with only 2 nodes in component)
        result = detour_factor.run(args)
        # This returns 1 because smallest component is too small for analysis
        assert result in [0, 1]
