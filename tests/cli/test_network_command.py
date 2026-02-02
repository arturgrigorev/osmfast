"""Comprehensive tests for the network command - road graph export."""
import json
import csv
import io
import pytest
from argparse import Namespace
from pathlib import Path


class TestNetworkBasicExport:
    """Tests for basic network export functionality."""

    def test_network_json_export(self, road_network_osm, tmp_path):
        """Test basic JSON export."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "network.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        assert "metadata" in data
        assert "nodes" in data
        assert "edges" in data
        assert data["metadata"]["mode"] == "drive"
        assert data["metadata"]["directed"] is False
        assert len(data["nodes"]) > 0
        assert len(data["edges"]) > 0

    def test_network_geojson_export(self, road_network_osm, tmp_path):
        """Test GeoJSON export."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "network.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            format="geojson",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) > 0

        # Each feature should be a LineString edge
        for feature in data["features"]:
            assert feature["type"] == "Feature"
            assert feature["geometry"]["type"] == "LineString"
            assert len(feature["geometry"]["coordinates"]) == 2
            assert "highway" in feature["properties"]
            assert "length_m" in feature["properties"]

    def test_network_graphml_export(self, road_network_osm, tmp_path):
        """Test GraphML export."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "network.graphml"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            format="graphml",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        content = output_file.read_text()
        assert '<?xml version="1.0"' in content
        assert '<graphml' in content
        assert '<node id=' in content
        assert '<edge id=' in content
        assert 'edgedefault="undirected"' in content

    def test_network_csv_export(self, road_network_osm, tmp_path):
        """Test CSV export."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "network.csv"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            format="csv",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        content = output_file.read_text()
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)

        assert len(rows) > 0
        assert "from" in reader.fieldnames
        assert "to" in reader.fieldnames
        assert "highway" in reader.fieldnames
        assert "length_m" in reader.fieldnames


class TestNetworkTravelModes:
    """Tests for different travel modes."""

    @pytest.fixture
    def multi_mode_osm(self, tmp_path):
        """Create OSM with various road types for different modes."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="3" lat="-33.902" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="4" lat="-33.903" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="5" lat="-33.904" lon="151.200"><tag k="junction" v="yes"/></node>

  <!-- Motorway - drive only -->
  <way id="100">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="motorway"/>
    <tag k="name" v="Highway"/>
  </way>

  <!-- Residential - drive, walk, bike -->
  <way id="101">
    <nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="residential"/>
    <tag k="name" v="Residential St"/>
  </way>

  <!-- Footway - walk only -->
  <way id="102">
    <nd ref="3"/><nd ref="4"/>
    <tag k="highway" v="footway"/>
    <tag k="name" v="Footpath"/>
  </way>

  <!-- Cycleway - bike only -->
  <way id="103">
    <nd ref="4"/><nd ref="5"/>
    <tag k="highway" v="cycleway"/>
    <tag k="name" v="Bike Lane"/>
  </way>
</osm>'''
        osm_file = tmp_path / "multi_mode.osm"
        osm_file.write_text(content)
        return osm_file

    def test_drive_mode_filters(self, multi_mode_osm, tmp_path):
        """Test that drive mode only includes drivable roads."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "drive.json"
        args = Namespace(
            input=str(multi_mode_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        highway_types = {e["highway"] for e in data["edges"]}

        # Drive mode should include motorway and residential
        assert "motorway" in highway_types
        assert "residential" in highway_types
        # But not footway or cycleway
        assert "footway" not in highway_types
        assert "cycleway" not in highway_types

    def test_walk_mode_filters(self, multi_mode_osm, tmp_path):
        """Test that walk mode includes walkable roads."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "walk.json"
        args = Namespace(
            input=str(multi_mode_osm),
            output=str(output_file),
            format="json",
            mode="walk",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        highway_types = {e["highway"] for e in data["edges"]}

        # Walk mode should include residential and footway
        assert "residential" in highway_types
        assert "footway" in highway_types
        # But not motorway
        assert "motorway" not in highway_types

    def test_bike_mode_filters(self, multi_mode_osm, tmp_path):
        """Test that bike mode includes bikeable roads."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "bike.json"
        args = Namespace(
            input=str(multi_mode_osm),
            output=str(output_file),
            format="json",
            mode="bike",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        highway_types = {e["highway"] for e in data["edges"]}

        # Bike mode should include residential and cycleway
        assert "residential" in highway_types
        assert "cycleway" in highway_types
        # But not motorway or footway
        assert "motorway" not in highway_types

    def test_all_mode_includes_everything(self, multi_mode_osm, tmp_path):
        """Test that 'all' mode includes all road types."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "all.json"
        args = Namespace(
            input=str(multi_mode_osm),
            output=str(output_file),
            format="json",
            mode="all",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        highway_types = {e["highway"] for e in data["edges"]}

        # All mode should include everything
        assert "motorway" in highway_types
        assert "residential" in highway_types
        assert "footway" in highway_types
        assert "cycleway" in highway_types


class TestNetworkDirectedGraph:
    """Tests for directed graph export."""

    @pytest.fixture
    def oneway_network_osm(self, tmp_path):
        """Create OSM with oneway roads."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="3" lat="-33.902" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="4" lat="-33.901" lon="151.201"><tag k="junction" v="yes"/></node>

  <!-- Bidirectional road -->
  <way id="100">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="Main Street"/>
  </way>

  <!-- Oneway forward -->
  <way id="101">
    <nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="One Way Forward"/>
    <tag k="oneway" v="yes"/>
  </way>

  <!-- Oneway reverse (oneway=-1) -->
  <way id="102">
    <nd ref="2"/><nd ref="4"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="One Way Reverse"/>
    <tag k="oneway" v="-1"/>
  </way>
</osm>'''
        osm_file = tmp_path / "oneway.osm"
        osm_file.write_text(content)
        return osm_file

    def test_undirected_graph(self, oneway_network_osm, tmp_path):
        """Test undirected graph has single edge per road segment."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "undirected.json"
        args = Namespace(
            input=str(oneway_network_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["metadata"]["directed"] is False

        # Count edges - undirected should have one edge per segment
        # 3 ways = 3 edges
        assert len(data["edges"]) == 3

    def test_directed_graph_bidirectional(self, oneway_network_osm, tmp_path):
        """Test directed graph creates two edges for bidirectional roads."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "directed.json"
        args = Namespace(
            input=str(oneway_network_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=True,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["metadata"]["directed"] is True

        # Find edges for bidirectional Main Street
        main_street_edges = [e for e in data["edges"] if e.get("name") == "Main Street"]
        # Should have 2 edges (both directions)
        assert len(main_street_edges) == 2

        # Check both directions exist
        directions = {(e["from"], e["to"]) for e in main_street_edges}
        assert len(directions) == 2

    def test_directed_graph_oneway_forward(self, oneway_network_osm, tmp_path):
        """Test directed graph respects oneway=yes."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "directed.json"
        args = Namespace(
            input=str(oneway_network_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=True,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())

        # Find edges for oneway forward road
        oneway_edges = [e for e in data["edges"] if e.get("name") == "One Way Forward"]
        # Should have only 1 edge (one direction)
        assert len(oneway_edges) == 1
        # Should go from 2 to 3
        assert oneway_edges[0]["from"] == "2"
        assert oneway_edges[0]["to"] == "3"

    def test_directed_graph_oneway_reverse(self, oneway_network_osm, tmp_path):
        """Test directed graph respects oneway=-1."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "directed.json"
        args = Namespace(
            input=str(oneway_network_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=True,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())

        # Find edges for oneway reverse road
        reverse_edges = [e for e in data["edges"] if e.get("name") == "One Way Reverse"]
        # Should have only 1 edge
        assert len(reverse_edges) == 1
        # Should go from 4 to 2 (reversed)
        assert reverse_edges[0]["from"] == "4"
        assert reverse_edges[0]["to"] == "2"

    def test_graphml_directed_attribute(self, oneway_network_osm, tmp_path):
        """Test GraphML has correct edgedefault for directed graph."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "directed.graphml"
        args = Namespace(
            input=str(oneway_network_osm),
            output=str(output_file),
            format="graphml",
            mode="drive",
            directed=True,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        content = output_file.read_text()
        assert 'edgedefault="directed"' in content


class TestNetworkSpeeds:
    """Tests for speed estimation and travel times."""

    @pytest.fixture
    def speed_network_osm(self, tmp_path):
        """Create OSM with various speed configurations."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="3" lat="-33.902" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="4" lat="-33.903" lon="151.200"><tag k="junction" v="yes"/></node>

  <!-- Road with explicit maxspeed -->
  <way id="100">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="primary"/>
    <tag k="maxspeed" v="60"/>
  </way>

  <!-- Road with mph speed -->
  <way id="101">
    <nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
    <tag k="maxspeed" v="30 mph"/>
  </way>

  <!-- Road without speed (uses default) -->
  <way id="102">
    <nd ref="3"/><nd ref="4"/>
    <tag k="highway" v="residential"/>
  </way>
</osm>'''
        osm_file = tmp_path / "speeds.osm"
        osm_file.write_text(content)
        return osm_file

    def test_speeds_not_included_by_default(self, speed_network_osm, tmp_path):
        """Test that speeds are not included without --include-speeds."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "no_speeds.json"
        args = Namespace(
            input=str(speed_network_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        for edge in data["edges"]:
            assert "speed_kmh" not in edge
            assert "travel_time_s" not in edge

    def test_speeds_included_when_requested(self, speed_network_osm, tmp_path):
        """Test that speeds are included with --include-speeds."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "with_speeds.json"
        args = Namespace(
            input=str(speed_network_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=True,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        for edge in data["edges"]:
            assert "speed_kmh" in edge
            assert "travel_time_s" in edge
            assert edge["speed_kmh"] > 0
            assert edge["travel_time_s"] > 0

    def test_explicit_maxspeed_used(self, speed_network_osm, tmp_path):
        """Test that explicit maxspeed is used when available."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "speeds.json"
        args = Namespace(
            input=str(speed_network_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=True,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())

        # Find edge from way 100 (has maxspeed=60)
        edge_60 = [e for e in data["edges"] if e["from"] == "1" and e["to"] == "2"][0]
        assert edge_60["speed_kmh"] == 60

    def test_mph_speed_converted(self, speed_network_osm, tmp_path):
        """Test that mph speeds are converted to km/h."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "speeds.json"
        args = Namespace(
            input=str(speed_network_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=True,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())

        # Find edge from way 101 (has maxspeed=30 mph = ~48 km/h)
        edge_mph = [e for e in data["edges"] if e["from"] == "2" and e["to"] == "3"][0]
        assert 47 <= edge_mph["speed_kmh"] <= 49  # 30 mph ~= 48 km/h

    def test_default_speed_used_when_missing(self, speed_network_osm, tmp_path):
        """Test that default speed is used when maxspeed not specified."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "speeds.json"
        args = Namespace(
            input=str(speed_network_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=True,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())

        # Find edge from way 102 (residential, default 30 km/h)
        edge_default = [e for e in data["edges"] if e["from"] == "3" and e["to"] == "4"][0]
        assert edge_default["speed_kmh"] == 30  # Default for residential

    def test_csv_includes_speed_columns(self, speed_network_osm, tmp_path):
        """Test CSV format includes speed columns when requested."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "speeds.csv"
        args = Namespace(
            input=str(speed_network_osm),
            output=str(output_file),
            format="csv",
            mode="drive",
            directed=False,
            include_speeds=True,
            stats=False
        )
        result = run(args)
        assert result == 0

        content = output_file.read_text()
        reader = csv.DictReader(io.StringIO(content))

        assert "speed_kmh" in reader.fieldnames
        assert "travel_time_s" in reader.fieldnames


class TestNetworkStatistics:
    """Tests for network statistics mode."""

    def test_stats_mode_basic(self, road_network_osm, capsys):
        """Test basic statistics output."""
        from osm_core.cli.commands.network import run

        args = Namespace(
            input=str(road_network_osm),
            output=None,
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=True
        )
        result = run(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "Network Statistics" in captured.out
        assert "Nodes:" in captured.out
        assert "Edges:" in captured.out
        assert "Total length:" in captured.out

    def test_stats_shows_topology(self, road_network_osm, capsys):
        """Test statistics includes topology info."""
        from osm_core.cli.commands.network import run

        args = Namespace(
            input=str(road_network_osm),
            output=None,
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=True
        )
        result = run(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "Topology:" in captured.out
        assert "Dead ends:" in captured.out
        assert "Intersections" in captured.out

    def test_stats_shows_highway_breakdown(self, road_network_osm, capsys):
        """Test statistics includes highway type breakdown."""
        from osm_core.cli.commands.network import run

        args = Namespace(
            input=str(road_network_osm),
            output=None,
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=True
        )
        result = run(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "By highway type:" in captured.out

    def test_stats_no_output_file_required(self, road_network_osm, tmp_path):
        """Test stats mode doesn't require output file."""
        from osm_core.cli.commands.network import run

        args = Namespace(
            input=str(road_network_osm),
            output=None,
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=True
        )
        result = run(args)
        assert result == 0


class TestNetworkEdgeCases:
    """Tests for edge cases and error handling."""

    def test_missing_file(self, tmp_path):
        """Test error handling for missing file."""
        from osm_core.cli.commands.network import run

        args = Namespace(
            input=str(tmp_path / "nonexistent.osm"),
            output=str(tmp_path / "output.json"),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 1

    def test_missing_output_without_stats(self, road_network_osm):
        """Test error when output not specified and not in stats mode."""
        from osm_core.cli.commands.network import run

        args = Namespace(
            input=str(road_network_osm),
            output=None,
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 1

    def test_empty_network(self, tmp_path):
        """Test handling of OSM with no roads."""
        osm_file = tmp_path / "empty.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="amenity" v="restaurant"/>
  </node>
</osm>''')

        from osm_core.cli.commands.network import run

        output_file = tmp_path / "empty.json"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert len(data["nodes"]) == 0
        assert len(data["edges"]) == 0


class TestNetworkEdgeAttributes:
    """Tests for edge attribute correctness."""

    def test_edge_has_required_attributes(self, road_network_osm, tmp_path):
        """Test edges have all required attributes."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "network.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        for edge in data["edges"]:
            assert "way_id" in edge
            assert "from" in edge
            assert "to" in edge
            assert "highway" in edge
            assert "length_m" in edge
            assert "oneway" in edge

    def test_edge_length_positive(self, road_network_osm, tmp_path):
        """Test all edge lengths are positive."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "network.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        for edge in data["edges"]:
            assert edge["length_m"] > 0

    def test_node_has_coordinates(self, road_network_osm, tmp_path):
        """Test all nodes have valid coordinates."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "network.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        for node in data["nodes"]:
            assert "id" in node
            assert "lon" in node
            assert "lat" in node
            assert -180 <= node["lon"] <= 180
            assert -90 <= node["lat"] <= 90


class TestNetworkMultiSegmentWays:
    """Tests for ways with multiple segments."""

    @pytest.fixture
    def multi_segment_osm(self, tmp_path):
        """Create OSM with a multi-segment way."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="3" lat="-33.902" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="4" lat="-33.903" lon="151.200"><tag k="junction" v="yes"/></node>

  <!-- Way with 4 nodes = 3 segments -->
  <way id="100">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="Long Road"/>
  </way>
</osm>'''
        osm_file = tmp_path / "multi_segment.osm"
        osm_file.write_text(content)
        return osm_file

    def test_multi_segment_creates_multiple_edges(self, multi_segment_osm, tmp_path):
        """Test that multi-segment way creates one edge per segment."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "network.json"
        args = Namespace(
            input=str(multi_segment_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())

        # Way with 4 nodes should create 3 edges
        edges = [e for e in data["edges"] if e["way_id"] == "100"]
        assert len(edges) == 3

        # Check connectivity
        edge_pairs = [(e["from"], e["to"]) for e in edges]
        assert ("1", "2") in edge_pairs
        assert ("2", "3") in edge_pairs
        assert ("3", "4") in edge_pairs

    def test_all_intermediate_nodes_included(self, multi_segment_osm, tmp_path):
        """Test all intermediate nodes are in the graph."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "network.json"
        args = Namespace(
            input=str(multi_segment_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        node_ids = {n["id"] for n in data["nodes"]}

        assert "1" in node_ids
        assert "2" in node_ids
        assert "3" in node_ids
        assert "4" in node_ids


class TestNetworkRoadNames:
    """Tests for road name handling."""

    @pytest.fixture
    def named_roads_osm(self, tmp_path):
        """Create OSM with named and unnamed roads."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="3" lat="-33.902" lon="151.200"><tag k="junction" v="yes"/></node>

  <way id="100">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="Main Street"/>
  </way>

  <way id="101">
    <nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="service"/>
  </way>
</osm>'''
        osm_file = tmp_path / "named.osm"
        osm_file.write_text(content)
        return osm_file

    def test_named_roads_have_name(self, named_roads_osm, tmp_path):
        """Test named roads have name attribute."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "network.json"
        args = Namespace(
            input=str(named_roads_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        named_edge = [e for e in data["edges"] if e["way_id"] == "100"][0]
        assert named_edge["name"] == "Main Street"

    def test_unnamed_roads_have_null_name(self, named_roads_osm, tmp_path):
        """Test unnamed roads have null name."""
        from osm_core.cli.commands.network import run

        output_file = tmp_path / "network.json"
        args = Namespace(
            input=str(named_roads_osm),
            output=str(output_file),
            format="json",
            mode="drive",
            directed=False,
            include_speeds=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        unnamed_edge = [e for e in data["edges"] if e["way_id"] == "101"][0]
        assert unnamed_edge["name"] is None
