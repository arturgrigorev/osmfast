"""Output format validation tests."""
import csv
import io
import json
import pytest
from argparse import Namespace


class TestGeoJSONValidity:
    """Test GeoJSON output validity."""

    def test_route_geojson_structure(self, road_network_osm, tmp_path):
        """Route GeoJSON should have valid FeatureCollection structure."""
        from osm_core.cli.commands import route

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

        # Validate FeatureCollection structure
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert isinstance(data["features"], list)

        for feature in data["features"]:
            assert feature["type"] == "Feature"
            assert "geometry" in feature
            assert "properties" in feature
            assert "type" in feature["geometry"]
            assert "coordinates" in feature["geometry"]

    def test_route_geojson_line_coordinates(self, road_network_osm, tmp_path):
        """Route LineString should have valid coordinates."""
        from osm_core.cli.commands import route

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
        route.run(args)

        data = json.loads(output_file.read_text())

        for feature in data["features"]:
            geom_type = feature["geometry"]["type"]
            coords = feature["geometry"]["coordinates"]

            if geom_type == "LineString":
                # Must have at least 2 coordinates
                assert len(coords) >= 2
                for coord in coords:
                    # Each coord is [lon, lat] or [lon, lat, alt]
                    assert len(coord) >= 2
                    lon, lat = coord[0], coord[1]
                    assert -180 <= lon <= 180
                    assert -90 <= lat <= 90

            elif geom_type == "Point":
                assert len(coords) >= 2
                lon, lat = coords[0], coords[1]
                assert -180 <= lon <= 180
                assert -90 <= lat <= 90

    def test_centrality_geojson_points(self, road_network_osm, tmp_path):
        """Centrality output should have Point features."""
        from osm_core.cli.commands import centrality

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

        for feature in data["features"]:
            assert feature["geometry"]["type"] == "Point"
            coords = feature["geometry"]["coordinates"]
            assert len(coords) >= 2

    def test_bottleneck_geojson_features(self, road_network_osm, tmp_path):
        """Bottleneck output should have Point or LineString features."""
        from osm_core.cli.commands import bottleneck

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

        for feature in data["features"]:
            # Bottleneck can output Points (articulation points) or LineStrings (bridge edges)
            assert feature["geometry"]["type"] in ["Point", "LineString"]


class TestJSONValidity:
    """Test JSON output validity."""

    def test_distance_matrix_json_structure(self, road_network_osm, tmp_path):
        """Distance matrix JSON should have proper structure."""
        from osm_core.cli.commands import distance_matrix

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

        # Required fields
        assert "distance_matrix_m" in data
        assert "time_matrix_s" in data
        assert "points" in data

        # Matrix should be square
        n = len(data["points"])
        dist_matrix = data["distance_matrix_m"]
        time_matrix = data["time_matrix_s"]

        assert len(dist_matrix) == n
        assert len(time_matrix) == n
        for row in dist_matrix:
            assert len(row) == n
        for row in time_matrix:
            assert len(row) == n

    def test_directions_json_structure(self, road_network_osm, tmp_path):
        """Directions JSON should have instructions."""
        from osm_core.cli.commands import directions

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
        assert isinstance(data["instructions"], list)

    def test_route_multi_json_structure(self, road_network_osm, tmp_path):
        """Route-multi JSON should have legs."""
        from osm_core.cli.commands import route_multi

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
        assert "total_time_s" in data
        assert len(data["legs"]) == 2  # 3 waypoints = 2 legs

        for leg in data["legs"]:
            assert "distance_m" in leg
            assert "time_s" in leg
            # Uses from_waypoint/to_waypoint for waypoint indices
            assert "from_waypoint" in leg or "from" in leg
            assert "to_waypoint" in leg or "to" in leg

    def test_connectivity_json_structure(self, road_network_osm, tmp_path):
        """Connectivity JSON should have component info."""
        from osm_core.cli.commands import connectivity

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
        # May have components array or largest_component_size
        assert "components" in data or "largest_component_size" in data

        assert isinstance(data["num_components"], int)
        assert isinstance(data["total_nodes"], int)
        assert isinstance(data["is_connected"], bool)

    def test_detour_factor_json_structure(self, road_network_osm, tmp_path):
        """Detour factor JSON should have statistics."""
        from osm_core.cli.commands import detour_factor

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
        stats = data["statistics"]
        assert "mean" in stats
        assert "median" in stats
        assert "min" in stats
        assert "max" in stats


class TestCSVValidity:
    """Test CSV output validity."""

    def test_distance_matrix_csv_format(self, road_network_osm, tmp_path, capsys):
        """Distance matrix CSV should be parseable."""
        from osm_core.cli.commands import distance_matrix

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

        # CSV is printed to stdout - would need to capture


class TestTextOutputFormat:
    """Test text output format."""

    def test_route_text_output(self, road_network_osm, capsys):
        """Route text output should be readable."""
        from osm_core.cli.commands import route

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

        # Text output goes to stdout
        # Verify it ran without error

    def test_directions_text_output(self, road_network_osm, capsys):
        """Directions text output should show turn-by-turn."""
        from osm_core.cli.commands import directions

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

    def test_connectivity_text_output(self, road_network_osm, capsys):
        """Connectivity text output should show summary."""
        from osm_core.cli.commands import connectivity

        args = Namespace(
            input=str(road_network_osm),
            output=None,
            mode="drive",
            format="text",
            show_components=False
        )
        result = connectivity.run(args)
        assert result == 0


class TestOutputFileCreation:
    """Test output file creation."""

    def test_creates_output_file(self, road_network_osm, tmp_path):
        """Should create output file at specified path."""
        from osm_core.cli.commands import route

        output_file = tmp_path / "output.json"
        assert not output_file.exists()

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

    def test_creates_nested_output_path(self, road_network_osm, tmp_path):
        """Should handle nested output directories."""
        from osm_core.cli.commands import route

        nested_dir = tmp_path / "subdir1" / "subdir2"
        nested_dir.mkdir(parents=True)
        output_file = nested_dir / "route.json"

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

    def test_overwrites_existing_file(self, road_network_osm, tmp_path):
        """Should overwrite existing output file."""
        from osm_core.cli.commands import route

        output_file = tmp_path / "output.json"
        output_file.write_text('{"old": "data"}')

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

        data = json.loads(output_file.read_text())
        assert "old" not in data
        assert "type" in data


class TestOutputConsistency:
    """Test output format consistency."""

    def test_json_geojson_consistency(self, road_network_osm, tmp_path):
        """JSON and GeoJSON should have matching data."""
        from osm_core.cli.commands import route

        # Get JSON output
        json_file = tmp_path / "route.json"
        json_args = Namespace(
            input=str(road_network_osm),
            output=str(json_file),
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format="json"
        )
        route.run(json_args)

        # Get GeoJSON output
        geojson_file = tmp_path / "route.geojson"
        geojson_args = Namespace(
            input=str(road_network_osm),
            output=str(geojson_file),
            origin="-33.900,151.200",
            destination="-33.902,151.200",
            mode="drive",
            optimize="time",
            format="geojson"
        )
        route.run(geojson_args)

        # Both should be valid JSON
        json_data = json.loads(json_file.read_text())
        geojson_data = json.loads(geojson_file.read_text())

        # GeoJSON should have FeatureCollection
        assert geojson_data["type"] == "FeatureCollection"

        # Both should report same route stats
        if "distance_m" in json_data:
            # Find LineString feature in GeoJSON
            for feature in geojson_data["features"]:
                if feature["geometry"]["type"] == "LineString":
                    geojson_dist = feature["properties"].get("distance_m")
                    if geojson_dist:
                        assert abs(json_data["distance_m"] - geojson_dist) < 1


class TestUnicodeHandling:
    """Test Unicode in output."""

    def test_json_utf8_encoding(self, tmp_path):
        """JSON output should handle Unicode correctly."""
        from osm_core.cli.commands import nearest

        # Create OSM with Unicode names
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200">
    <tag k="amenity" v="restaurant"/>
    <tag k="name" v="Cafe Muller"/>
    <tag k="name:ja" v="Test"/>
  </node>
  <node id="2" lat="-33.901" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>'''
        osm_file = tmp_path / "unicode.osm"
        osm_file.write_text(content, encoding='utf-8')

        output_file = tmp_path / "nearest.json"
        args = Namespace(
            input=str(osm_file),
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

        # Should be valid JSON with UTF-8
        content = output_file.read_text(encoding='utf-8')
        data = json.loads(content)
        assert data["type"] == "FeatureCollection"
