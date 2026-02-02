"""Tests for data models."""
import pytest
from osm_core.models.elements import OSMNode, OSMWay, OSMRelation
from osm_core.models.features import SemanticFeature


class TestOSMNode:
    """Tests for OSMNode class."""

    def test_creation(self, sample_node):
        """Test node creation with valid data."""
        assert sample_node.id == "12345"
        assert sample_node.lat == 51.5
        assert sample_node.lon == -0.1
        assert sample_node.tags["amenity"] == "restaurant"

    def test_to_geojson_feature(self, sample_node):
        """Test GeoJSON feature generation."""
        geojson = sample_node.to_geojson_feature()

        assert geojson["type"] == "Feature"
        assert geojson["geometry"]["type"] == "Point"
        assert geojson["geometry"]["coordinates"] == [-0.1, 51.5]
        assert geojson["properties"]["id"] == "12345"
        assert geojson["properties"]["osm_type"] == "node"
        assert geojson["properties"]["amenity"] == "restaurant"


class TestOSMWay:
    """Tests for OSMWay class."""

    def test_creation(self, sample_way):
        """Test way creation with valid data."""
        assert sample_way.id == "67890"
        assert len(sample_way.node_refs) == 4
        assert sample_way.tags["building"] == "residential"

    def test_nodes_property(self, sample_way):
        """Test backward compatibility with .nodes property."""
        assert sample_way.nodes == sample_way.node_refs

    def test_is_closed(self, sample_way):
        """Test closed way detection."""
        assert sample_way.is_closed is True

    def test_is_closed_open_way(self):
        """Test open way detection."""
        way = OSMWay(id="1", node_refs=["1", "2", "3"], tags={})
        assert way.is_closed is False

    def test_is_area(self, sample_way):
        """Test area detection."""
        assert sample_way.is_area is True

    def test_to_geojson_feature(self, sample_way):
        """Test GeoJSON feature generation."""
        node_coords = {
            "1": (51.5, -0.1),
            "2": (51.51, -0.11),
            "3": (51.52, -0.12)
        }
        geojson = sample_way.to_geojson_feature(node_coords)

        assert geojson["type"] == "Feature"
        assert geojson["properties"]["id"] == "67890"
        assert geojson["properties"]["node_count"] == 4


class TestSemanticFeature:
    """Tests for SemanticFeature class."""

    def test_point_feature(self):
        """Test point geometry feature."""
        feature = SemanticFeature(
            id="1",
            feature_type="amenity",
            feature_subtype="restaurant",
            name="Test",
            geometry_type="point",
            coordinates=[0.0, 51.0],
            properties={"cuisine": "italian"}
        )

        geojson = feature.to_geojson_feature()
        assert geojson["geometry"]["type"] == "Point"
        assert geojson["properties"]["category"] == "amenity"

    def test_line_feature(self):
        """Test line geometry feature."""
        feature = SemanticFeature(
            id="1",
            feature_type="highway",
            feature_subtype="primary",
            name="Main St",
            geometry_type="line",
            coordinates=[[0.0, 51.0], [0.1, 51.1]],
            properties={}
        )

        geojson = feature.to_geojson_feature()
        assert geojson["geometry"]["type"] == "LineString"

    def test_polygon_feature(self):
        """Test polygon geometry feature."""
        feature = SemanticFeature(
            id="1",
            feature_type="building",
            feature_subtype="residential",
            name="House",
            geometry_type="polygon",
            coordinates=[[0.0, 51.0], [0.1, 51.0], [0.1, 51.1], [0.0, 51.0]],
            properties={}
        )

        geojson = feature.to_geojson_feature()
        assert geojson["geometry"]["type"] == "Polygon"
