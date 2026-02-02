"""Main OSMFast API.

Provides the high-level OSMFast class for feature extraction.
"""
import os
import time
from typing import Dict, Any, List, Optional

from osm_core.models.elements import OSMNode, OSMWay
from osm_core.models.features import SemanticFeature
from osm_core.filters.osm_filter import OSMFilter
from osm_core.parsing.mmap_parser import UltraFastOSMParser
from osm_core.extraction.feature_extractor import SemanticFilters
from osm_core.export.base import ExtractionContext
from osm_core.export.json_exporter import JSONExporter, GeoJSONExporter
from osm_core.export.xml_exporter import XMLExporter, OSMMerger
from osm_core.export.csv_exporter import CSVExporter


class OSMFast:
    """OSMFast - Ultra-High Performance OpenStreetMap Data Extractor.

    Combines 175x+ performance optimization with semantic feature extraction.
    Production-ready with data integrity validation.
    """

    def __init__(self, osm_filter: Optional[OSMFilter] = None):
        """Initialize OSMFast.

        Args:
            osm_filter: Optional OSMFilter for filtering elements
        """
        self.parser = UltraFastOSMParser()
        self.filters = SemanticFilters()
        self.osm_filter = osm_filter or OSMFilter()

        # Processing statistics
        self.stats = {
            'files_processed': 0,
            'total_processing_time': 0,
            'features_extracted': 0,
            'last_performance_rate': 0
        }

    def _create_context(self, osm_file_path: str) -> ExtractionContext:
        """Create extraction context for a file.

        Args:
            osm_file_path: Path to OSM file

        Returns:
            ExtractionContext instance
        """
        if not os.path.exists(osm_file_path):
            raise FileNotFoundError(f"OSM file not found: {osm_file_path}")

        return ExtractionContext(osm_file_path, self.parser, self.osm_filter)

    def extract_features(self, osm_file_path: str) -> Dict[str, Any]:
        """Extract semantic features from OSM file with ultra-high performance.

        Args:
            osm_file_path: Path to OSM XML file

        Returns:
            Dictionary with extracted features and metadata
        """
        context = self._create_context(osm_file_path)
        context.parse_and_filter()

        # Extract semantic features
        features = self.filters.extract_all_features(
            context.nodes,
            context.ways,
            context.node_coordinates
        )

        total_features = sum(len(f) for f in features.values())

        # Update statistics
        self.stats['files_processed'] += 1
        self.stats['total_processing_time'] += context.processing_time
        self.stats['features_extracted'] += total_features
        self.stats['last_performance_rate'] = (
            total_features / max(context.processing_time, 0.001)
        )

        return {
            'features': features,
            'metadata': context.build_metadata(
                features_extracted={
                    'amenities': len(features['amenities']),
                    'highways': len(features['highways']),
                    'buildings': len(features['buildings']),
                    'total': total_features
                },
                extraction_rate_features_per_second=self.stats['last_performance_rate'],
                parser_stats=self.parser.get_performance_stats()
            )
        }

    def extract_to_geojson(self, osm_file_path: str, output_file: str) -> Dict[str, Any]:
        """Extract features and export to GeoJSON format.

        Args:
            osm_file_path: Input OSM file path
            output_file: Output GeoJSON file path

        Returns:
            Result dictionary with metadata
        """
        context = self._create_context(osm_file_path)
        exporter = GeoJSONExporter()
        result = exporter.export(context, output_file)

        self.stats['files_processed'] += 1
        self.stats['total_processing_time'] += context.processing_time

        print(f"GeoJSON saved to: {output_file}")
        return result

    def extract_to_csv(self, osm_file_path: str, output_file: str,
                       include_metadata: bool = False) -> Dict[str, Any]:
        """Extract elements and export to CSV format.

        Args:
            osm_file_path: Input OSM file path
            output_file: Output CSV file path
            include_metadata: Include metadata columns

        Returns:
            Result dictionary with metadata
        """
        context = self._create_context(osm_file_path)
        exporter = CSVExporter(include_metadata=include_metadata)
        result = exporter.export(context, output_file)

        self.stats['files_processed'] += 1
        self.stats['total_processing_time'] += context.processing_time

        print(f"CSV saved to: {output_file}")
        return result

    def extract_to_xml(self, osm_file_path: str, output_file: str) -> Dict[str, Any]:
        """Extract elements and export to OSM XML format.

        Args:
            osm_file_path: Input OSM file path
            output_file: Output XML file path

        Returns:
            Result dictionary with metadata
        """
        context = self._create_context(osm_file_path)
        exporter = XMLExporter()
        result = exporter.export(context, output_file)

        self.stats['files_processed'] += 1
        self.stats['total_processing_time'] += context.processing_time

        print(f"OSM XML saved to: {output_file}")
        return result

    def extract_to_json(self, osm_file_path: str, output_file: str) -> Dict[str, Any]:
        """Extract features and export to JSON format.

        Args:
            osm_file_path: Input OSM file path
            output_file: Output JSON file path

        Returns:
            Result dictionary with features and metadata
        """
        context = self._create_context(osm_file_path)
        exporter = JSONExporter()
        result = exporter.export(context, output_file)

        self.stats['files_processed'] += 1
        self.stats['total_processing_time'] += context.processing_time

        print(f"JSON saved to: {output_file}")
        return result

    def extract_to_shapefile(self, osm_file_path: str, output_base: str,
                             include_all_tags: bool = False,
                             tag_filter: set = None) -> Dict[str, Any]:
        """Extract features and export to Shapefile format.

        Creates multiple shapefiles split by geometry type:
        - {output_base}_points.shp for Point geometries
        - {output_base}_lines.shp for LineString geometries
        - {output_base}_polygons.shp for Polygon geometries

        Requires pyshp: pip install osmfast[shapefile]

        Args:
            osm_file_path: Input OSM file path
            output_base: Output base path (without extension)
            include_all_tags: Include all OSM tags as DBF fields
            tag_filter: Optional custom set of tags to include (e.g., ROAD_ATTRIBUTES)

        Returns:
            Result dictionary with metadata

        Raises:
            ImportError: If pyshp is not installed
        """
        from osm_core.export import shapefile_available

        if not shapefile_available():
            raise ImportError(
                "pyshp is required for Shapefile export. "
                "Install with: pip install osmfast[shapefile]"
            )

        from osm_core.export.shapefile_exporter import ShapefileExporter

        context = self._create_context(osm_file_path)
        exporter = ShapefileExporter(include_all_tags=include_all_tags, tag_filter=tag_filter)
        result = exporter.export(context, output_base)

        self.stats['files_processed'] += 1
        self.stats['total_processing_time'] += context.processing_time

        files = result['metadata'].get('files_created', [])
        print(f"Shapefile(s) saved: {', '.join(files)}")
        return result

    @staticmethod
    def merge_osm_files(input_files: List[str], output_file: str) -> Dict[str, Any]:
        """Merge multiple OSM XML files into one.

        Args:
            input_files: List of input file paths
            output_file: Output file path

        Returns:
            Metadata dictionary
        """
        result = OSMMerger.merge(input_files, output_file)
        print(f"Merged {len(input_files)} files to: {output_file}")
        return result

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics.

        Returns:
            Dictionary with processing statistics
        """
        avg_processing_time = (
            self.stats['total_processing_time'] /
            max(self.stats['files_processed'], 1)
        )

        return {
            'files_processed': self.stats['files_processed'],
            'total_features_extracted': self.stats['features_extracted'],
            'average_processing_time': avg_processing_time,
            'last_performance_rate': self.stats['last_performance_rate'],
            'total_processing_time': self.stats['total_processing_time']
        }
