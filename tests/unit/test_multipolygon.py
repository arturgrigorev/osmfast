"""Tests for multipolygon assembly."""
import pytest
from osm_core.models.elements import OSMWay, OSMRelation
from osm_core.utils.multipolygon import MultipolygonAssembler, assemble_multipolygon


class TestMultipolygonAssembler:
    """Tests for MultipolygonAssembler class."""

    @pytest.fixture
    def simple_polygon_data(self):
        """Simple closed polygon data."""
        # A simple square
        ways = {
            'w1': OSMWay(id='w1', node_refs=['n1', 'n2', 'n3', 'n4', 'n1'], tags={})
        }
        node_coords = {
            'n1': (0.0, 0.0),
            'n2': (0.0, 1.0),
            'n3': (1.0, 1.0),
            'n4': (1.0, 0.0),
        }
        relation = OSMRelation(
            id='r1',
            members=[{'type': 'way', 'ref': 'w1', 'role': 'outer'}],
            tags={'type': 'multipolygon'}
        )
        return ways, node_coords, relation

    @pytest.fixture
    def polygon_with_hole_data(self):
        """Polygon with a hole."""
        ways = {
            # Outer square
            'w1': OSMWay(id='w1', node_refs=['n1', 'n2', 'n3', 'n4', 'n1'], tags={}),
            # Inner hole
            'w2': OSMWay(id='w2', node_refs=['n5', 'n6', 'n7', 'n8', 'n5'], tags={}),
        }
        node_coords = {
            # Outer
            'n1': (0.0, 0.0),
            'n2': (0.0, 10.0),
            'n3': (10.0, 10.0),
            'n4': (10.0, 0.0),
            # Inner hole
            'n5': (3.0, 3.0),
            'n6': (3.0, 7.0),
            'n7': (7.0, 7.0),
            'n8': (7.0, 3.0),
        }
        relation = OSMRelation(
            id='r1',
            members=[
                {'type': 'way', 'ref': 'w1', 'role': 'outer'},
                {'type': 'way', 'ref': 'w2', 'role': 'inner'},
            ],
            tags={'type': 'multipolygon', 'landuse': 'forest'}
        )
        return ways, node_coords, relation

    def test_assembler_initialization(self, simple_polygon_data):
        """Test assembler initializes correctly."""
        ways, node_coords, _ = simple_polygon_data
        assembler = MultipolygonAssembler(ways, node_coords)
        assert assembler.ways == ways
        assert assembler.node_coords == node_coords

    def test_get_way_coordinates(self, simple_polygon_data):
        """Test way coordinate extraction."""
        ways, node_coords, _ = simple_polygon_data
        assembler = MultipolygonAssembler(ways, node_coords)

        coords = assembler.get_way_coordinates('w1')
        assert coords is not None
        assert len(coords) == 5  # 4 corners + closing point
        assert coords[0] == [0.0, 0.0]  # GeoJSON [lon, lat]

    def test_get_way_coordinates_missing(self, simple_polygon_data):
        """Test missing way returns None."""
        ways, node_coords, _ = simple_polygon_data
        assembler = MultipolygonAssembler(ways, node_coords)

        coords = assembler.get_way_coordinates('nonexistent')
        assert coords is None

    def test_simple_polygon_assembly(self, simple_polygon_data):
        """Test simple polygon assembly."""
        ways, node_coords, relation = simple_polygon_data
        assembler = MultipolygonAssembler(ways, node_coords)

        geometry = assembler.assemble(relation)

        assert geometry is not None
        assert geometry['type'] == 'Polygon'
        assert len(geometry['coordinates']) == 1  # One ring (outer)
        assert len(geometry['coordinates'][0]) == 5  # 5 points

    def test_polygon_with_hole_assembly(self, polygon_with_hole_data):
        """Test polygon with hole assembly."""
        ways, node_coords, relation = polygon_with_hole_data
        assembler = MultipolygonAssembler(ways, node_coords)

        geometry = assembler.assemble(relation)

        assert geometry is not None
        assert geometry['type'] == 'Polygon'
        assert len(geometry['coordinates']) == 2  # Outer + 1 hole
        assert len(geometry['coordinates'][0]) >= 4  # Outer ring
        assert len(geometry['coordinates'][1]) >= 4  # Hole

    def test_non_multipolygon_returns_none(self, simple_polygon_data):
        """Test non-multipolygon relation returns None."""
        ways, node_coords, _ = simple_polygon_data
        relation = OSMRelation(
            id='r1',
            members=[{'type': 'way', 'ref': 'w1', 'role': 'outer'}],
            tags={'type': 'route'}  # Not multipolygon
        )
        assembler = MultipolygonAssembler(ways, node_coords)

        geometry = assembler.assemble(relation)
        assert geometry is None

    def test_winding_order_compliance(self, polygon_with_hole_data):
        """Test RFC 7946 winding order: CCW outer, CW hole."""
        from osm_core.utils.geo_utils import get_ring_winding

        ways, node_coords, relation = polygon_with_hole_data
        assembler = MultipolygonAssembler(ways, node_coords)

        geometry = assembler.assemble(relation)

        # Outer ring should be CCW
        outer = geometry['coordinates'][0]
        assert get_ring_winding(outer) == 'ccw'

        # Inner ring (hole) should be CW
        inner = geometry['coordinates'][1]
        assert get_ring_winding(inner) == 'cw'


class TestAssembleMultipolygonFunction:
    """Tests for assemble_multipolygon convenience function."""

    def test_assemble_multipolygon(self):
        """Test convenience function."""
        ways = {
            'w1': OSMWay(id='w1', node_refs=['n1', 'n2', 'n3', 'n1'], tags={})
        }
        node_coords = {
            'n1': (0.0, 0.0),
            'n2': (0.0, 1.0),
            'n3': (1.0, 0.5),
        }
        relation = OSMRelation(
            id='r1',
            members=[{'type': 'way', 'ref': 'w1', 'role': 'outer'}],
            tags={'type': 'multipolygon'}
        )

        geometry = assemble_multipolygon(relation, ways, node_coords)

        assert geometry is not None
        assert geometry['type'] == 'Polygon'


class TestRingBuilding:
    """Tests for ring building from way segments."""

    def test_build_from_multiple_ways(self):
        """Test ring built from multiple way segments."""
        # Two ways that need to be joined
        ways = {
            'w1': OSMWay(id='w1', node_refs=['n1', 'n2', 'n3'], tags={}),
            'w2': OSMWay(id='w2', node_refs=['n3', 'n4', 'n1'], tags={}),
        }
        node_coords = {
            'n1': (0.0, 0.0),
            'n2': (0.0, 1.0),
            'n3': (1.0, 1.0),
            'n4': (1.0, 0.0),
        }
        relation = OSMRelation(
            id='r1',
            members=[
                {'type': 'way', 'ref': 'w1', 'role': 'outer'},
                {'type': 'way', 'ref': 'w2', 'role': 'outer'},
            ],
            tags={'type': 'multipolygon'}
        )

        assembler = MultipolygonAssembler(ways, node_coords)
        geometry = assembler.assemble(relation)

        assert geometry is not None
        assert geometry['type'] == 'Polygon'
        # Ring should have 4 unique vertices + closing point
        assert len(geometry['coordinates'][0]) >= 4
