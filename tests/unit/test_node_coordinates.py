"""Tests for node coordinate handling - ensures all nodes (tagged and untagged) are available.

This test module was added to prevent regression of a bug where routing commands
only used tagged nodes for building the road network, missing 63% of road geometry
nodes that have no tags. The fix uses parser.node_coordinates which caches ALL
nodes during parsing.
"""

import pytest
import tempfile
import os
from pathlib import Path

from osm_core.parsing.mmap_parser import UltraFastOSMParser


class TestNodeCoordinateCache:
    """Tests for parser's node_coordinates cache."""

    def test_cache_includes_untagged_nodes(self):
        """Verify that node_coordinates includes nodes without tags."""
        osm_content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.0" lon="-0.1"/>
  <node id="2" lat="51.1" lon="-0.2"/>
  <node id="3" lat="51.2" lon="-0.3">
    <tag k="name" v="Tagged Node"/>
  </node>
</osm>'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False) as f:
            f.write(osm_content)
            temp_path = f.name

        try:
            parser = UltraFastOSMParser()
            nodes, ways = parser.parse_file_ultra_fast(temp_path)

            # Only tagged nodes are returned
            assert len(nodes) == 1
            assert nodes[0].id == "3"

            # But ALL nodes are in the coordinate cache
            assert len(parser.node_coordinates) == 3
            assert "1" in parser.node_coordinates
            assert "2" in parser.node_coordinates
            assert "3" in parser.node_coordinates

            # Verify coordinates are correct
            assert parser.node_coordinates["1"] == (51.0, -0.1)
            assert parser.node_coordinates["2"] == (51.1, -0.2)
            assert parser.node_coordinates["3"] == (51.2, -0.3)

        finally:
            os.unlink(temp_path)

    def test_cache_available_for_way_geometry(self):
        """Verify way node refs can be resolved using coordinate cache."""
        osm_content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="100" lat="51.0" lon="-0.1"/>
  <node id="101" lat="51.1" lon="-0.1"/>
  <node id="102" lat="51.2" lon="-0.1"/>
  <node id="103" lat="51.3" lon="-0.1"/>
  <way id="1">
    <nd ref="100"/>
    <nd ref="101"/>
    <nd ref="102"/>
    <nd ref="103"/>
    <tag k="highway" v="residential"/>
  </way>
</osm>'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False) as f:
            f.write(osm_content)
            temp_path = f.name

        try:
            parser = UltraFastOSMParser()
            nodes, ways = parser.parse_file_ultra_fast(temp_path)

            # No tagged nodes
            assert len(nodes) == 0

            # One way
            assert len(ways) == 1
            way = ways[0]
            assert len(way.node_refs) == 4

            # All node refs should be resolvable from cache
            for ref in way.node_refs:
                assert ref in parser.node_coordinates, f"Node {ref} not in coordinate cache"

        finally:
            os.unlink(temp_path)

    def test_cache_with_mixed_node_types(self):
        """Test with realistic mix of tagged POIs and untagged geometry nodes."""
        osm_content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <!-- Untagged road geometry nodes -->
  <node id="1" lat="51.00" lon="-0.10"/>
  <node id="2" lat="51.01" lon="-0.10"/>
  <node id="3" lat="51.02" lon="-0.10"/>
  <node id="4" lat="51.03" lon="-0.10"/>
  <node id="5" lat="51.04" lon="-0.10"/>

  <!-- Tagged POI nodes -->
  <node id="100" lat="51.00" lon="-0.11">
    <tag k="amenity" v="restaurant"/>
    <tag k="name" v="Test Restaurant"/>
  </node>
  <node id="101" lat="51.02" lon="-0.11">
    <tag k="shop" v="supermarket"/>
  </node>

  <!-- Road using untagged nodes -->
  <way id="1">
    <nd ref="1"/>
    <nd ref="2"/>
    <nd ref="3"/>
    <nd ref="4"/>
    <nd ref="5"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="Main Street"/>
  </way>
</osm>'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False) as f:
            f.write(osm_content)
            temp_path = f.name

        try:
            parser = UltraFastOSMParser()
            nodes, ways = parser.parse_file_ultra_fast(temp_path)

            # Only 2 tagged nodes returned
            assert len(nodes) == 2

            # All 7 nodes in cache (5 geometry + 2 POIs)
            assert len(parser.node_coordinates) == 7

            # Way should have 5 node refs, all resolvable
            assert len(ways) == 1
            assert len(ways[0].node_refs) == 5
            for ref in ways[0].node_refs:
                assert ref in parser.node_coordinates

        finally:
            os.unlink(temp_path)


class TestNetworkNodeCoordinates:
    """Tests for network command using all node coordinates."""

    @pytest.fixture
    def sample_osm_file(self):
        """Create a sample OSM file with connected roads."""
        osm_content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <!-- Intersection node (shared by two roads) -->
  <node id="100" lat="51.5" lon="-0.1"/>

  <!-- Road 1 geometry nodes -->
  <node id="1" lat="51.4" lon="-0.1"/>
  <node id="2" lat="51.45" lon="-0.1"/>

  <!-- Road 2 geometry nodes -->
  <node id="3" lat="51.5" lon="-0.05"/>
  <node id="4" lat="51.5" lon="0.0"/>

  <!-- Road 1: South to intersection -->
  <way id="1">
    <nd ref="1"/>
    <nd ref="2"/>
    <nd ref="100"/>
    <tag k="highway" v="residential"/>
  </way>

  <!-- Road 2: Intersection to east -->
  <way id="2">
    <nd ref="100"/>
    <nd ref="3"/>
    <nd ref="4"/>
    <tag k="highway" v="residential"/>
  </way>
</osm>'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False) as f:
            f.write(osm_content)
            temp_path = f.name

        yield temp_path
        os.unlink(temp_path)

    def test_network_uses_all_nodes(self, sample_osm_file):
        """Verify network command builds graph with all nodes."""
        from argparse import Namespace
        from osm_core.cli.commands import network
        import json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name

        try:
            args = Namespace(
                input=sample_osm_file,
                output=output_path,
                format='json',
                mode='drive',
                directed=False,
                include_speeds=False,
                stats=False
            )

            result = network.run(args)
            assert result == 0

            with open(output_path) as f:
                data = json.load(f)

            # Should have all 5 nodes (not just tagged ones - there are none!)
            assert len(data['nodes']) == 5

            # Should have 4 edges (2 roads with 2 segments each)
            assert len(data['edges']) == 4

        finally:
            os.unlink(output_path)

    def test_network_connectivity_at_intersection(self, sample_osm_file):
        """Verify roads are connected at shared intersection node."""
        from argparse import Namespace
        from osm_core.cli.commands import connectivity
        import sys
        from io import StringIO

        args = Namespace(
            input=sample_osm_file,
            output=None,
            mode='drive',
            format='text',
            show_components=False
        )

        # Capture output
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()

        try:
            result = connectivity.run(args)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        assert result == 0
        # Should have only 1 connected component (roads meet at intersection)
        assert "Connected components: 1" in output


class TestRouteNodeCoordinates:
    """Tests for routing using all node coordinates."""

    @pytest.fixture
    def connected_roads_file(self):
        """Create OSM file with connected road network."""
        osm_content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <!-- Grid of nodes forming connected roads -->
  <node id="1" lat="51.50" lon="-0.10"/>
  <node id="2" lat="51.51" lon="-0.10"/>
  <node id="3" lat="51.52" lon="-0.10"/>
  <node id="4" lat="51.50" lon="-0.09"/>
  <node id="5" lat="51.51" lon="-0.09"/>
  <node id="6" lat="51.52" lon="-0.09"/>

  <!-- Vertical road 1 -->
  <way id="1">
    <nd ref="1"/>
    <nd ref="2"/>
    <nd ref="3"/>
    <tag k="highway" v="residential"/>
  </way>

  <!-- Vertical road 2 -->
  <way id="2">
    <nd ref="4"/>
    <nd ref="5"/>
    <nd ref="6"/>
    <tag k="highway" v="residential"/>
  </way>

  <!-- Horizontal connector -->
  <way id="3">
    <nd ref="2"/>
    <nd ref="5"/>
    <tag k="highway" v="residential"/>
  </way>
</osm>'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False) as f:
            f.write(osm_content)
            temp_path = f.name

        yield temp_path
        os.unlink(temp_path)

    def test_route_finds_path_via_untagged_nodes(self, connected_roads_file):
        """Verify routing works through untagged geometry nodes."""
        from argparse import Namespace
        from osm_core.cli.commands import route
        import json
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            output_path = f.name

        try:
            # Route from node 1 to node 6 (opposite corners, requires path through network)
            args = Namespace(
                input=connected_roads_file,
                output=output_path,
                origin='51.50,-0.10',  # Near node 1
                destination='51.52,-0.09',  # Near node 6
                mode='drive',
                optimize='distance',
                format='geojson'
            )

            result = route.run(args)
            assert result == 0

            with open(output_path) as f:
                data = json.load(f)

            # Should find a route (GeoJSON includes route + origin/dest markers)
            assert len(data['features']) >= 1

            # Find the LineString feature (the route)
            route_feature = None
            for feat in data['features']:
                if feat['geometry']['type'] == 'LineString':
                    route_feature = feat
                    break

            assert route_feature is not None, "No route LineString found"

            # Route should have multiple nodes (path through network)
            coords = route_feature['geometry']['coordinates']
            assert len(coords) >= 4  # At least 4 nodes in path

            # Distance should be reasonable (not 0, not infinite)
            distance = route_feature['properties'].get('distance_m', 0)
            assert distance > 0
            assert distance < 10000  # Less than 10km for this small network

        finally:
            os.unlink(output_path)


class TestParserCoordinateCacheIntegrity:
    """Tests for coordinate cache data integrity."""

    def test_cache_not_cleared_between_calls(self):
        """Verify cache persists after parsing."""
        osm_content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.0" lon="-0.1"/>
  <node id="2" lat="51.1" lon="-0.2"/>
</osm>'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False) as f:
            f.write(osm_content)
            temp_path = f.name

        try:
            parser = UltraFastOSMParser()
            nodes, ways = parser.parse_file_ultra_fast(temp_path)

            # Cache should be populated
            assert len(parser.node_coordinates) == 2

            # Access cache multiple times
            coord1 = parser.node_coordinates["1"]
            coord2 = parser.node_coordinates["2"]

            # Should still be there
            assert parser.node_coordinates["1"] == coord1
            assert parser.node_coordinates["2"] == coord2

        finally:
            os.unlink(temp_path)

    def test_cache_cleared_on_reset(self):
        """Verify reset_stats clears the cache."""
        osm_content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.0" lon="-0.1"/>
</osm>'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False) as f:
            f.write(osm_content)
            temp_path = f.name

        try:
            parser = UltraFastOSMParser()
            nodes, ways = parser.parse_file_ultra_fast(temp_path)

            assert len(parser.node_coordinates) == 1

            parser.reset_stats()

            assert len(parser.node_coordinates) == 0

        finally:
            os.unlink(temp_path)

    def test_coordinate_precision(self):
        """Verify coordinates maintain precision."""
        osm_content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5074456" lon="-0.1277583"/>
</osm>'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False) as f:
            f.write(osm_content)
            temp_path = f.name

        try:
            parser = UltraFastOSMParser()
            parser.parse_file_ultra_fast(temp_path)

            lat, lon = parser.node_coordinates["1"]

            # Should maintain at least 6 decimal places
            assert abs(lat - 51.5074456) < 0.0000001
            assert abs(lon - (-0.1277583)) < 0.0000001

        finally:
            os.unlink(temp_path)
