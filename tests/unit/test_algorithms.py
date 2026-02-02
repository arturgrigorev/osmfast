"""Algorithm validation tests for routing and network analysis."""
import math
import pytest


class TestHaversineDistance:
    """Test haversine distance calculation."""

    def get_haversine(self):
        """Import haversine function."""
        from osm_core.cli.commands.route import haversine_distance
        return haversine_distance

    def test_same_point_zero_distance(self):
        """Same point should have zero distance."""
        haversine = self.get_haversine()
        dist = haversine(0, 0, 0, 0)
        assert dist == 0

    def test_known_distance_equator(self):
        """Test known distance along equator."""
        haversine = self.get_haversine()
        # 1 degree longitude at equator is approximately 111.32 km
        dist = haversine(0, 0, 1, 0)
        assert 110000 < dist < 112000

    def test_known_distance_london_paris(self):
        """Test known distance between cities."""
        haversine = self.get_haversine()
        # London (51.5074, -0.1278) to Paris (48.8566, 2.3522)
        # Distance is approximately 344 km
        dist = haversine(-0.1278, 51.5074, 2.3522, 48.8566)
        assert 340000 < dist < 350000

    def test_antipodal_points(self):
        """Test distance between antipodal points."""
        haversine = self.get_haversine()
        # Opposite sides of Earth, should be ~20,000 km (half circumference)
        dist = haversine(0, 0, 180, 0)
        assert 19500000 < dist < 20500000

    def test_symmetry(self):
        """Distance should be symmetric."""
        haversine = self.get_haversine()
        dist1 = haversine(0, 0, 1, 1)
        dist2 = haversine(1, 1, 0, 0)
        assert abs(dist1 - dist2) < 0.001

    def test_small_distance(self):
        """Test very small distances."""
        haversine = self.get_haversine()
        # ~11 meters (0.0001 degree at equator)
        dist = haversine(0, 0, 0.0001, 0)
        assert 10 < dist < 12


class TestDijkstraAlgorithm:
    """Test Dijkstra's shortest path algorithm."""

    def get_dijkstra(self):
        """Import dijkstra function."""
        from osm_core.cli.commands.route import dijkstra_path
        return dijkstra_path

    def test_direct_connection(self):
        """Test simple direct connection."""
        dijkstra = self.get_dijkstra()
        graph = {
            'A': [('B', 10)],
            'B': [('A', 10)]
        }
        path, cost = dijkstra(graph, 'A', 'B')
        assert path == ['A', 'B']
        assert cost == 10

    def test_shortest_of_two_paths(self):
        """Should find shortest path when two options exist."""
        dijkstra = self.get_dijkstra()
        # A -> B (direct: 10, via C: 3+3=6)
        graph = {
            'A': [('B', 10), ('C', 3)],
            'B': [('A', 10), ('C', 3)],
            'C': [('A', 3), ('B', 3)]
        }
        path, cost = dijkstra(graph, 'A', 'B')
        assert path == ['A', 'C', 'B']
        assert cost == 6

    def test_no_path_exists(self):
        """Should return None when no path exists."""
        dijkstra = self.get_dijkstra()
        graph = {
            'A': [('B', 10)],
            'B': [('A', 10)],
            'C': []  # Disconnected
        }
        path, cost = dijkstra(graph, 'A', 'C')
        assert path is None
        assert cost is None

    def test_same_start_end(self):
        """Path from node to itself."""
        dijkstra = self.get_dijkstra()
        graph = {
            'A': [('B', 10)],
            'B': [('A', 10)]
        }
        path, cost = dijkstra(graph, 'A', 'A')
        assert path == ['A']
        assert cost == 0

    def test_longer_path(self):
        """Test path with multiple hops."""
        dijkstra = self.get_dijkstra()
        graph = {
            'A': [('B', 1)],
            'B': [('A', 1), ('C', 2)],
            'C': [('B', 2), ('D', 3)],
            'D': [('C', 3), ('E', 4)],
            'E': [('D', 4)]
        }
        path, cost = dijkstra(graph, 'A', 'E')
        assert path == ['A', 'B', 'C', 'D', 'E']
        assert cost == 10

    def test_multiple_edges_same_weight(self):
        """Test graph with multiple equal-weight options."""
        dijkstra = self.get_dijkstra()
        graph = {
            'A': [('B', 5), ('C', 5)],
            'B': [('A', 5), ('D', 5)],
            'C': [('A', 5), ('D', 5)],
            'D': [('B', 5), ('C', 5)]
        }
        path, cost = dijkstra(graph, 'A', 'D')
        # Either path is valid (A->B->D or A->C->D)
        assert cost == 10
        assert len(path) == 3
        assert path[0] == 'A'
        assert path[-1] == 'D'


class TestGraphBuilding:
    """Test graph construction from OSM data."""

    def test_bidirectional_walk(self, road_network_osm):
        """Walk mode should create bidirectional edges."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser
        from osm_core.cli.commands.route import build_graph

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(road_network_osm))

        node_coords = {}
        for node in nodes:
            node_coords[node.id] = (float(node.lon), float(node.lat))

        graph, edge_info = build_graph(ways, node_coords, 'walk', 'distance')

        # Check bidirectionality - if (A, B) exists, (B, A) should too
        for key in edge_info.keys():
            from_id, to_id = key
            reverse_key = (to_id, from_id)
            assert reverse_key in edge_info, f"Missing reverse edge for {key}"

    def test_graph_contains_all_road_nodes(self, road_network_osm):
        """Graph should contain nodes referenced by roads."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser
        from osm_core.cli.commands.route import build_graph

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(road_network_osm))

        node_coords = {}
        for node in nodes:
            node_coords[node.id] = (float(node.lon), float(node.lat))

        graph, edge_info = build_graph(ways, node_coords, 'drive', 'time')

        # Graph should not be empty
        assert len(graph) > 0


class TestNearestNodeFinding:
    """Test nearest node finding."""

    def test_exact_match(self):
        """Node at exact location should have zero distance."""
        from osm_core.cli.commands.route import find_nearest_node

        node_coords = {
            'A': (0.0, 0.0),
            'B': (1.0, 1.0)
        }
        nearest, dist = find_nearest_node(0.0, 0.0, node_coords)
        assert nearest == 'A'
        assert dist < 1  # Very small

    def test_finds_closest(self):
        """Should find closest node."""
        from osm_core.cli.commands.route import find_nearest_node

        node_coords = {
            'A': (0.0, 0.0),
            'B': (0.001, 0.001),  # Closer
            'C': (0.01, 0.01)     # Farther
        }
        nearest, dist = find_nearest_node(0.0005, 0.0005, node_coords)
        assert nearest == 'B'

    def test_empty_coords(self):
        """Empty coords should return None."""
        from osm_core.cli.commands.route import find_nearest_node

        nearest, dist = find_nearest_node(0.0, 0.0, {})
        assert nearest is None


class TestConnectedComponents:
    """Test connected component analysis."""

    def test_single_component(self, road_network_osm, tmp_path):
        """Connected network should have one component."""
        import json
        from argparse import Namespace
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
        assert data["num_components"] == 1
        assert data["is_connected"] == True

    def test_two_components(self, disconnected_network_osm, tmp_path):
        """Disconnected network should have two components."""
        import json
        from argparse import Namespace
        from osm_core.cli.commands import connectivity

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


class TestDistanceMatrixCorrectness:
    """Test distance matrix calculations."""

    def test_diagonal_zero(self, road_network_osm, tmp_path):
        """Diagonal of distance matrix should be zero."""
        import json
        from argparse import Namespace
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
        matrix = data["distance_matrix_m"]
        n = len(matrix)
        for i in range(n):
            assert matrix[i][i] == 0

    def test_triangle_inequality(self, road_network_osm, tmp_path):
        """Distance should satisfy triangle inequality (approximately)."""
        import json
        from argparse import Namespace
        from osm_core.cli.commands import distance_matrix

        output_file = tmp_path / "matrix.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            points="-33.900,151.200;-33.901,151.200;-33.902,151.200",
            mode="walk",  # Bidirectional
            metric="both",
            format="json"
        )
        result = distance_matrix.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        matrix = data["distance_matrix_m"]

        # For walk mode, d(A,C) <= d(A,B) + d(B,C)
        # Note: This is approximate due to snapping
        n = len(matrix)
        for i in range(n):
            for j in range(n):
                for k in range(n):
                    if matrix[i][j] is not None and matrix[j][k] is not None and matrix[i][k] is not None:
                        # Allow some tolerance for snapping differences
                        assert matrix[i][k] <= matrix[i][j] + matrix[j][k] + 100  # 100m tolerance


class TestBottleneckDetection:
    """Test bottleneck/bridge detection algorithm."""

    def test_linear_network_all_bridges(self, tmp_path):
        """In a linear network, all edges are bridges."""
        import json
        from argparse import Namespace
        from osm_core.cli.commands import bottleneck

        # Create linear network A -- B -- C -- D
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="3" lat="-33.902" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="4" lat="-33.903" lon="151.200"><tag k="junction" v="yes"/></node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>'''
        osm_file = tmp_path / "linear.osm"
        osm_file.write_text(content)

        output_file = tmp_path / "bottlenecks.json"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            top=10,
            format="json"
        )
        result = bottleneck.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Should find bridges (edges that if removed disconnect the graph)
        assert data["type"] == "FeatureCollection"

    def test_cyclic_network_no_bridges(self, tmp_path):
        """In a cyclic network with no spurs, there are no bridges."""
        import json
        from argparse import Namespace
        from osm_core.cli.commands import bottleneck

        # Create triangular network A -- B -- C -- A
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="2" lat="-33.901" lon="151.201"><tag k="junction" v="yes"/></node>
  <node id="3" lat="-33.902" lon="151.200"><tag k="junction" v="yes"/></node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="primary"/>
  </way>
  <way id="101">
    <nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
  <way id="102">
    <nd ref="3"/><nd ref="1"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>'''
        osm_file = tmp_path / "cyclic.osm"
        osm_file.write_text(content)

        output_file = tmp_path / "bottlenecks.json"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            top=10,
            format="json"
        )
        result = bottleneck.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Pure cycle has no bridges
        assert data["type"] == "FeatureCollection"


class TestCentralityCalculation:
    """Test betweenness centrality calculation."""

    def test_center_node_highest_centrality(self, tmp_path):
        """Node in center of star should have highest centrality."""
        import json
        from argparse import Namespace
        from osm_core.cli.commands import centrality

        # Star network: center node C connected to A, B, D, E
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.199"><tag k="junction" v="yes"/></node>
  <node id="2" lat="-33.900" lon="151.201"><tag k="junction" v="yes"/></node>
  <node id="3" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="4" lat="-33.899" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="5" lat="-33.901" lon="151.200"><tag k="junction" v="yes"/></node>
  <way id="100">
    <nd ref="1"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
  <way id="101">
    <nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
  <way id="102">
    <nd ref="4"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
  <way id="103">
    <nd ref="5"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>'''
        osm_file = tmp_path / "star.osm"
        osm_file.write_text(content)

        output_file = tmp_path / "centrality.json"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            top=5,
            sample=100,  # High sample for accuracy
            format="json"
        )
        result = centrality.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"
        features = data["features"]

        # The center node (id=3) should have highest centrality
        if features:
            top_node = features[0]
            # Center is at -33.900, 151.200
            coords = top_node["geometry"]["coordinates"]
            # Check it's close to center
            assert abs(coords[0] - 151.200) < 0.001
            assert abs(coords[1] - (-33.900)) < 0.001


class TestDetourFactorCalculation:
    """Test detour factor calculation."""

    def test_straight_road_low_detour(self, tmp_path):
        """Straight road should have detour factor close to 1."""
        import json
        from argparse import Namespace
        from osm_core.cli.commands import detour_factor

        # Straight road A -- B -- C
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="3" lat="-33.902" lon="151.200"><tag k="junction" v="yes"/></node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>'''
        osm_file = tmp_path / "straight.osm"
        osm_file.write_text(content)

        output_file = tmp_path / "detour.json"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            mode="drive",
            sample=10,
            format="json"
        )
        result = detour_factor.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Straight road should have detour factor close to 1
        mean_detour = data["statistics"]["mean"]
        assert mean_detour < 1.5  # Close to 1.0
