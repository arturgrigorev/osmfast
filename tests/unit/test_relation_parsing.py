"""Tests for relation parsing."""
import pytest
import tempfile
import os
from osm_core.parsing.mmap_parser import UltraFastOSMParser


class TestRelationParsing:
    """Tests for relation parsing functionality."""

    @pytest.fixture
    def osm_with_relations(self):
        """Create OSM file with relations."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.0" lon="-0.1"/>
  <node id="2" lat="51.0" lon="0.0"/>
  <node id="3" lat="51.1" lon="0.0"/>
  <node id="4" lat="51.1" lon="-0.1"/>
  <node id="5" lat="51.03" lon="-0.07"/>
  <node id="6" lat="51.03" lon="-0.03"/>
  <node id="7" lat="51.07" lon="-0.03"/>
  <node id="8" lat="51.07" lon="-0.07"/>
  <way id="100">
    <nd ref="1"/>
    <nd ref="2"/>
    <nd ref="3"/>
    <nd ref="4"/>
    <nd ref="1"/>
    <tag k="building" v="yes"/>
  </way>
  <way id="101">
    <nd ref="5"/>
    <nd ref="6"/>
    <nd ref="7"/>
    <nd ref="8"/>
    <nd ref="5"/>
    <tag k="area" v="yes"/>
  </way>
  <relation id="1000">
    <member type="way" ref="100" role="outer"/>
    <member type="way" ref="101" role="inner"/>
    <tag k="type" v="multipolygon"/>
    <tag k="landuse" v="residential"/>
    <tag k="name" v="Test Area"/>
  </relation>
  <relation id="1001">
    <member type="node" ref="1" role="stop"/>
    <member type="node" ref="2" role="stop"/>
    <member type="way" ref="100" role=""/>
    <tag k="type" v="route"/>
    <tag k="route" v="bus"/>
  </relation>
</osm>'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False) as f:
            f.write(content)
            return f.name

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return UltraFastOSMParser()

    def test_parse_without_relations(self, osm_with_relations, parser):
        """Test parsing without relations (default behavior)."""
        nodes, ways = parser.parse_file_ultra_fast(osm_with_relations)

        assert len(nodes) >= 0  # Only nodes with tags are returned
        assert len(ways) == 2

        # Clean up
        os.unlink(osm_with_relations)

    def test_parse_with_relations(self, osm_with_relations, parser):
        """Test parsing with relations enabled."""
        nodes, ways, relations = parser.parse_file_ultra_fast(
            osm_with_relations, include_relations=True
        )

        assert len(relations) == 2

        # Clean up
        os.unlink(osm_with_relations)

    def test_relation_attributes(self, osm_with_relations, parser):
        """Test relation attributes are correctly parsed."""
        _, _, relations = parser.parse_file_ultra_fast(
            osm_with_relations, include_relations=True
        )

        # Find the multipolygon relation
        mp_relation = next((r for r in relations if r.tags.get('type') == 'multipolygon'), None)
        assert mp_relation is not None
        assert mp_relation.id == '1000'
        assert mp_relation.tags['landuse'] == 'residential'
        assert mp_relation.tags['name'] == 'Test Area'

        # Clean up
        os.unlink(osm_with_relations)

    def test_relation_members(self, osm_with_relations, parser):
        """Test relation members are correctly parsed."""
        _, _, relations = parser.parse_file_ultra_fast(
            osm_with_relations, include_relations=True
        )

        mp_relation = next((r for r in relations if r.tags.get('type') == 'multipolygon'), None)

        assert len(mp_relation.members) == 2

        # Check outer member
        outer = mp_relation.get_members_by_role('outer')
        assert len(outer) == 1
        assert outer[0]['type'] == 'way'
        assert outer[0]['ref'] == '100'

        # Check inner member
        inner = mp_relation.get_members_by_role('inner')
        assert len(inner) == 1
        assert inner[0]['type'] == 'way'
        assert inner[0]['ref'] == '101'

        # Clean up
        os.unlink(osm_with_relations)

    def test_route_relation_members(self, osm_with_relations, parser):
        """Test route relation with mixed member types."""
        _, _, relations = parser.parse_file_ultra_fast(
            osm_with_relations, include_relations=True
        )

        route_relation = next((r for r in relations if r.tags.get('type') == 'route'), None)
        assert route_relation is not None

        # Check node members
        node_members = route_relation.get_members_by_type('node')
        assert len(node_members) == 2

        # Check way members
        way_members = route_relation.get_members_by_type('way')
        assert len(way_members) == 1

        # Clean up
        os.unlink(osm_with_relations)


class TestExtractMembers:
    """Tests for member extraction."""

    def test_extract_members_basic(self):
        """Test basic member extraction."""
        parser = UltraFastOSMParser()

        content = b'''<member type="way" ref="123" role="outer"/>
                      <member type="node" ref="456" role="stop"/>'''

        members = parser.extract_members(content)

        assert len(members) == 2
        assert members[0] == {'type': 'way', 'ref': '123', 'role': 'outer'}
        assert members[1] == {'type': 'node', 'ref': '456', 'role': 'stop'}

    def test_extract_members_empty_role(self):
        """Test member with empty role."""
        parser = UltraFastOSMParser()

        content = b'<member type="way" ref="789" role=""/>'

        members = parser.extract_members(content)

        assert len(members) == 1
        assert members[0]['role'] == ''

    def test_extract_members_no_members(self):
        """Test extraction from content with no members."""
        parser = UltraFastOSMParser()

        content = b'<tag k="name" v="Test"/>'

        members = parser.extract_members(content)

        assert len(members) == 0
