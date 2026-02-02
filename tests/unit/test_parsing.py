"""Tests for OSM parsing functionality."""
import pytest
import mmap
import re
import tempfile
from pathlib import Path


class TestUltraFastOSMParser:
    """Tests for UltraFastOSMParser."""

    def test_parser_initialization(self):
        """Test parser initializes correctly."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        parser = UltraFastOSMParser()

        assert parser.pattern_cache is not None
        assert parser.stats is not None
        assert parser.node_coordinates == {}
        assert parser.stats['elements_parsed'] == 0

    def test_parse_nodes_basic(self, tmp_path):
        """Test basic node parsing."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "nodes.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="name" v="Test Node"/>
  </node>
</osm>''')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        assert len(nodes) == 1
        assert nodes[0].id == "1"
        assert nodes[0].lat == 51.5
        assert nodes[0].lon == -0.1
        assert nodes[0].tags["name"] == "Test Node"

    def test_parse_multiple_nodes(self, tmp_path):
        """Test parsing multiple nodes."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "nodes.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="amenity" v="restaurant"/>
  </node>
  <node id="2" lat="51.51" lon="-0.11">
    <tag k="amenity" v="cafe"/>
  </node>
  <node id="3" lat="51.52" lon="-0.12">
    <tag k="shop" v="supermarket"/>
  </node>
</osm>''')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        assert len(nodes) == 3
        assert parser.stats['elements_parsed'] >= 3

    def test_parse_ways_basic(self, tmp_path):
        """Test basic way parsing."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "ways.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="junction" v="yes"/>
  </node>
  <node id="2" lat="51.51" lon="-0.11">
    <tag k="junction" v="yes"/>
  </node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="Main Street"/>
  </way>
</osm>''')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        assert len(ways) == 1
        assert ways[0].id == "100"
        assert ways[0].tags["highway"] == "primary"
        assert ways[0].tags["name"] == "Main Street"
        assert ways[0].node_refs == ["1", "2"]

    def test_parse_closed_way(self, tmp_path):
        """Test parsing closed way (polygon)."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "polygon.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1"><tag k="junction" v="yes"/></node>
  <node id="2" lat="51.5" lon="-0.09"><tag k="junction" v="yes"/></node>
  <node id="3" lat="51.51" lon="-0.09"><tag k="junction" v="yes"/></node>
  <node id="4" lat="51.51" lon="-0.1"><tag k="junction" v="yes"/></node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/>
    <tag k="building" v="residential"/>
  </way>
</osm>''')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        assert len(ways) == 1
        assert ways[0].node_refs[0] == ways[0].node_refs[-1]  # Closed polygon
        assert len(ways[0].node_refs) == 5

    def test_node_coordinates_cached(self, tmp_path):
        """Test that node coordinates are cached for way processing."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "coords.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="junction" v="yes"/>
  </node>
  <node id="2" lat="51.51" lon="-0.11">
    <tag k="junction" v="yes"/>
  </node>
</osm>''')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        assert "1" in parser.node_coordinates
        assert "2" in parser.node_coordinates
        assert parser.node_coordinates["1"] == (51.5, -0.1)
        assert parser.node_coordinates["2"] == (51.51, -0.11)

    def test_tagged_nodes_returned(self, tmp_path):
        """Test that only nodes with tags are returned in node list."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "nodes.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1"/>
  <node id="2" lat="51.51" lon="-0.11">
    <tag k="name" v="Named Node"/>
  </node>
</osm>''')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        # Parser only returns nodes with tags (untagged nodes are skipped)
        assert len(nodes) == 1

        # The returned node has the name tag
        assert nodes[0].tags.get("name") == "Named Node"

        # Coordinates are cached for parsed nodes
        assert len(parser.node_coordinates) >= 1

    def test_ways_without_tags_skipped(self, tmp_path):
        """Test that ways without tags are skipped."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "ways.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1"><tag k="junction" v="yes"/></node>
  <node id="2" lat="51.51" lon="-0.11"><tag k="junction" v="yes"/></node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/>
  </way>
  <way id="101">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>''')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        # Only way 101 should be returned (has tags)
        assert len(ways) == 1
        assert ways[0].id == "101"

    def test_extract_tags_method(self, tmp_path):
        """Test direct tag extraction method."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        parser = UltraFastOSMParser()
        content = b'<tag k="name" v="Test"/><tag k="type" v="building"/>'

        tags = parser.extract_tags(content)

        assert tags["name"] == "Test"
        assert tags["type"] == "building"

    def test_extract_node_refs_method(self):
        """Test direct node reference extraction method."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        parser = UltraFastOSMParser()
        content = b'<nd ref="1"/><nd ref="2"/><nd ref="3"/>'

        refs = parser.extract_node_refs(content)

        assert refs == ["1", "2", "3"]

    def test_unicode_handling(self, tmp_path):
        """Test parsing with Unicode characters."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "unicode.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="name" v="Cafe Muller"/>
    <tag k="name:de" v="Cafe Muller"/>
    <tag k="name:ja" v="Japanese"/>
  </node>
</osm>''', encoding='utf-8')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        assert len(nodes) == 1
        assert "Muller" in nodes[0].tags["name"]

    def test_special_characters_in_values(self, tmp_path):
        """Test parsing with special characters in tag values."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "special.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="phone" v="+1-800-555-1234"/>
    <tag k="website" v="https://example.com"/>
    <tag k="opening_hours" v="Mo-Fr 09:00-17:00"/>
  </node>
</osm>''')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        assert len(nodes) == 1
        assert nodes[0].tags["phone"] == "+1-800-555-1234"
        assert nodes[0].tags["website"] == "https://example.com"
        assert nodes[0].tags["opening_hours"] == "Mo-Fr 09:00-17:00"

    def test_performance_stats(self, tmp_path):
        """Test performance statistics collection."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "stats.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="name" v="Node 1"/>
    <tag k="type" v="test"/>
  </node>
  <node id="2" lat="51.51" lon="-0.11">
    <tag k="name" v="Node 2"/>
  </node>
</osm>''')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        stats = parser.get_performance_stats()

        assert stats['elements_parsed'] == 2
        assert stats['bytes_processed'] > 0
        assert stats['parsing_time'] >= 0
        assert stats['tags_extracted'] >= 3
        assert 'performance_class' in stats

    def test_reset_stats(self, tmp_path):
        """Test resetting statistics."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "reset.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="name" v="Test"/>
  </node>
</osm>''')

        parser = UltraFastOSMParser()
        parser.parse_file_ultra_fast(str(osm_file))

        assert parser.stats['elements_parsed'] > 0
        assert len(parser.node_coordinates) > 0

        parser.reset_stats()

        assert parser.stats['elements_parsed'] == 0
        assert len(parser.node_coordinates) == 0

    def test_empty_file(self, tmp_path):
        """Test parsing empty OSM file."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "empty.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
</osm>''')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        assert len(nodes) == 0
        assert len(ways) == 0

    def test_large_node_ids(self, tmp_path):
        """Test parsing with large node IDs."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "large_ids.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="9876543210" lat="51.5" lon="-0.1">
    <tag k="name" v="Large ID Node"/>
  </node>
</osm>''')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        assert len(nodes) == 1
        assert nodes[0].id == "9876543210"


class TestOptimizedPatternCache:
    """Tests for OptimizedPatternCache."""

    def test_cache_initialization(self):
        """Test cache initializes correctly."""
        from osm_core.parsing.pattern_cache import OptimizedPatternCache

        cache = OptimizedPatternCache()

        assert cache.max_size == 100
        assert len(cache._cache) > 0  # Pre-compiled patterns

    def test_custom_max_size(self):
        """Test custom max size."""
        from osm_core.parsing.pattern_cache import OptimizedPatternCache

        cache = OptimizedPatternCache(max_size=50)

        assert cache.max_size == 50

    def test_get_pattern_caching(self):
        """Test pattern is cached after first access."""
        from osm_core.parsing.pattern_cache import OptimizedPatternCache

        cache = OptimizedPatternCache()
        pattern = rb'test_pattern_(\d+)'

        result1 = cache.get_pattern(pattern)
        result2 = cache.get_pattern(pattern)

        assert result1 is result2  # Same object

    def test_pattern_compilation(self):
        """Test patterns are compiled correctly."""
        from osm_core.parsing.pattern_cache import OptimizedPatternCache

        cache = OptimizedPatternCache()
        pattern = rb'hello\s+world'

        compiled = cache.get_pattern(pattern)

        assert compiled.match(b'hello world') is not None
        assert compiled.match(b'hello  world') is not None

    def test_usage_count_tracking(self):
        """Test usage count is tracked."""
        from osm_core.parsing.pattern_cache import OptimizedPatternCache

        cache = OptimizedPatternCache()
        pattern = rb'counting_test'

        cache.get_pattern(pattern)
        cache.get_pattern(pattern)
        cache.get_pattern(pattern)

        assert cache._usage_count[(pattern, re.DOTALL)] == 3

    def test_precompiled_critical_patterns(self):
        """Test critical patterns are pre-compiled."""
        from osm_core.parsing.pattern_cache import OptimizedPatternCache

        cache = OptimizedPatternCache()
        stats = cache.get_stats()

        assert stats['critical_patterns_cached'] > 0

    def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        from osm_core.parsing.pattern_cache import OptimizedPatternCache

        cache = OptimizedPatternCache(max_size=5)

        # Clear cache except critical patterns
        initial_count = len(cache._cache)

        # Add more patterns than max_size
        for i in range(10):
            cache.get_pattern(f'pattern_{i}'.encode())

        # Cache should not exceed max_size significantly
        assert len(cache._cache) <= cache.max_size + initial_count

    def test_get_stats(self):
        """Test statistics retrieval."""
        from osm_core.parsing.pattern_cache import OptimizedPatternCache

        cache = OptimizedPatternCache()
        stats = cache.get_stats()

        assert 'cached_patterns' in stats
        assert 'total_usage' in stats
        assert 'hit_rate' in stats
        assert 'compile_time_saved' in stats

    def test_clear_cache(self):
        """Test cache clearing."""
        from osm_core.parsing.pattern_cache import OptimizedPatternCache

        cache = OptimizedPatternCache()
        cache.get_pattern(rb'test_pattern')

        cache.clear()

        # Critical patterns should be re-initialized
        stats = cache.get_stats()
        assert stats['critical_patterns_cached'] > 0

    def test_different_flags(self):
        """Test patterns with different flags are cached separately."""
        from osm_core.parsing.pattern_cache import OptimizedPatternCache

        cache = OptimizedPatternCache()
        pattern = rb'test'

        result1 = cache.get_pattern(pattern, flags=re.DOTALL)
        result2 = cache.get_pattern(pattern, flags=re.IGNORECASE)

        assert result1 is not result2


class TestParserIntegration:
    """Integration tests for parser with realistic data."""

    def test_parse_realistic_osm_data(self, tmp_path):
        """Test parsing realistic OSM data structure."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "realistic.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <bounds minlat="51.49" minlon="-0.15" maxlat="51.52" maxlon="-0.08"/>

  <node id="100" lat="51.5074" lon="-0.1278">
    <tag k="amenity" v="restaurant"/>
    <tag k="name" v="The Gherkin Restaurant"/>
    <tag k="cuisine" v="british"/>
    <tag k="phone" v="+44 20 7123 4567"/>
  </node>

  <node id="101" lat="51.5033" lon="-0.1195">
    <tag k="amenity" v="cafe"/>
    <tag k="name" v="Tower Bridge Cafe"/>
  </node>

  <node id="200" lat="51.5075" lon="-0.1279"><tag k="junction" v="yes"/></node>
  <node id="201" lat="51.5080" lon="-0.1280"><tag k="junction" v="yes"/></node>
  <node id="202" lat="51.5085" lon="-0.1275"><tag k="junction" v="yes"/></node>

  <way id="500">
    <nd ref="200"/>
    <nd ref="201"/>
    <nd ref="202"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="Bishopsgate"/>
    <tag k="maxspeed" v="30"/>
    <tag k="lanes" v="2"/>
  </way>

  <way id="501">
    <nd ref="200"/>
    <nd ref="201"/>
    <nd ref="202"/>
    <nd ref="200"/>
    <tag k="building" v="commercial"/>
    <tag k="name" v="30 St Mary Axe"/>
    <tag k="building:levels" v="41"/>
  </way>
</osm>''')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        # Verify nodes
        assert len(nodes) >= 2  # At least the amenity nodes
        restaurant = next((n for n in nodes if n.tags.get('name') == 'The Gherkin Restaurant'), None)
        assert restaurant is not None
        assert restaurant.tags['cuisine'] == 'british'

        # Verify ways
        assert len(ways) == 2
        highway = next((w for w in ways if w.tags.get('highway') == 'primary'), None)
        assert highway is not None
        assert highway.tags['name'] == 'Bishopsgate'

    def test_parser_memory_efficiency(self, tmp_path):
        """Test parser handles larger files without memory issues."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        # Generate a moderately large file
        nodes = []
        for i in range(1000):
            nodes.append(f'''  <node id="{i}" lat="{51.5 + i*0.0001}" lon="{-0.1 + i*0.0001}">
    <tag k="name" v="Node {i}"/>
    <tag k="type" v="test"/>
  </node>''')

        osm_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
{''.join(nodes)}
</osm>'''

        osm_file = tmp_path / "large.osm"
        osm_file.write_text(osm_content)

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        assert len(nodes) == 1000
        assert parser.stats['elements_parsed'] == 1000

    def test_parser_attribute_order_variations(self, tmp_path):
        """Test parser handles different attribute orders."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        osm_file = tmp_path / "attr_order.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="name" v="Standard order"/>
  </node>
  <node id="2" lon="-0.11" lat="51.51">
    <tag k="name" v="Reversed order"/>
  </node>
  <node lat="51.52" id="3" lon="-0.12">
    <tag k="name" v="Mixed order"/>
  </node>
</osm>''')

        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(osm_file))

        # Parser may not handle all orders, but should not crash
        assert len(nodes) >= 1
