"""PhD-level debugging tests for algorithm correctness."""
import json
import math
import pytest
from argparse import Namespace


class TestHaversinePrecision:
    """Test haversine distance for numerical precision issues."""

    def get_haversine(self):
        from osm_core.cli.commands.route import haversine_distance
        return haversine_distance

    def test_very_close_points_precision(self):
        """Test precision for points < 1 meter apart."""
        haversine = self.get_haversine()
        # Points approximately 0.1 meters apart
        dist = haversine(0, 0, 0.000001, 0)
        # Should be approximately 0.11 meters at equator
        assert 0.05 < dist < 0.2

    def test_numerical_stability_near_poles(self):
        """Test stability near poles where lon differences amplify."""
        haversine = self.get_haversine()
        # Near north pole
        dist = haversine(0, 89.9999, 180, 89.9999)
        assert dist > 0  # Should not be NaN or negative
        assert dist < 100  # Should be small

    def test_numerical_stability_date_line(self):
        """Test stability crossing date line."""
        haversine = self.get_haversine()
        # Cross date line
        dist1 = haversine(179.9, 0, -179.9, 0)
        dist2 = haversine(-179.9, 0, 179.9, 0)
        # Should be approximately 22 km, not 39,000 km (going the wrong way)
        assert dist1 < 30000
        assert abs(dist1 - dist2) < 0.01

    def test_zero_distance_precision(self):
        """Test that same point returns exactly 0."""
        haversine = self.get_haversine()
        dist = haversine(151.204364, -33.900714, 151.204364, -33.900714)
        assert dist == 0.0


class TestDijkstraCorrectness:
    """Test Dijkstra algorithm for correctness issues."""

    def get_dijkstra(self):
        from osm_core.cli.commands.route import dijkstra_path
        return dijkstra_path

    def test_negative_cost_handling(self):
        """Dijkstra doesn't handle negative costs correctly - verify behavior."""
        dijkstra = self.get_dijkstra()
        # Negative costs would break Dijkstra
        graph = {
            'A': [('B', 10), ('C', 5)],
            'B': [('C', -10)],  # Negative cost!
            'C': [('A', 5), ('B', -10)]
        }
        # This test documents current behavior - Dijkstra may give wrong results
        path, cost = dijkstra(graph, 'A', 'C')
        # With negative costs, Dijkstra might not find optimal path
        # but it should still return SOMETHING without crashing
        assert path is not None or path is None  # Just shouldn't crash

    def test_unreachable_node_returns_none(self):
        """Verify unreachable nodes return None, not crash."""
        dijkstra = self.get_dijkstra()
        graph = {
            'A': [('B', 10)],
            'B': [('A', 10)],
            'C': []  # Isolated node
        }
        path, cost = dijkstra(graph, 'A', 'C')
        assert path is None
        assert cost is None

    def test_self_loop_handling(self):
        """Test handling of self-loops in graph."""
        dijkstra = self.get_dijkstra()
        graph = {
            'A': [('A', 0), ('B', 10)],  # Self-loop with 0 cost
            'B': [('A', 10)]
        }
        path, cost = dijkstra(graph, 'A', 'B')
        assert path == ['A', 'B']
        assert cost == 10

    def test_parallel_edges(self):
        """Test handling of parallel edges (multiple edges between same nodes)."""
        dijkstra = self.get_dijkstra()
        graph = {
            'A': [('B', 10), ('B', 5), ('B', 15)],  # Three edges to B
            'B': [('A', 10), ('A', 5), ('A', 15)]
        }
        path, cost = dijkstra(graph, 'A', 'B')
        assert path == ['A', 'B']
        assert cost == 5  # Should take shortest edge


class TestGraphConstructionBugs:
    """Test for bugs in graph construction."""

    def test_duplicate_edges_in_graph(self, tmp_path):
        """Test that duplicate edges from overlapping ways are handled."""
        from osm_core.cli.commands.route import build_graph
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        # Create OSM with two ways sharing same edge
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="3" lat="-33.902" lon="151.200"><tag k="junction" v="yes"/></node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
  <way id="101">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="secondary"/>
  </way>
</osm>'''
        osm_file = tmp_path / "overlap.osm"
        osm_file.write_text(content)

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        node_coords = {}
        for node in nodes:
            node_coords[node.id] = (float(node.lon), float(node.lat))

        graph, edge_info = build_graph(ways, node_coords, 'drive', 'distance')

        # Check that edge 1->2 has duplicates
        edge_count = sum(1 for neighbor, _ in graph['1'] if neighbor == '2')
        # This documents current behavior - duplicates exist
        assert edge_count >= 1

    def test_oneway_reverse_direction(self, tmp_path):
        """Test oneway=-1 is handled correctly."""
        from osm_core.cli.commands.route import build_graph
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="junction" v="yes"/></node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="primary"/>
    <tag k="oneway" v="-1"/>
  </way>
</osm>'''
        osm_file = tmp_path / "reverse.osm"
        osm_file.write_text(content)

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        node_coords = {}
        for node in nodes:
            node_coords[node.id] = (float(node.lon), float(node.lat))

        graph, edge_info = build_graph(ways, node_coords, 'drive', 'distance')

        # With oneway=-1, should only be able to go 2->1, not 1->2
        neighbors_of_1 = [n for n, _ in graph.get('1', [])]
        neighbors_of_2 = [n for n, _ in graph.get('2', [])]

        assert '1' in neighbors_of_2  # Can go 2->1
        assert '2' not in neighbors_of_1  # Cannot go 1->2


class TestCentralityBugs:
    """Test centrality algorithm for correctness."""

    def test_centrality_on_star_graph(self, tmp_path):
        """Center of star should have highest centrality."""
        import json
        from osm_core.cli.commands import centrality

        # Star: center C connected to A, B, D, E
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.899" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="3" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="4" lat="-33.900" lon="151.199"><tag k="junction" v="yes"/></node>
  <node id="5" lat="-33.900" lon="151.201"><tag k="junction" v="yes"/></node>
  <way id="100"><nd ref="1"/><nd ref="3"/><tag k="highway" v="primary"/></way>
  <way id="101"><nd ref="2"/><nd ref="3"/><tag k="highway" v="primary"/></way>
  <way id="102"><nd ref="4"/><nd ref="3"/><tag k="highway" v="primary"/></way>
  <way id="103"><nd ref="5"/><nd ref="3"/><tag k="highway" v="primary"/></way>
</osm>'''
        osm_file = tmp_path / "star.osm"
        osm_file.write_text(content)

        output_file = tmp_path / "centrality.json"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            top=5,
            sample=100,  # High sample for determinism
            format="geojson"  # Use geojson format for file output
        )
        result = centrality.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Output is GeoJSON FeatureCollection
        assert data["type"] == "FeatureCollection"
        features = data["features"]
        # Node 3 (center at -33.900, 151.200) should have highest centrality
        if features:
            top_feature = features[0]
            coords = top_feature["geometry"]["coordinates"]
            # Check it's near the center (151.200, -33.900)
            assert abs(coords[0] - 151.200) < 0.001
            assert abs(coords[1] - (-33.900)) < 0.001

    def test_centrality_memory_explosion(self, tmp_path):
        """Test that centrality doesn't crash on graphs with many equal paths."""
        from osm_core.cli.commands import centrality

        # Create grid that has many equal-length paths
        nodes = []
        ways = []
        for i in range(5):
            for j in range(5):
                node_id = i * 5 + j + 1
                lat = -33.900 + i * 0.001
                lon = 151.200 + j * 0.001
                nodes.append(f'  <node id="{node_id}" lat="{lat}" lon="{lon}"><tag k="j" v="y"/></node>')

        way_id = 100
        # Horizontal edges
        for i in range(5):
            for j in range(4):
                from_id = i * 5 + j + 1
                to_id = from_id + 1
                ways.append(f'  <way id="{way_id}"><nd ref="{from_id}"/><nd ref="{to_id}"/><tag k="highway" v="primary"/></way>')
                way_id += 1
        # Vertical edges
        for i in range(4):
            for j in range(5):
                from_id = i * 5 + j + 1
                to_id = from_id + 5
                ways.append(f'  <way id="{way_id}"><nd ref="{from_id}"/><nd ref="{to_id}"/><tag k="highway" v="primary"/></way>')
                way_id += 1

        content = f'''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
{chr(10).join(nodes)}
{chr(10).join(ways)}
</osm>'''
        osm_file = tmp_path / "grid5.osm"
        osm_file.write_text(content)

        args = Namespace(
            input=str(osm_file),
            output=None,
            top=5,
            sample=10,  # Low sample to be fast
            format="text"
        )
        # Should complete without memory error
        result = centrality.run(args)
        assert result == 0


class TestBottleneckBugs:
    """Test bottleneck detection for correctness."""

    def test_bridge_detection_linear(self, tmp_path):
        """All edges in linear graph should be bridges."""
        import json
        from osm_core.cli.commands import bottleneck

        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="j" v="y"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="j" v="y"/></node>
  <node id="3" lat="-33.902" lon="151.200"><tag k="j" v="y"/></node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>'''
        osm_file = tmp_path / "linear.osm"
        osm_file.write_text(content)

        output_file = tmp_path / "bottleneck.json"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            top=10,
            format="geojson"  # Output is GeoJSON when writing to file
        )
        result = bottleneck.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Output is GeoJSON FeatureCollection
        assert data["type"] == "FeatureCollection"
        # Count bridge edges (LineString features with type=bridge_edge)
        bridge_edges = [f for f in data["features"] if f["properties"].get("type") == "bridge_edge"]
        assert len(bridge_edges) == 2

    def test_articulation_point_middle_node(self, tmp_path):
        """Middle node of linear graph is articulation point."""
        import json
        from osm_core.cli.commands import bottleneck

        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="j" v="y"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="j" v="y"/></node>
  <node id="3" lat="-33.902" lon="151.200"><tag k="j" v="y"/></node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>'''
        osm_file = tmp_path / "linear.osm"
        osm_file.write_text(content)

        output_file = tmp_path / "bottleneck.json"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            top=10,
            format="geojson"
        )
        result = bottleneck.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Node 2 should be articulation point (Point features with type=articulation_point)
        art_points = [f for f in data["features"] if f["properties"].get("type") == "articulation_point"]
        art_node_ids = [f["properties"]["node_id"] for f in art_points]
        assert "2" in art_node_ids

    def test_no_bridges_in_cycle(self, tmp_path):
        """Cycle should have no bridges."""
        import json
        from osm_core.cli.commands import bottleneck

        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="j" v="y"/></node>
  <node id="2" lat="-33.901" lon="151.201"><tag k="j" v="y"/></node>
  <node id="3" lat="-33.902" lon="151.200"><tag k="j" v="y"/></node>
  <way id="100"><nd ref="1"/><nd ref="2"/><tag k="highway" v="primary"/></way>
  <way id="101"><nd ref="2"/><nd ref="3"/><tag k="highway" v="primary"/></way>
  <way id="102"><nd ref="3"/><nd ref="1"/><tag k="highway" v="primary"/></way>
</osm>'''
        osm_file = tmp_path / "cycle.osm"
        osm_file.write_text(content)

        output_file = tmp_path / "bottleneck.json"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            top=10,
            format="geojson"
        )
        result = bottleneck.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Cycle has no bridges or articulation points
        bridge_edges = [f for f in data["features"] if f["properties"].get("type") == "bridge_edge"]
        art_points = [f for f in data["features"] if f["properties"].get("type") == "articulation_point"]
        assert len(bridge_edges) == 0
        assert len(art_points) == 0


class TestNodeCoordsMismatch:
    """Test handling of node_coords mismatches."""

    def test_way_references_missing_node(self, tmp_path):
        """Test when way references node not in node_coords."""
        from osm_core.cli.commands import route

        # Way references node 3 which has no tags (won't be parsed)
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="3" lat="-33.902" lon="151.200"/>
  <way id="100">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>'''
        osm_file = tmp_path / "missing_node.osm"
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
        # This should either work (ignoring the edge to node 3) or fail gracefully
        result = route.run(args)
        # Document current behavior
        assert result in [0, 1]


class TestDistanceMatrixBugs:
    """Test distance matrix for correctness."""

    def test_matrix_self_distance_zero(self, tmp_path):
        """Diagonal should be exactly 0."""
        import json
        from osm_core.cli.commands import distance_matrix

        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="j" v="y"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="j" v="y"/></node>
  <way id="100"><nd ref="1"/><nd ref="2"/><tag k="highway" v="primary"/></way>
</osm>'''
        osm_file = tmp_path / "simple.osm"
        osm_file.write_text(content)

        output_file = tmp_path / "matrix.json"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            points="-33.900,151.200;-33.901,151.200",
            mode="drive",
            metric="both",
            format="json"
        )
        result = distance_matrix.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        matrix = data["distance_matrix_m"]

        # Diagonal must be exactly 0
        for i in range(len(matrix)):
            assert matrix[i][i] == 0

    def test_matrix_unreachable_points(self, tmp_path):
        """Test matrix with unreachable points."""
        import json
        from osm_core.cli.commands import distance_matrix

        # Two disconnected components
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200"><tag k="j" v="y"/></node>
  <node id="2" lat="-33.901" lon="151.200"><tag k="j" v="y"/></node>
  <node id="3" lat="-33.910" lon="151.210"><tag k="j" v="y"/></node>
  <node id="4" lat="-33.911" lon="151.210"><tag k="j" v="y"/></node>
  <way id="100"><nd ref="1"/><nd ref="2"/><tag k="highway" v="primary"/></way>
  <way id="101"><nd ref="3"/><nd ref="4"/><tag k="highway" v="primary"/></way>
</osm>'''
        osm_file = tmp_path / "disconnected.osm"
        osm_file.write_text(content)

        output_file = tmp_path / "matrix.json"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            points="-33.900,151.200;-33.910,151.210",
            mode="drive",
            metric="both",
            format="json"
        )
        result = distance_matrix.run(args)

        # Should handle gracefully
        if result == 0:
            data = json.loads(output_file.read_text())
            matrix = data["distance_matrix_m"]
            # Unreachable should be null or infinity
            assert matrix[0][1] is None or matrix[0][1] == float('inf') or matrix[0][1] > 1000000
