"""Tests for Shapefile exporter.

These tests require pyshp to be installed. If not available, tests are skipped.
"""
import pytest
import tempfile
import os

# Skip all tests in this module if pyshp is not installed
shapefile = pytest.importorskip("shapefile")

from osm_core.export.shapefile_exporter import (
    ShapefileExporter, shapefile_available, WGS84_PRJ
)
from osm_core.export.base import ExtractionContext
from osm_core.parsing.mmap_parser import UltraFastOSMParser
from osm_core.filters.osm_filter import OSMFilter


class TestShapefileAvailability:
    """Tests for shapefile availability check."""

    def test_shapefile_available(self):
        """Test that shapefile is available when pyshp is installed."""
        assert shapefile_available() is True

    def test_exporter_is_available(self):
        """Test static availability check."""
        assert ShapefileExporter.is_available() is True


class TestShapefileExporter:
    """Tests for ShapefileExporter class."""

    @pytest.fixture
    def osm_file(self):
        """Create sample OSM file with various feature types."""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="amenity" v="restaurant"/>
    <tag k="name" v="Test Restaurant"/>
  </node>
  <node id="2" lat="51.51" lon="-0.09">
    <tag k="amenity" v="cafe"/>
    <tag k="name" v="Test Cafe"/>
  </node>
  <node id="10" lat="51.5" lon="-0.1"/>
  <node id="11" lat="51.51" lon="-0.1"/>
  <node id="12" lat="51.51" lon="-0.09"/>
  <node id="13" lat="51.5" lon="-0.09"/>
  <node id="20" lat="51.5" lon="-0.08"/>
  <node id="21" lat="51.52" lon="-0.08"/>
  <way id="100">
    <nd ref="10"/>
    <nd ref="11"/>
    <nd ref="12"/>
    <nd ref="13"/>
    <nd ref="10"/>
    <tag k="building" v="residential"/>
    <tag k="name" v="Test Building"/>
  </way>
  <way id="101">
    <nd ref="20"/>
    <nd ref="21"/>
    <tag k="highway" v="residential"/>
    <tag k="name" v="Test Street"/>
  </way>
</osm>'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.osm', delete=False) as f:
            f.write(content)
            return f.name

    @pytest.fixture
    def output_base(self):
        """Create temporary output base path."""
        with tempfile.NamedTemporaryFile(suffix='', delete=False) as f:
            base = f.name
        # Remove the empty file
        os.unlink(base)
        return base

    def test_exporter_initialization(self):
        """Test exporter initializes correctly."""
        exporter = ShapefileExporter()
        assert exporter.include_all_tags is False

        exporter_with_tags = ShapefileExporter(include_all_tags=True)
        assert exporter_with_tags.include_all_tags is True

    def test_get_format_name(self):
        """Test format name."""
        exporter = ShapefileExporter()
        assert exporter.get_format_name() == 'shapefile'

    def test_export_creates_files(self, osm_file, output_base):
        """Test export creates shapefile components."""
        parser = UltraFastOSMParser()
        osm_filter = OSMFilter()
        context = ExtractionContext(osm_file, parser, osm_filter)

        exporter = ShapefileExporter()
        result = exporter.export(context, output_base)

        # Check metadata
        metadata = result['metadata']
        assert 'files_created' in metadata
        assert metadata['total_features_exported'] > 0

        # Check that files were created
        files_created = metadata['files_created']
        assert len(files_created) > 0

        for shp_path in files_created:
            assert os.path.exists(shp_path)
            # Check companion files
            base = os.path.splitext(shp_path)[0]
            assert os.path.exists(f"{base}.shx")
            assert os.path.exists(f"{base}.dbf")
            assert os.path.exists(f"{base}.prj")

        # Cleanup
        for shp_path in files_created:
            base = os.path.splitext(shp_path)[0]
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                try:
                    os.unlink(f"{base}{ext}")
                except FileNotFoundError:
                    pass
        os.unlink(osm_file)

    def test_prj_file_contains_wgs84(self, osm_file, output_base):
        """Test that .prj file contains WGS84 definition."""
        parser = UltraFastOSMParser()
        osm_filter = OSMFilter()
        context = ExtractionContext(osm_file, parser, osm_filter)

        exporter = ShapefileExporter()
        result = exporter.export(context, output_base)

        files_created = result['metadata']['files_created']
        for shp_path in files_created:
            prj_path = os.path.splitext(shp_path)[0] + '.prj'
            with open(prj_path, 'r') as f:
                content = f.read()
            assert 'WGS_1984' in content or 'WGS84' in content.upper()

        # Cleanup
        for shp_path in files_created:
            base = os.path.splitext(shp_path)[0]
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                try:
                    os.unlink(f"{base}{ext}")
                except FileNotFoundError:
                    pass
        os.unlink(osm_file)

    def test_points_shapefile(self, osm_file, output_base):
        """Test points shapefile is readable."""
        parser = UltraFastOSMParser()
        osm_filter = OSMFilter()
        context = ExtractionContext(osm_file, parser, osm_filter)

        exporter = ShapefileExporter()
        result = exporter.export(context, output_base)

        points_count = result['metadata']['points_exported']
        if points_count > 0:
            with shapefile.Reader(f"{output_base}_points") as sf:
                shapes = sf.shapes()
                records = sf.records()

                assert len(shapes) == points_count
                assert len(records) == points_count

                # Check first shape is a point
                assert shapes[0].shapeType == shapefile.POINT

        # Cleanup
        files_created = result['metadata']['files_created']
        for shp_path in files_created:
            base = os.path.splitext(shp_path)[0]
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                try:
                    os.unlink(f"{base}{ext}")
                except (FileNotFoundError, PermissionError):
                    pass
        try:
            os.unlink(osm_file)
        except (FileNotFoundError, PermissionError):
            pass

    def test_lines_shapefile(self, osm_file, output_base):
        """Test lines shapefile is readable."""
        parser = UltraFastOSMParser()
        osm_filter = OSMFilter()
        context = ExtractionContext(osm_file, parser, osm_filter)

        exporter = ShapefileExporter()
        result = exporter.export(context, output_base)

        lines_count = result['metadata']['lines_exported']
        if lines_count > 0:
            with shapefile.Reader(f"{output_base}_lines") as sf:
                shapes = sf.shapes()

                assert len(shapes) == lines_count
                assert shapes[0].shapeType == shapefile.POLYLINE

        # Cleanup
        files_created = result['metadata']['files_created']
        for shp_path in files_created:
            base = os.path.splitext(shp_path)[0]
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                try:
                    os.unlink(f"{base}{ext}")
                except (FileNotFoundError, PermissionError):
                    pass
        try:
            os.unlink(osm_file)
        except (FileNotFoundError, PermissionError):
            pass

    def test_polygons_shapefile(self, osm_file, output_base):
        """Test polygons shapefile is readable."""
        parser = UltraFastOSMParser()
        osm_filter = OSMFilter()
        context = ExtractionContext(osm_file, parser, osm_filter)

        exporter = ShapefileExporter()
        result = exporter.export(context, output_base)

        polygons_count = result['metadata']['polygons_exported']
        if polygons_count > 0:
            with shapefile.Reader(f"{output_base}_polygons") as sf:
                shapes = sf.shapes()

                assert len(shapes) == polygons_count
                assert shapes[0].shapeType == shapefile.POLYGON

        # Cleanup
        files_created = result['metadata']['files_created']
        for shp_path in files_created:
            base = os.path.splitext(shp_path)[0]
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                try:
                    os.unlink(f"{base}{ext}")
                except (FileNotFoundError, PermissionError):
                    pass
        try:
            os.unlink(osm_file)
        except (FileNotFoundError, PermissionError):
            pass

    def test_dbf_fields(self, osm_file, output_base):
        """Test DBF fields are correctly defined."""
        parser = UltraFastOSMParser()
        osm_filter = OSMFilter()
        context = ExtractionContext(osm_file, parser, osm_filter)

        exporter = ShapefileExporter()
        result = exporter.export(context, output_base)

        points_count = result['metadata']['points_exported']
        if points_count > 0:
            with shapefile.Reader(f"{output_base}_points") as sf:
                fields = [f[0] for f in sf.fields[1:]]  # Skip DeletionFlag

                # Check standard fields
                assert 'osm_id' in fields
                assert 'osm_type' in fields
                assert 'category' in fields
                assert 'subcateg' in fields
                assert 'name' in fields

        # Cleanup
        files_created = result['metadata']['files_created']
        for shp_path in files_created:
            base = os.path.splitext(shp_path)[0]
            for ext in ['.shp', '.shx', '.dbf', '.prj']:
                try:
                    os.unlink(f"{base}{ext}")
                except (FileNotFoundError, PermissionError):
                    pass
        try:
            os.unlink(osm_file)
        except (FileNotFoundError, PermissionError):
            pass


class TestWGS84PRJ:
    """Tests for WGS84 projection constant."""

    def test_prj_contains_required_elements(self):
        """Test WGS84 PRJ string has required elements."""
        assert 'GEOGCS' in WGS84_PRJ
        assert 'WGS_1984' in WGS84_PRJ
        assert 'DATUM' in WGS84_PRJ
        assert 'SPHEROID' in WGS84_PRJ
