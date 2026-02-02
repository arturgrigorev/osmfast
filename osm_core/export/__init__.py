"""Export functionality for various output formats."""

from osm_core.export.base import ExtractionContext, BaseExporter
from osm_core.export.json_exporter import JSONExporter, GeoJSONExporter
from osm_core.export.xml_exporter import XMLExporter
from osm_core.export.csv_exporter import CSVExporter

# Conditional import for Shapefile support (requires pyshp)
try:
    from osm_core.export.shapefile_exporter import ShapefileExporter, shapefile_available
    _HAS_SHAPEFILE = True
except ImportError:
    ShapefileExporter = None
    _HAS_SHAPEFILE = False

    def shapefile_available():
        return False

__all__ = [
    'ExtractionContext', 'BaseExporter',
    'JSONExporter', 'GeoJSONExporter', 'XMLExporter', 'CSVExporter',
    'shapefile_available',
]

if _HAS_SHAPEFILE:
    __all__.append('ShapefileExporter')
