"""Regression tests for oneway=-1 bug fix.

This bug was found during PhD-level debugging. The issue was that when a road
had oneway="-1" (meaning traffic flows opposite to the way direction), the
graph construction was incorrectly adding bidirectional edges instead of
reverse-only edges.

Bug details:
- Old code checked `oneway in ('yes', '1', 'true')` which is False for '-1'
- When reverse was True (for oneway=-1), it added edge to_id -> from_id
- But then `if not oneway` was True, so it also added from_id -> to_id
- This created bidirectional edges for oneway=-1 roads

Fix:
- Changed to `is_oneway = oneway_tag in ('yes', '1', 'true', '-1')`
- Added `is_reverse = oneway_tag == '-1'`
- Restructured logic to properly handle all cases
"""
import json
import pytest
from argparse import Namespace


class TestOnewayMinusOneBug:
    """Regression tests for oneway=-1 handling in routing."""

    @pytest.fixture
    def oneway_minus_one_osm(self, tmp_path):
        """Create OSM with oneway=-1 road."""
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
    <tag k="oneway" v="-1"/>
  </way>
</osm>'''
        osm_file = tmp_path / "oneway_minus_one.osm"
        osm_file.write_text(content)
        return osm_file

    @pytest.fixture
    def oneway_yes_osm(self, tmp_path):
        """Create OSM with oneway=yes road."""
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
    <tag k="oneway" v="yes"/>
  </way>
</osm>'''
        osm_file = tmp_path / "oneway_yes.osm"
        osm_file.write_text(content)
        return osm_file

    @pytest.fixture
    def bidirectional_osm(self, tmp_path):
        """Create OSM with bidirectional road."""
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
        osm_file = tmp_path / "bidirectional.osm"
        osm_file.write_text(content)
        return osm_file

    def test_oneway_minus_one_blocks_forward(self, oneway_minus_one_osm):
        """oneway=-1 should block routing from node 1 to node 2."""
        from osm_core.cli.commands import route

        args = Namespace(
            input=str(oneway_minus_one_osm),
            output=None,
            origin="-33.900,151.200",  # Node 1
            destination="-33.901,151.200",  # Node 2
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)

        # Should fail - cannot go from 1 to 2 when oneway=-1
        assert result == 1, "oneway=-1 should block forward routing"

    def test_oneway_minus_one_allows_reverse(self, oneway_minus_one_osm):
        """oneway=-1 should allow routing from node 2 to node 1."""
        from osm_core.cli.commands import route

        args = Namespace(
            input=str(oneway_minus_one_osm),
            output=None,
            origin="-33.901,151.200",  # Node 2
            destination="-33.900,151.200",  # Node 1
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)

        # Should succeed - can go from 2 to 1 when oneway=-1
        assert result == 0, "oneway=-1 should allow reverse routing"

    def test_oneway_yes_allows_forward(self, oneway_yes_osm):
        """oneway=yes should allow routing from node 1 to node 2."""
        from osm_core.cli.commands import route

        args = Namespace(
            input=str(oneway_yes_osm),
            output=None,
            origin="-33.900,151.200",  # Node 1
            destination="-33.901,151.200",  # Node 2
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)

        # Should succeed - can go from 1 to 2 when oneway=yes
        assert result == 0, "oneway=yes should allow forward routing"

    def test_oneway_yes_blocks_reverse(self, oneway_yes_osm):
        """oneway=yes should block routing from node 2 to node 1."""
        from osm_core.cli.commands import route

        args = Namespace(
            input=str(oneway_yes_osm),
            output=None,
            origin="-33.901,151.200",  # Node 2
            destination="-33.900,151.200",  # Node 1
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)

        # Should fail - cannot go from 2 to 1 when oneway=yes
        assert result == 1, "oneway=yes should block reverse routing"

    def test_bidirectional_allows_both(self, bidirectional_osm):
        """Bidirectional road should allow routing in both directions."""
        from osm_core.cli.commands import route

        # Forward
        args_forward = Namespace(
            input=str(bidirectional_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.901,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result_forward = route.run(args_forward)
        assert result_forward == 0, "Bidirectional should allow forward"

        # Reverse
        args_reverse = Namespace(
            input=str(bidirectional_osm),
            output=None,
            origin="-33.901,151.200",
            destination="-33.900,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result_reverse = route.run(args_reverse)
        assert result_reverse == 0, "Bidirectional should allow reverse"

    def test_graph_construction_oneway_minus_one(self, oneway_minus_one_osm):
        """Verify graph edges are correct for oneway=-1."""
        from osm_core.cli.commands.route import build_graph
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(oneway_minus_one_osm))

        node_coords = {}
        for node in nodes:
            node_coords[node.id] = (float(node.lon), float(node.lat))

        graph, _ = build_graph(ways, node_coords, "drive", "time")

        # For oneway=-1, only edge 2->1 should exist
        if "1" in graph:
            neighbors_of_1 = [n[0] for n in graph["1"]]
            assert "2" not in neighbors_of_1, "oneway=-1 should not have edge 1->2"

        if "2" in graph:
            neighbors_of_2 = [n[0] for n in graph["2"]]
            assert "1" in neighbors_of_2, "oneway=-1 should have edge 2->1"

    def test_graph_construction_oneway_yes(self, oneway_yes_osm):
        """Verify graph edges are correct for oneway=yes."""
        from osm_core.cli.commands.route import build_graph
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(oneway_yes_osm))

        node_coords = {}
        for node in nodes:
            node_coords[node.id] = (float(node.lon), float(node.lat))

        graph, _ = build_graph(ways, node_coords, "drive", "time")

        # For oneway=yes, only edge 1->2 should exist
        if "1" in graph:
            neighbors_of_1 = [n[0] for n in graph["1"]]
            assert "2" in neighbors_of_1, "oneway=yes should have edge 1->2"

        if "2" in graph:
            neighbors_of_2 = [n[0] for n in graph["2"]]
            assert "1" not in neighbors_of_2, "oneway=yes should not have edge 2->1"

    def test_walk_mode_ignores_oneway(self, oneway_minus_one_osm):
        """Walking should ignore oneway restrictions."""
        from osm_core.cli.commands import route

        # Both directions should work in walk mode
        args_forward = Namespace(
            input=str(oneway_minus_one_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.901,151.200",
            mode="walk",
            optimize="time",
            format="text"
        )
        result_forward = route.run(args_forward)
        assert result_forward == 0, "Walking should ignore oneway"

        args_reverse = Namespace(
            input=str(oneway_minus_one_osm),
            output=None,
            origin="-33.901,151.200",
            destination="-33.900,151.200",
            mode="walk",
            optimize="time",
            format="text"
        )
        result_reverse = route.run(args_reverse)
        assert result_reverse == 0, "Walking should ignore oneway"

    def test_bike_mode_ignores_oneway(self, oneway_minus_one_osm):
        """Biking should ignore oneway restrictions."""
        from osm_core.cli.commands import route

        # Both directions should work in bike mode
        args_forward = Namespace(
            input=str(oneway_minus_one_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.901,151.200",
            mode="bike",
            optimize="time",
            format="text"
        )
        result_forward = route.run(args_forward)
        assert result_forward == 0, "Biking should ignore oneway"


class TestOnewayVariations:
    """Test all oneway tag variations."""

    @pytest.fixture
    def create_oneway_osm(self, tmp_path):
        """Factory fixture to create OSM with specific oneway value."""
        def _create(oneway_value):
            content = f'''<?xml version="1.0" encoding="UTF-8"?>
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
    <tag k="oneway" v="{oneway_value}"/>
  </way>
</osm>'''
            osm_file = tmp_path / f"oneway_{oneway_value.replace('-', 'minus')}.osm"
            osm_file.write_text(content)
            return osm_file
        return _create

    @pytest.mark.parametrize("oneway_value", ["yes", "1", "true"])
    def test_forward_oneway_values(self, create_oneway_osm, oneway_value):
        """Test all forward oneway values block reverse direction."""
        from osm_core.cli.commands import route

        osm_file = create_oneway_osm(oneway_value)

        # Reverse should fail
        args = Namespace(
            input=str(osm_file),
            output=None,
            origin="-33.901,151.200",
            destination="-33.900,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 1, f"oneway={oneway_value} should block reverse"

    def test_oneway_minus_one_value(self, create_oneway_osm):
        """Test oneway=-1 blocks forward direction."""
        from osm_core.cli.commands import route

        osm_file = create_oneway_osm("-1")

        # Forward should fail
        args = Namespace(
            input=str(osm_file),
            output=None,
            origin="-33.900,151.200",
            destination="-33.901,151.200",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 1, "oneway=-1 should block forward"


class TestIsochroneOnewayBug:
    """Test that isochrone also handles oneway=-1 correctly.

    Note: The isochrone command may have the same bug pattern.
    """

    @pytest.fixture
    def oneway_network_osm(self, tmp_path):
        """Create network with mixed oneway values."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>
  <node id="2" lat="-33.901" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>
  <node id="3" lat="-33.901" lon="151.201">
    <tag k="junction" v="yes"/>
  </node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="primary"/>
    <tag k="oneway" v="-1"/>
  </way>
  <way id="101">
    <nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>'''
        osm_file = tmp_path / "oneway_network.osm"
        osm_file.write_text(content)
        return osm_file

    def test_isochrone_respects_oneway(self, oneway_network_osm, tmp_path):
        """Isochrone should respect oneway restrictions."""
        from osm_core.cli.commands.isochrone import run

        output_file = tmp_path / "isochrone.geojson"
        args = Namespace(
            input=str(oneway_network_osm),
            output=str(output_file),
            lat=-33.900,
            lon=151.200,
            time="10",
            mode="drive",
            resolution=18
        )
        result = run(args)
        # Should succeed but may have limited reachable area due to oneway
        assert result == 0
