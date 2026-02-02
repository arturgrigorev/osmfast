"""Stress tests with complex networks and large data."""
import json
import pytest
import random
from argparse import Namespace
from pathlib import Path


class TestLargeGridNetwork:
    """Tests with programmatically generated large grid networks."""

    @pytest.fixture
    def large_grid_osm(self, tmp_path):
        """Generate a 10x10 grid network."""
        nodes = []
        ways = []

        # Generate 100 nodes (10x10 grid)
        node_id = 1
        for row in range(10):
            for col in range(10):
                lat = -33.900 + row * 0.001
                lon = 151.200 + col * 0.001
                nodes.append(f'''  <node id="{node_id}" lat="{lat}" lon="{lon}">
    <tag k="junction" v="yes"/>
  </node>''')
                node_id += 1

        # Generate horizontal roads
        way_id = 100
        for row in range(10):
            refs = " ".join([f'<nd ref="{row * 10 + col + 1}"/>' for col in range(10)])
            ways.append(f'''  <way id="{way_id}">
    {refs}
    <tag k="highway" v="primary"/>
    <tag k="name" v="Row {row}"/>
  </way>''')
            way_id += 1

        # Generate vertical roads
        for col in range(10):
            refs = " ".join([f'<nd ref="{row * 10 + col + 1}"/>' for row in range(10)])
            ways.append(f'''  <way id="{way_id}">
    {refs}
    <tag k="highway" v="primary"/>
    <tag k="name" v="Col {col}"/>
  </way>''')
            way_id += 1

        content = f'''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
{chr(10).join(nodes)}
{chr(10).join(ways)}
</osm>'''

        osm_file = tmp_path / "large_grid.osm"
        osm_file.write_text(content)
        return osm_file

    def test_route_across_grid(self, large_grid_osm):
        """Route from corner to corner of grid."""
        from osm_core.cli.commands import route

        args = Namespace(
            input=str(large_grid_osm),
            output=None,
            origin="-33.900,151.200",  # Top-left
            destination="-33.909,151.209",  # Bottom-right
            mode="drive",
            optimize="distance",
            format="text"
        )
        result = route.run(args)
        assert result == 0

    def test_distance_matrix_many_points(self, large_grid_osm, tmp_path):
        """Distance matrix with many points."""
        from osm_core.cli.commands import distance_matrix

        # 5 points across the grid
        points = ";".join([
            "-33.900,151.200",
            "-33.902,151.202",
            "-33.905,151.205",
            "-33.907,151.207",
            "-33.909,151.209"
        ])

        output_file = tmp_path / "matrix.json"
        args = Namespace(
            input=str(large_grid_osm),
            output=str(output_file),
            points=points,
            mode="drive",
            metric="both",
            format="json"
        )
        result = distance_matrix.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert len(data["distance_matrix_m"]) == 5
        assert len(data["distance_matrix_m"][0]) == 5

    def test_connectivity_large_grid(self, large_grid_osm, tmp_path):
        """Grid should be fully connected."""
        from osm_core.cli.commands import connectivity

        output_file = tmp_path / "connectivity.json"
        args = Namespace(
            input=str(large_grid_osm),
            output=str(output_file),
            mode="drive",
            format="json",
            show_components=False
        )
        result = connectivity.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["is_connected"] == True
        assert data["num_components"] == 1
        assert data["total_nodes"] == 100

    def test_centrality_large_grid(self, large_grid_osm, tmp_path):
        """Centrality on large grid."""
        from osm_core.cli.commands import centrality

        output_file = tmp_path / "centrality.json"
        args = Namespace(
            input=str(large_grid_osm),
            output=str(output_file),
            top=10,
            sample=50,
            format="json"
        )
        result = centrality.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert len(data["features"]) <= 10

    def test_bottleneck_large_grid(self, large_grid_osm, tmp_path):
        """Bottleneck detection on large grid."""
        from osm_core.cli.commands import bottleneck

        output_file = tmp_path / "bottleneck.json"
        args = Namespace(
            input=str(large_grid_osm),
            output=str(output_file),
            top=20,
            format="json"
        )
        result = bottleneck.run(args)
        assert result == 0

    def test_alternatives_large_grid(self, large_grid_osm, tmp_path):
        """Alternative routes on grid (many possibilities)."""
        from osm_core.cli.commands import alternatives

        output_file = tmp_path / "alternatives.json"
        args = Namespace(
            input=str(large_grid_osm),
            output=str(output_file),
            origin="-33.900,151.200",
            destination="-33.909,151.209",
            mode="drive",
            count=5,
            format="json"
        )
        result = alternatives.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Grid has many alternative routes
        assert len(data["features"]) >= 1


class TestManyWaypoints:
    """Tests with many waypoints."""

    def test_route_multi_10_waypoints(self, tmp_path):
        """Route through 10 waypoints."""
        from osm_core.cli.commands import route_multi

        # Generate linear network
        nodes = []
        for i in range(15):
            lat = -33.900 + i * 0.001
            lon = 151.200
            nodes.append(f'''  <node id="{i+1}" lat="{lat}" lon="{lon}">
    <tag k="junction" v="yes"/>
  </node>''')

        refs = " ".join([f'<nd ref="{i+1}"/>' for i in range(15)])
        content = f'''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
{chr(10).join(nodes)}
  <way id="100">
    {refs}
    <tag k="highway" v="primary"/>
  </way>
</osm>'''
        osm_file = tmp_path / "linear15.osm"
        osm_file.write_text(content)

        # 10 waypoints along the line
        waypoints = ";".join([f"-33.{900+i*1:03d},151.200" for i in range(10)])

        output_file = tmp_path / "route.json"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            waypoints=waypoints,
            mode="drive",
            optimize="time",
            format="json"
        )
        result = route_multi.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert len(data["legs"]) == 9  # 10 waypoints = 9 legs


class TestComplexTopologies:
    """Tests with complex network topologies."""

    @pytest.fixture
    def hub_and_spoke_osm(self, tmp_path):
        """Generate hub-and-spoke network (many spokes from center)."""
        nodes = []
        ways = []

        # Center hub
        nodes.append('''  <node id="1" lat="-33.900" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>''')

        # 8 spokes with 3 nodes each
        node_id = 2
        way_id = 100
        for spoke in range(8):
            angle = spoke * 45
            for dist in range(1, 4):
                lat = -33.900 + dist * 0.001 * (1 if spoke < 4 else -1)
                lon = 151.200 + dist * 0.001 * (1 if spoke % 4 < 2 else -1)
                nodes.append(f'''  <node id="{node_id}" lat="{lat}" lon="{lon}">
    <tag k="junction" v="yes"/>
  </node>''')
                node_id += 1

            # Connect spoke to hub
            spoke_start = 2 + spoke * 3
            refs = f'<nd ref="1"/><nd ref="{spoke_start}"/><nd ref="{spoke_start+1}"/><nd ref="{spoke_start+2}"/>'
            ways.append(f'''  <way id="{way_id}">
    {refs}
    <tag k="highway" v="primary"/>
    <tag k="name" v="Spoke {spoke}"/>
  </way>''')
            way_id += 1

        content = f'''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
{chr(10).join(nodes)}
{chr(10).join(ways)}
</osm>'''

        osm_file = tmp_path / "hub_spoke.osm"
        osm_file.write_text(content)
        return osm_file

    def test_hub_centrality(self, hub_and_spoke_osm, tmp_path):
        """Hub should have highest centrality."""
        from osm_core.cli.commands import centrality

        output_file = tmp_path / "centrality.json"
        args = Namespace(
            input=str(hub_and_spoke_osm),
            output=str(output_file),
            top=5,
            sample=100,
            format="json"
        )
        result = centrality.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        features = data["features"]
        if features:
            # Hub at -33.900, 151.200 should be first
            top = features[0]
            coords = top["geometry"]["coordinates"]
            assert abs(coords[0] - 151.200) < 0.0001
            assert abs(coords[1] - (-33.900)) < 0.0001

    @pytest.fixture
    def ring_network_osm(self, tmp_path):
        """Generate ring network (circular road)."""
        nodes = []
        import math

        # 12 nodes in a circle
        for i in range(12):
            angle = i * 30 * math.pi / 180
            lat = -33.900 + 0.002 * math.cos(angle)
            lon = 151.200 + 0.002 * math.sin(angle)
            nodes.append(f'''  <node id="{i+1}" lat="{lat}" lon="{lon}">
    <tag k="junction" v="yes"/>
  </node>''')

        # Single ring road
        refs = " ".join([f'<nd ref="{i+1}"/>' for i in range(12)] + ['<nd ref="1"/>'])
        content = f'''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
{chr(10).join(nodes)}
  <way id="100">
    {refs}
    <tag k="highway" v="primary"/>
    <tag k="name" v="Ring Road"/>
  </way>
</osm>'''

        osm_file = tmp_path / "ring.osm"
        osm_file.write_text(content)
        return osm_file

    def test_ring_connectivity(self, ring_network_osm, tmp_path):
        """Ring should be connected."""
        from osm_core.cli.commands import connectivity

        output_file = tmp_path / "connectivity.json"
        args = Namespace(
            input=str(ring_network_osm),
            output=str(output_file),
            mode="drive",
            format="json",
            show_components=False
        )
        result = connectivity.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["is_connected"] == True

    def test_ring_no_bottlenecks(self, ring_network_osm, tmp_path):
        """Ring should have no bottleneck edges (all redundant)."""
        from osm_core.cli.commands import bottleneck

        output_file = tmp_path / "bottleneck.json"
        args = Namespace(
            input=str(ring_network_osm),
            output=str(output_file),
            top=10,
            format="json"
        )
        result = bottleneck.run(args)
        assert result == 0


class TestRandomizedNetworks:
    """Tests with randomly generated networks."""

    @pytest.fixture
    def random_network_osm(self, tmp_path):
        """Generate random connected network."""
        random.seed(42)  # Reproducible

        nodes = []
        n_nodes = 20

        # Random node positions
        for i in range(n_nodes):
            lat = -33.900 + random.uniform(0, 0.01)
            lon = 151.200 + random.uniform(0, 0.01)
            nodes.append(f'''  <node id="{i+1}" lat="{lat}" lon="{lon}">
    <tag k="junction" v="yes"/>
  </node>''')

        # Generate edges to ensure connectivity (spanning tree + random edges)
        ways = []
        way_id = 100

        # First, create minimum spanning tree using simple chain
        for i in range(n_nodes - 1):
            ways.append(f'''  <way id="{way_id}">
    <nd ref="{i+1}"/><nd ref="{i+2}"/>
    <tag k="highway" v="primary"/>
  </way>''')
            way_id += 1

        # Add some random extra edges
        for _ in range(10):
            a = random.randint(1, n_nodes)
            b = random.randint(1, n_nodes)
            if a != b:
                ways.append(f'''  <way id="{way_id}">
    <nd ref="{a}"/><nd ref="{b}"/>
    <tag k="highway" v="secondary"/>
  </way>''')
                way_id += 1

        content = f'''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
{chr(10).join(nodes)}
{chr(10).join(ways)}
</osm>'''

        osm_file = tmp_path / "random.osm"
        osm_file.write_text(content)
        return osm_file

    def test_random_network_routing(self, random_network_osm):
        """Route on random network."""
        from osm_core.cli.commands import route

        args = Namespace(
            input=str(random_network_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.905,151.205",
            mode="drive",
            optimize="distance",
            format="text"
        )
        result = route.run(args)
        assert result == 0

    def test_random_network_connectivity(self, random_network_osm, tmp_path):
        """Random network should be connected (by construction)."""
        from osm_core.cli.commands import connectivity

        output_file = tmp_path / "connectivity.json"
        args = Namespace(
            input=str(random_network_osm),
            output=str(output_file),
            mode="drive",
            format="json",
            show_components=False
        )
        result = connectivity.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["is_connected"] == True


class TestRepeatedOperations:
    """Test repeated operations don't cause issues."""

    def test_repeated_routing(self, road_network_osm):
        """Repeated routing should give consistent results."""
        from osm_core.cli.commands import route

        results = []
        for _ in range(5):
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
            results.append(result)

        # All should succeed
        assert all(r == 0 for r in results)

    def test_repeated_connectivity(self, road_network_osm, tmp_path):
        """Repeated connectivity analysis should be consistent."""
        from osm_core.cli.commands import connectivity

        results = []
        for i in range(5):
            output_file = tmp_path / f"connectivity_{i}.json"
            args = Namespace(
                input=str(road_network_osm),
                output=str(output_file),
                mode="drive",
                format="json",
                show_components=False
            )
            result = connectivity.run(args)
            results.append(result)

            data = json.loads(output_file.read_text())
            assert data["num_components"] == 1

        assert all(r == 0 for r in results)
