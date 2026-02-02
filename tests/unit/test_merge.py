"""Unit tests for OSM merge functionality."""
import pytest
from pathlib import Path


class TestOSMMerger:
    """Tests for OSMMerger class."""

    def test_merge_basic(self, tmp_path):
        """Test basic merge functionality."""
        from osm_core.export.xml_exporter import OSMMerger

        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="name" v="Node1"/>
  </node>
</osm>''')

        file2 = tmp_path / "file2.osm"
        file2.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="2" lat="51.6" lon="-0.2">
    <tag k="name" v="Node2"/>
  </node>
</osm>''')

        output = tmp_path / "merged.osm"
        result = OSMMerger.merge([str(file1), str(file2)], str(output))

        assert output.exists()
        assert 'metadata' in result
        assert result['metadata']['elements_merged']['nodes'] == 2

    def test_merge_returns_metadata(self, tmp_path):
        """Test merge returns correct metadata."""
        from osm_core.export.xml_exporter import OSMMerger

        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="test" v="1"/>
  </node>
  <node id="2" lat="51.51" lon="-0.11">
    <tag k="test" v="2"/>
  </node>
</osm>''')

        file2 = tmp_path / "file2.osm"
        file2.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <way id="100">
    <nd ref="1"/>
    <nd ref="2"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>''')

        output = tmp_path / "merged.osm"
        result = OSMMerger.merge([str(file1), str(file2)], str(output))

        metadata = result['metadata']
        assert 'processing_time_seconds' in metadata
        assert 'elements_merged' in metadata
        assert metadata['elements_merged']['nodes'] == 2
        assert metadata['elements_merged']['ways'] == 1
        assert metadata['elements_merged']['total'] == 3
        assert 'merge_rate_elements_per_second' in metadata

    def test_merge_deduplicates_by_id(self, tmp_path):
        """Test merge removes duplicates by ID."""
        from osm_core.export.xml_exporter import OSMMerger
        from osm_core.parsing import UltraFastOSMParser

        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="name" v="First"/>
  </node>
</osm>''')

        file2 = tmp_path / "file2.osm"
        file2.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="name" v="Second"/>
  </node>
</osm>''')

        output = tmp_path / "merged.osm"
        result = OSMMerger.merge([str(file1), str(file2)], str(output))

        # Only one node should exist
        assert result['metadata']['elements_merged']['nodes'] == 1

        # Verify last one wins
        parser = UltraFastOSMParser()
        nodes, _ = parser.parse_file_ultra_fast(str(output))
        assert len(nodes) == 1
        assert nodes[0].tags['name'] == 'Second'

    def test_merge_file_not_found(self, tmp_path):
        """Test merge raises error for missing file."""
        from osm_core.export.xml_exporter import OSMMerger

        file1 = tmp_path / "exists.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
</osm>''')

        output = tmp_path / "merged.osm"

        with pytest.raises(FileNotFoundError):
            OSMMerger.merge([str(file1), str(tmp_path / "missing.osm")], str(output))

    def test_merge_empty_files(self, tmp_path):
        """Test merging empty OSM files."""
        from osm_core.export.xml_exporter import OSMMerger

        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
</osm>''')

        file2 = tmp_path / "file2.osm"
        file2.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
</osm>''')

        output = tmp_path / "merged.osm"
        result = OSMMerger.merge([str(file1), str(file2)], str(output))

        assert result['metadata']['elements_merged']['total'] == 0
        assert output.exists()

    def test_merge_many_files(self, tmp_path):
        """Test merging many files at once."""
        from osm_core.export.xml_exporter import OSMMerger

        files = []
        for i in range(10):
            f = tmp_path / f"file{i}.osm"
            f.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="{i}" lat="51.{i}" lon="-0.{i}">
    <tag k="name" v="Node{i}"/>
  </node>
</osm>''')
            files.append(str(f))

        output = tmp_path / "merged.osm"
        result = OSMMerger.merge(files, str(output))

        assert result['metadata']['elements_merged']['nodes'] == 10
        assert len(result['metadata']['input_files']) == 10

    def test_merge_preserves_way_node_refs(self, tmp_path):
        """Test merge preserves way node references."""
        from osm_core.export.xml_exporter import OSMMerger
        from osm_core.parsing import UltraFastOSMParser

        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <way id="100">
    <nd ref="1"/>
    <nd ref="2"/>
    <nd ref="3"/>
    <nd ref="4"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>''')

        file2 = tmp_path / "file2.osm"
        file2.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
</osm>''')

        output = tmp_path / "merged.osm"
        OSMMerger.merge([str(file1), str(file2)], str(output))

        parser = UltraFastOSMParser()
        _, ways = parser.parse_file_ultra_fast(str(output))
        assert len(ways) == 1
        assert ways[0].node_refs == ['1', '2', '3', '4']

    def test_merge_output_is_valid_xml(self, tmp_path):
        """Test merged output is valid XML."""
        from osm_core.export.xml_exporter import OSMMerger
        import xml.etree.ElementTree as ET

        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="name" v="Test"/>
  </node>
</osm>''')

        file2 = tmp_path / "file2.osm"
        file2.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
</osm>''')

        output = tmp_path / "merged.osm"
        OSMMerger.merge([str(file1), str(file2)], str(output))

        # Should parse without error
        tree = ET.parse(str(output))
        root = tree.getroot()
        assert root.tag == 'osm'
