"""Tests for core CLI commands: extract, stats, merge, filter."""
import json
import pytest
from argparse import Namespace
from pathlib import Path


class TestStatsCommand:
    """Tests for stats command."""

    def test_stats_summary(self, small_osm_file, capsys):
        """Test stats summary output."""
        from osm_core.cli.commands.stats import cmd_stats

        args = Namespace(
            input_file=str(small_osm_file),
            json=False,
            summary=True,
            suggest_bbox=False
        )
        result = cmd_stats(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "nodes" in captured.out.lower()

    def test_stats_detailed(self, small_osm_file, capsys):
        """Test stats detailed output."""
        from osm_core.cli.commands.stats import cmd_stats

        args = Namespace(
            input_file=str(small_osm_file),
            json=False,
            summary=False,
            suggest_bbox=False
        )
        result = cmd_stats(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "OSM File Statistics" in captured.out
        assert "Elements" in captured.out

    def test_stats_json(self, small_osm_file, capsys):
        """Test stats JSON output."""
        from osm_core.cli.commands.stats import cmd_stats

        args = Namespace(
            input_file=str(small_osm_file),
            json=True,
            summary=False,
            suggest_bbox=False
        )
        result = cmd_stats(args)
        assert result == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        # The to_dict() returns nested structure with 'elements' containing node/way counts
        assert "elements" in data
        assert "nodes" in data["elements"]
        assert "ways" in data["elements"]

    def test_stats_suggest_bbox(self, small_osm_file, capsys):
        """Test stats with bbox suggestion."""
        from osm_core.cli.commands.stats import cmd_stats

        args = Namespace(
            input_file=str(small_osm_file),
            json=False,
            summary=False,
            suggest_bbox=True
        )
        result = cmd_stats(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "--bbox" in captured.out

    def test_stats_missing_file(self, tmp_path, capsys):
        """Test stats with missing file."""
        from osm_core.cli.commands.stats import cmd_stats

        args = Namespace(
            input_file=str(tmp_path / "nonexistent.osm"),
            json=False,
            summary=False,
            suggest_bbox=False
        )
        result = cmd_stats(args)
        assert result == 3  # File not found exit code

    def test_stats_empty_file(self, empty_osm_file, capsys):
        """Test stats with empty file."""
        from osm_core.cli.commands.stats import cmd_stats

        args = Namespace(
            input_file=str(empty_osm_file),
            json=False,
            summary=True,
            suggest_bbox=False
        )
        result = cmd_stats(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "0 nodes" in captured.out

    def test_stats_counts_elements(self, small_osm_file):
        """Test stats correctly counts elements."""
        from osm_core.cli.commands.stats import analyze_osm_file

        stats = analyze_osm_file(str(small_osm_file))

        assert stats.nodes == 4
        assert stats.ways == 2
        assert stats.relations == 0

    def test_stats_detects_highway_types(self, small_osm_file):
        """Test stats detects highway types."""
        from osm_core.cli.commands.stats import analyze_osm_file

        stats = analyze_osm_file(str(small_osm_file))

        assert "primary" in stats.highway_types

    def test_stats_detects_amenity_types(self, small_osm_file):
        """Test stats detects amenity types."""
        from osm_core.cli.commands.stats import analyze_osm_file

        stats = analyze_osm_file(str(small_osm_file))

        assert "restaurant" in stats.amenity_types
        assert "bank" in stats.amenity_types


class TestExtractCommand:
    """Tests for extract command."""

    def test_extract_to_json(self, small_osm_file, tmp_path):
        """Test extracting to JSON."""
        from osm_core.cli.commands.extract import cmd_extract

        output_file = tmp_path / "output.json"
        args = Namespace(
            input_file=str(small_osm_file),
            output_file=str(output_file),
            format="json",
            accept_ways=None,
            reject_ways=None,
            accept_nodes=None,
            reject_nodes=None,
            used_node=False,
            reject_ways_global=False,
            reject_nodes_global=False,
            reject_relations=False,
            bbox=None,
            include_metadata=False,
            quiet=False
        )
        result = cmd_extract(args)
        assert result == 0
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        assert "features" in data or "metadata" in data

    def test_extract_to_geojson(self, small_osm_file, tmp_path):
        """Test extracting to GeoJSON."""
        from osm_core.cli.commands.extract import cmd_extract

        output_file = tmp_path / "output.geojson"
        args = Namespace(
            input_file=str(small_osm_file),
            output_file=str(output_file),
            format="geojson",
            accept_ways=None,
            reject_ways=None,
            accept_nodes=None,
            reject_nodes=None,
            used_node=False,
            reject_ways_global=False,
            reject_nodes_global=False,
            reject_relations=False,
            bbox=None,
            include_metadata=False,
            quiet=False
        )
        result = cmd_extract(args)
        assert result == 0
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"

    def test_extract_to_csv(self, small_osm_file, tmp_path):
        """Test extracting to CSV."""
        from osm_core.cli.commands.extract import cmd_extract

        output_file = tmp_path / "output.csv"
        args = Namespace(
            input_file=str(small_osm_file),
            output_file=str(output_file),
            format="csv",
            accept_ways=None,
            reject_ways=None,
            accept_nodes=None,
            reject_nodes=None,
            used_node=False,
            reject_ways_global=False,
            reject_nodes_global=False,
            reject_relations=False,
            bbox=None,
            include_metadata=True,
            quiet=False
        )
        result = cmd_extract(args)
        assert result == 0
        assert output_file.exists()

        content = output_file.read_text()
        assert len(content) > 0
        assert "," in content  # CSV format

    def test_extract_auto_format_from_extension(self, small_osm_file, tmp_path):
        """Test format auto-detection from file extension."""
        from osm_core.cli.commands.extract import cmd_extract

        output_file = tmp_path / "output.geojson"
        args = Namespace(
            input_file=str(small_osm_file),
            output_file=str(output_file),
            format=None,  # Should detect from extension
            accept_ways=None,
            reject_ways=None,
            accept_nodes=None,
            reject_nodes=None,
            used_node=False,
            reject_ways_global=False,
            reject_nodes_global=False,
            reject_relations=False,
            bbox=None,
            include_metadata=False,
            quiet=True
        )
        result = cmd_extract(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"

    def test_extract_with_accept_nodes_filter(self, small_osm_file, tmp_path):
        """Test extracting with node filter."""
        from osm_core.cli.commands.extract import cmd_extract

        output_file = tmp_path / "output.json"
        args = Namespace(
            input_file=str(small_osm_file),
            output_file=str(output_file),
            format="json",
            accept_ways=None,
            reject_ways=None,
            accept_nodes=["amenity=restaurant"],
            reject_nodes=None,
            used_node=False,
            reject_ways_global=False,
            reject_nodes_global=False,
            reject_relations=False,
            bbox=None,
            include_metadata=False,
            quiet=True
        )
        result = cmd_extract(args)
        assert result == 0

    def test_extract_with_accept_ways_filter(self, small_osm_file, tmp_path):
        """Test extracting with way filter."""
        from osm_core.cli.commands.extract import cmd_extract

        output_file = tmp_path / "output.json"
        args = Namespace(
            input_file=str(small_osm_file),
            output_file=str(output_file),
            format="json",
            accept_ways=["highway=*"],
            reject_ways=None,
            accept_nodes=None,
            reject_nodes=None,
            used_node=True,
            reject_ways_global=False,
            reject_nodes_global=False,
            reject_relations=False,
            bbox=None,
            include_metadata=False,
            quiet=True
        )
        result = cmd_extract(args)
        assert result == 0

    def test_extract_quiet_mode(self, small_osm_file, tmp_path, capsys):
        """Test quiet mode suppresses output."""
        from osm_core.cli.commands.extract import cmd_extract

        output_file = tmp_path / "output.json"
        args = Namespace(
            input_file=str(small_osm_file),
            output_file=str(output_file),
            format="json",
            accept_ways=None,
            reject_ways=None,
            accept_nodes=None,
            reject_nodes=None,
            used_node=False,
            reject_ways_global=False,
            reject_nodes_global=False,
            reject_relations=False,
            bbox=None,
            include_metadata=False,
            quiet=True
        )
        result = cmd_extract(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "Extraction complete" not in captured.out


class TestMergeCommand:
    """Tests for merge command."""

    def test_merge_two_files(self, tmp_path):
        """Test merging two OSM files."""
        from osm_core.cli.commands.merge import cmd_merge

        # Create two small OSM files
        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="amenity" v="restaurant"/>
  </node>
</osm>''')

        file2 = tmp_path / "file2.osm"
        file2.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="2" lat="51.6" lon="-0.2">
    <tag k="amenity" v="cafe"/>
  </node>
</osm>''')

        output_file = tmp_path / "merged.osm"
        args = Namespace(
            input_files=[str(file1), str(file2)],
            output=str(output_file),
            quiet=False
        )
        result = cmd_merge(args)
        assert result == 0
        assert output_file.exists()

        # Verify merged content
        content = output_file.read_text()
        assert 'id="1"' in content
        assert 'id="2"' in content
        assert 'amenity' in content
        assert 'restaurant' in content
        assert 'cafe' in content

    def test_merge_conflicting_ids_keeps_last(self, tmp_path):
        """Test merging files with conflicting IDs keeps last occurrence."""
        from osm_core.cli.commands.merge import cmd_merge

        # Create two files with same node ID
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

        output_file = tmp_path / "merged.osm"
        args = Namespace(
            input_files=[str(file1), str(file2)],
            output=str(output_file),
            quiet=False
        )
        result = cmd_merge(args)
        assert result == 0

        content = output_file.read_text()
        # Last file wins, so "Second" should be present
        assert "Second" in content
        # Only one node with id="1" should exist
        assert content.count('id="1"') == 1

    def test_merge_three_files(self, tmp_path):
        """Test merging three files."""
        from osm_core.cli.commands.merge import cmd_merge

        files = []
        for i in range(3):
            f = tmp_path / f"file{i}.osm"
            f.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="{i+100}" lat="51.{i}" lon="-0.{i}">
    <tag k="name" v="Node{i}"/>
  </node>
</osm>''')
            files.append(str(f))

        output_file = tmp_path / "merged.osm"
        args = Namespace(
            input_files=files,
            output=str(output_file),
            quiet=True
        )
        result = cmd_merge(args)
        assert result == 0

        # Verify all three nodes are present
        content = output_file.read_text()
        assert 'id="100"' in content
        assert 'id="101"' in content
        assert 'id="102"' in content

    def test_merge_nodes_and_ways(self, tmp_path):
        """Test merging files with both nodes and ways."""
        from osm_core.cli.commands.merge import cmd_merge

        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="junction" v="yes"/>
  </node>
  <node id="2" lat="51.51" lon="-0.11">
    <tag k="junction" v="yes"/>
  </node>
  <way id="100">
    <nd ref="1"/>
    <nd ref="2"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>''')

        file2 = tmp_path / "file2.osm"
        file2.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="3" lat="51.52" lon="-0.12">
    <tag k="junction" v="yes"/>
  </node>
  <node id="4" lat="51.53" lon="-0.13">
    <tag k="junction" v="yes"/>
  </node>
  <way id="101">
    <nd ref="3"/>
    <nd ref="4"/>
    <tag k="highway" v="secondary"/>
  </way>
</osm>''')

        output_file = tmp_path / "merged.osm"
        args = Namespace(
            input_files=[str(file1), str(file2)],
            output=str(output_file),
            quiet=True
        )
        result = cmd_merge(args)
        assert result == 0

        content = output_file.read_text()
        # Check nodes (parser only returns nodes with tags)
        assert 'id="1"' in content
        assert 'id="2"' in content
        assert 'id="3"' in content
        assert 'id="4"' in content
        # Check ways
        assert 'id="100"' in content
        assert 'id="101"' in content
        assert 'highway' in content

    def test_merge_preserves_tags(self, tmp_path):
        """Test that merge preserves all tags correctly."""
        from osm_core.cli.commands.merge import cmd_merge

        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="amenity" v="restaurant"/>
    <tag k="name" v="Test Place"/>
    <tag k="cuisine" v="italian"/>
  </node>
</osm>''')

        output_file = tmp_path / "merged.osm"
        args = Namespace(
            input_files=[str(file1)],
            output=str(output_file),
            quiet=True
        )
        # Need at least 2 files
        file2 = tmp_path / "file2.osm"
        file2.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
</osm>''')

        args = Namespace(
            input_files=[str(file1), str(file2)],
            output=str(output_file),
            quiet=True
        )
        result = cmd_merge(args)
        assert result == 0

        content = output_file.read_text()
        assert 'amenity' in content
        assert 'restaurant' in content
        assert 'name' in content
        assert 'Test Place' in content
        assert 'cuisine' in content
        assert 'italian' in content

    def test_merge_escapes_xml_special_chars(self, tmp_path):
        """Test that merge properly escapes XML special characters."""
        from osm_core.cli.commands.merge import cmd_merge

        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="name" v="Joe&apos;s Bar &amp; Grill"/>
  </node>
</osm>''')

        file2 = tmp_path / "file2.osm"
        file2.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
</osm>''')

        output_file = tmp_path / "merged.osm"
        args = Namespace(
            input_files=[str(file1), str(file2)],
            output=str(output_file),
            quiet=True
        )
        result = cmd_merge(args)
        assert result == 0

        # Output should be valid XML
        content = output_file.read_text()
        assert '&amp;' in content or '&' not in content.replace('&amp;', '').replace('&apos;', '').replace('&quot;', '').replace('&lt;', '').replace('&gt;', '')

    def test_merge_insufficient_files(self, tmp_path, capsys):
        """Test merge with less than 2 files fails."""
        from osm_core.cli.commands.merge import cmd_merge

        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1"/>
</osm>''')

        output_file = tmp_path / "merged.osm"
        args = Namespace(
            input_files=[str(file1)],
            output=str(output_file),
            quiet=False
        )
        result = cmd_merge(args)
        assert result == 2  # Error exit code

        captured = capsys.readouterr()
        assert "at least 2" in captured.out.lower()

    def test_merge_missing_file(self, tmp_path):
        """Test merge with missing file fails."""
        from osm_core.cli.commands.merge import cmd_merge

        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1"/>
</osm>''')

        output_file = tmp_path / "merged.osm"
        args = Namespace(
            input_files=[str(file1), str(tmp_path / "nonexistent.osm")],
            output=str(output_file),
            quiet=False
        )

        with pytest.raises(FileNotFoundError):
            cmd_merge(args)

    def test_merge_quiet_mode(self, tmp_path, capsys):
        """Test merge quiet mode suppresses output."""
        from osm_core.cli.commands.merge import cmd_merge

        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1"/>
</osm>''')

        file2 = tmp_path / "file2.osm"
        file2.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="2" lat="51.6" lon="-0.2"/>
</osm>''')

        output_file = tmp_path / "merged.osm"
        args = Namespace(
            input_files=[str(file1), str(file2)],
            output=str(output_file),
            quiet=True
        )
        result = cmd_merge(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "Merge complete" not in captured.out

    def test_merge_output_statistics(self, tmp_path, capsys):
        """Test merge outputs correct statistics."""
        from osm_core.cli.commands.merge import cmd_merge

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
  <node id="3" lat="51.52" lon="-0.12">
    <tag k="test" v="3"/>
  </node>
  <way id="100">
    <nd ref="1"/>
    <nd ref="2"/>
    <nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
</osm>''')

        output_file = tmp_path / "merged.osm"
        args = Namespace(
            input_files=[str(file1), str(file2)],
            output=str(output_file),
            quiet=False
        )
        result = cmd_merge(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "Nodes: 3" in captured.out
        assert "Ways: 1" in captured.out

    def test_merge_valid_osm_output(self, tmp_path):
        """Test merged output is valid OSM XML."""
        from osm_core.cli.commands.merge import cmd_merge
        from osm_core.parsing import UltraFastOSMParser

        file1 = tmp_path / "file1.osm"
        file1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="amenity" v="cafe"/>
  </node>
</osm>''')

        file2 = tmp_path / "file2.osm"
        file2.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="2" lat="51.6" lon="-0.2">
    <tag k="amenity" v="restaurant"/>
  </node>
</osm>''')

        output_file = tmp_path / "merged.osm"
        args = Namespace(
            input_files=[str(file1), str(file2)],
            output=str(output_file),
            quiet=True
        )
        result = cmd_merge(args)
        assert result == 0

        # Verify output can be parsed
        parser = UltraFastOSMParser()
        nodes, ways = parser.parse_file_ultra_fast(str(output_file))
        assert len(nodes) == 2


class TestFilterCommand:
    """Tests for filter command."""

    def test_filter_basic(self, small_osm_file, tmp_path):
        """Test basic filtering."""
        from osm_core.cli.commands.filter import cmd_filter

        output_file = tmp_path / "filtered.osm"
        args = Namespace(
            input_file=str(small_osm_file),
            output=str(output_file),
            accept_ways=["highway=*"],
            reject_ways=None,
            accept_nodes=None,
            reject_nodes=None,
            used_node=False,
            reject_ways_global=False,
            reject_nodes_global=False,
            reject_relations=False,
            bbox=None,
            quiet=False
        )
        result = cmd_filter(args)
        assert result == 0
        assert output_file.exists()

    def test_filter_with_bbox(self, tmp_path):
        """Test filtering with bounding box."""
        from osm_core.cli.commands.filter import cmd_filter

        # Create OSM with nodes at different locations
        osm_file = tmp_path / "input.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="name" v="Inside"/>
  </node>
  <node id="2" lat="52.5" lon="-0.1">
    <tag k="name" v="Outside"/>
  </node>
</osm>''')

        output_file = tmp_path / "filtered.osm"
        args = Namespace(
            input_file=str(osm_file),
            output=str(output_file),
            accept_ways=None,
            reject_ways=None,
            accept_nodes=None,
            reject_nodes=None,
            used_node=False,
            reject_ways_global=False,
            reject_nodes_global=False,
            reject_relations=False,
            bbox=[51.6, -0.2, 51.4, 0.0],  # top, left, bottom, right
            quiet=True
        )
        result = cmd_filter(args)
        assert result == 0

        content = output_file.read_text()
        assert "Inside" in content

    def test_filter_reject_nodes(self, small_osm_file, tmp_path):
        """Test filtering with node rejection."""
        from osm_core.cli.commands.filter import cmd_filter

        output_file = tmp_path / "filtered.osm"
        args = Namespace(
            input_file=str(small_osm_file),
            output=str(output_file),
            accept_ways=None,
            reject_ways=None,
            accept_nodes=["amenity=*"],
            reject_nodes=["amenity=bank"],
            used_node=False,
            reject_ways_global=False,
            reject_nodes_global=False,
            reject_relations=False,
            bbox=None,
            quiet=True
        )
        result = cmd_filter(args)
        assert result == 0


class TestOSMStatsModel:
    """Tests for OSMStats model."""

    def test_stats_initialization(self):
        """Test OSMStats default initialization."""
        from osm_core.models.statistics import OSMStats

        stats = OSMStats()
        assert stats.nodes == 0
        assert stats.ways == 0
        assert stats.relations == 0
        assert stats.total_elements == 0

    def test_stats_update_bounds(self):
        """Test bounds update."""
        from osm_core.models.statistics import OSMStats

        stats = OSMStats()
        stats.update_bounds(51.5, -0.1)
        stats.update_bounds(51.6, -0.2)

        assert stats.min_lat == 51.5
        assert stats.max_lat == 51.6
        assert stats.min_lon == -0.2
        assert stats.max_lon == -0.1

    def test_stats_center(self):
        """Test center calculation."""
        from osm_core.models.statistics import OSMStats

        stats = OSMStats()
        stats.update_bounds(51.5, -0.1)
        stats.update_bounds(51.6, -0.2)

        center = stats.center
        assert center[0] == pytest.approx(51.55, rel=1e-5)
        assert center[1] == pytest.approx(-0.15, rel=1e-5)

    def test_stats_to_dict(self):
        """Test conversion to dictionary."""
        from osm_core.models.statistics import OSMStats

        stats = OSMStats()
        stats.nodes = 100
        stats.ways = 50
        stats.relations = 10

        data = stats.to_dict()
        # The to_dict returns nested structure with 'elements' key
        assert data["elements"]["nodes"] == 100
        assert data["elements"]["ways"] == 50
        assert data["elements"]["relations"] == 10

    def test_stats_processing_rate(self):
        """Test processing rate calculation."""
        from osm_core.models.statistics import OSMStats

        stats = OSMStats()
        stats.nodes = 1000
        stats.ways = 500
        stats.relations = 100
        stats.processing_time = 0.1

        rate = stats.get_processing_rate()
        assert rate == 16000.0  # 1600 elements / 0.1s


class TestConvertCommand:
    """Tests for convert command."""

    def test_convert_osm_to_geojson(self, small_osm_file, tmp_path):
        """Test converting OSM to GeoJSON."""
        from osm_core.cli.commands.convert import run

        output_file = tmp_path / "output.geojson"
        args = Namespace(
            input=str(small_osm_file),
            output=str(output_file),
            format="geojson",
            nodes_only=False,
            ways_only=False,
            tagged_only=False,
            include_area=False,
            include_length=False,
            flatten_tags=False,
            compact=False
        )
        result = run(args)
        assert result == 0
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"

    def test_convert_osm_to_json(self, small_osm_file, tmp_path):
        """Test converting OSM to JSON."""
        from osm_core.cli.commands.convert import run

        output_file = tmp_path / "output.json"
        args = Namespace(
            input=str(small_osm_file),
            output=str(output_file),
            format="json",
            nodes_only=False,
            ways_only=False,
            tagged_only=False,
            include_area=False,
            include_length=False,
            flatten_tags=False,
            compact=False
        )
        result = run(args)
        assert result == 0


class TestInfoCommand:
    """Tests for info command."""

    def test_info_basic(self, small_osm_file, capsys):
        """Test basic info output."""
        from osm_core.cli.commands.info import run

        args = Namespace(
            input=str(small_osm_file),
            json=False,
            oneline=False
        )
        result = run(args)
        assert result == 0

    def test_info_json(self, small_osm_file, capsys):
        """Test info JSON output."""
        from osm_core.cli.commands.info import run

        args = Namespace(
            input=str(small_osm_file),
            json=True,
            oneline=False
        )
        result = run(args)
        assert result == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "file" in data or "nodes" in data


class TestBboxCommand:
    """Tests for bbox command."""

    def test_bbox_calculate(self, small_osm_file, capsys):
        """Test bbox calculation."""
        from osm_core.cli.commands.bbox import run

        args = Namespace(
            input=str(small_osm_file),
            output=None,
            from_coords=None,
            from_center=None,
            radius=None,
            buffer=None,
            expand=None,
            round=None,
            format="text",
            copy=False
        )
        result = run(args)
        assert result == 0

    def test_bbox_json(self, small_osm_file, capsys):
        """Test bbox JSON output."""
        from osm_core.cli.commands.bbox import run

        args = Namespace(
            input=str(small_osm_file),
            output=None,
            from_coords=None,
            from_center=None,
            radius=None,
            buffer=None,
            expand=None,
            round=None,
            format="json",
            copy=False
        )
        result = run(args)
        assert result == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "min_lat" in data or "bbox" in data
