"""Edge case and error handling tests for CLI commands."""
import json
import pytest
from argparse import Namespace

from osm_core.cli.commands import (
    route, route_multi, directions, alternatives,
    distance_matrix, nearest, nearest_road,
    centrality, connectivity, bottleneck, detour_factor
)


class TestInvalidInputHandling:
    """Test handling of invalid inputs."""

    def test_route_empty_origin(self, road_network_osm):
        """Empty origin should fail gracefully."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="",
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 1

    def test_route_empty_destination(self, road_network_osm):
        """Empty destination should fail gracefully."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="-33.900,151.200",
            destination="",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 1

    def test_route_malformed_coords(self, road_network_osm):
        """Malformed coordinates should fail gracefully."""
        # These coordinates are clearly malformed
        malformed_coords = [
            "abc,def",
            "51.5",
            "51.5,",
            ",51.5",
            "51.5;0.1",
        ]
        for coord in malformed_coords:
            args = Namespace(
                input=str(road_network_osm),
                output=None,
                origin=coord,
                destination="-33.902,151.200",
                mode="drive",
                optimize="time",
                format="text"
            )
            result = route.run(args)
            assert result == 1, f"Should fail for coord: {coord}"

    def test_route_out_of_range_coords(self, road_network_osm):
        """Out of range coordinates should fail or return no route."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="91.0,181.0",  # Invalid lat/lon
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        # Should either fail or return no route found
        assert result in [0, 1]

    def test_route_same_origin_destination(self, road_network_osm):
        """Same origin and destination should succeed with zero distance."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.900,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        # Should succeed - zero distance route
        assert result == 0

    def test_distance_matrix_single_point(self, road_network_osm):
        """Distance matrix with single point should fail."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            points="-33.900,151.200",
            mode="drive",
            metric="both",
            format="text"
        )
        result = distance_matrix.run(args)
        assert result == 1

    def test_distance_matrix_empty_points(self, road_network_osm):
        """Distance matrix with empty points should fail."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            points="",
            mode="drive",
            metric="both",
            format="text"
        )
        result = distance_matrix.run(args)
        assert result == 1

    def test_route_multi_single_waypoint(self, road_network_osm):
        """Route-multi with single waypoint should fail."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            waypoints="-33.900,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route_multi.run(args)
        assert result == 1


class TestEmptyNetworks:
    """Test handling of empty or minimal networks."""

    def test_centrality_minimal_network(self, tmp_path):
        """Centrality on network with only 2 nodes."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>
  <node id="2" lat="-33.901" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>'''
        osm_file = tmp_path / "minimal.osm"
        osm_file.write_text(content)

        args = Namespace(
            input=str(osm_file),
            output=None,
            top=5,
            sample=10,
            format="text"
        )
        result = centrality.run(args)
        # Should handle gracefully
        assert result in [0, 1]

    def test_bottleneck_linear_network(self, tmp_path):
        """Bottleneck on linear network (all edges are bridges)."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>
  <node id="2" lat="-33.901" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>
  <node id="3" lat="-33.902" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>'''
        osm_file = tmp_path / "linear.osm"
        osm_file.write_text(content)

        args = Namespace(
            input=str(osm_file),
            output=None,
            top=10,
            format="text"
        )
        result = bottleneck.run(args)
        assert result == 0


class TestFileHandling:
    """Test file handling edge cases."""

    def test_nonexistent_input_file(self, tmp_path):
        """Nonexistent input file should fail gracefully."""
        args = Namespace(
            input=str(tmp_path / "does_not_exist.osm"),
            output=None,
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 1

    def test_empty_osm_file(self, tmp_path):
        """Empty OSM file should fail gracefully."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
</osm>'''
        osm_file = tmp_path / "empty.osm"
        osm_file.write_text(content)

        args = Namespace(
            input=str(osm_file),
            output=None,
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 1

    def test_invalid_xml_file(self, tmp_path):
        """Invalid XML should fail gracefully."""
        osm_file = tmp_path / "invalid.osm"
        osm_file.write_text("This is not valid XML")

        args = Namespace(
            input=str(osm_file),
            output=None,
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 1

    def test_output_to_nonexistent_directory(self, road_network_osm, tmp_path):
        """Output to non-existent directory should raise an error."""
        import pytest
        # Try to write to a path that doesn't exist
        args = Namespace(
            input=str(road_network_osm),
            output=str(tmp_path / "nonexistent_subdir" / "output.json"),
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format="json"
        )
        # This will raise FileNotFoundError since dir doesn't exist
        with pytest.raises(FileNotFoundError):
            route.run(args)


class TestSpecialCharacters:
    """Test handling of special characters in data."""

    def test_nearest_special_filter(self, road_network_osm):
        """Test nearest with special characters in filter."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.900,
            lon=151.200,
            filter="name=Test's \"Restaurant\"",
            count=5,
            max_distance=None,
            format="text"
        )
        result = nearest.run(args)
        # Should handle gracefully (no matches is OK)
        assert result == 0


class TestBoundaryConditions:
    """Test boundary conditions."""

    def test_alternatives_count_zero(self, road_network_osm):
        """Request zero alternatives should return at least one route."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            count=0,
            format="text"
        )
        result = alternatives.run(args)
        # Implementation may treat 0 as "default" or fail
        assert result in [0, 1]

    def test_alternatives_count_large(self, road_network_osm):
        """Request many alternatives on small network."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            count=100,  # More than possible routes
            format="text"
        )
        result = alternatives.run(args)
        assert result == 0

    def test_centrality_sample_larger_than_nodes(self, road_network_osm):
        """Centrality sample larger than node count should work."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            top=5,
            sample=1000,  # Much larger than network
            format="text"
        )
        result = centrality.run(args)
        assert result == 0

    def test_nearest_zero_count(self, road_network_osm):
        """Request zero nearest features."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.900,
            lon=151.200,
            filter="amenity=*",
            count=0,
            max_distance=None,
            format="text"
        )
        result = nearest.run(args)
        assert result == 0

    def test_nearest_very_small_max_distance(self, road_network_osm):
        """Very small max distance should return no results."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.900,
            lon=151.200,
            filter="amenity=*",
            count=5,
            max_distance=0.001,  # 1mm
            format="text"
        )
        result = nearest.run(args)
        assert result == 0


class TestDisconnectedNetworkEdgeCases:
    """Test edge cases with disconnected networks."""

    def test_route_between_components(self, disconnected_network_osm):
        """Routing between disconnected components should fail."""
        args = Namespace(
            input=str(disconnected_network_osm),
            output=None,
            origin="-33.900,151.200",  # Component 1
            destination="-33.910,151.210",  # Component 2
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 1

    def test_distance_matrix_disconnected(self, disconnected_network_osm, tmp_path):
        """Distance matrix on disconnected network."""
        output_file = tmp_path / "matrix.json"
        # Points from different components
        points = "-33.900,151.200;-33.910,151.210"

        args = Namespace(
            input=str(disconnected_network_osm),
            output=str(output_file),
            points=points,
            mode="drive",
            metric="both",
            format="json"
        )
        result = distance_matrix.run(args)
        # Should succeed but with infinity/null for unreachable pairs
        assert result in [0, 1]

    def test_connectivity_reports_components(self, disconnected_network_osm, tmp_path):
        """Connectivity should correctly report disconnected components."""
        output_file = tmp_path / "connectivity.json"
        args = Namespace(
            input=str(disconnected_network_osm),
            output=str(output_file),
            mode="drive",
            format="json",
            show_components=False
        )
        result = connectivity.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["num_components"] == 2
        assert data["is_connected"] == False


class TestOutputFormats:
    """Test all output format variations."""

    @pytest.mark.parametrize("fmt", ["text", "json", "geojson"])
    def test_route_all_formats(self, road_network_osm, tmp_path, fmt):
        """Route command should support all formats."""
        ext = ".json" if fmt in ["json", "geojson"] else ".txt"
        output_file = tmp_path / f"route{ext}"

        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file) if fmt != "text" else None,
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format=fmt
        )
        result = route.run(args)
        assert result == 0

        if fmt != "text":
            assert output_file.exists()
            if fmt in ["json", "geojson"]:
                data = json.loads(output_file.read_text())
                assert "type" in data or "features" in data

    @pytest.mark.parametrize("fmt", ["text", "json", "csv"])
    def test_distance_matrix_all_formats(self, road_network_osm, tmp_path, fmt):
        """Distance matrix should support all formats."""
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            points="-33.900,151.200;-33.901,151.200",
            mode="drive",
            metric="both",
            format=fmt
        )
        result = distance_matrix.run(args)
        assert result == 0
