"""Shapefile export functionality.

Requires pyshp: pip install osmfast[shapefile]

Shapefiles require homogeneous geometry types, so this exporter
automatically splits output by geometry type:
- {basename}_points.shp for Point geometries
- {basename}_lines.shp for LineString geometries
- {basename}_polygons.shp for Polygon geometries
"""
import os
from typing import Dict, Any, List, Optional

from osm_core.export.base import ExtractionContext, BaseExporter
from osm_core.extraction.feature_extractor import SemanticFilters
from osm_core.utils.geo_utils import ensure_winding_order

# Optional import - graceful handling if pyshp not installed
try:
    import shapefile
    HAS_PYSHP = True
except ImportError:
    HAS_PYSHP = False
    shapefile = None


# WGS84 projection definition for .prj file
WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137,298.257223563]],'
    'PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]'
)


class ShapefileExporter(BaseExporter):
    """Export to ESRI Shapefile format.

    Auto-splits output by geometry type:
    - {basename}_points.shp for Point geometries (amenities)
    - {basename}_lines.shp for LineString geometries (highways)
    - {basename}_polygons.shp for Polygon geometries (buildings)

    Each shapefile includes:
    - .shp - geometry data
    - .shx - shape index
    - .dbf - attribute data
    - .prj - WGS84 projection definition

    Requires pyshp: pip install osmfast[shapefile]
    """

    # Maximum field name length for DBF format
    MAX_FIELD_NAME = 10

    # Standard attribute fields
    STANDARD_FIELDS = [
        ('osm_id', 'C', 20),       # OSM element ID
        ('osm_type', 'C', 10),     # node/way/relation
        ('category', 'C', 20),     # feature_type (amenity, highway, building)
        ('subcateg', 'C', 30),     # feature_subtype
        ('name', 'C', 100),        # feature name
    ]

    def __init__(self, include_all_tags: bool = False, tag_filter: set = None):
        """Initialize Shapefile exporter.

        Args:
            include_all_tags: Include all OSM tags as DBF fields (may truncate names)
            tag_filter: Optional custom set of tags to include (overrides include_all_tags)

        Raises:
            ImportError: If pyshp is not installed
        """
        if not HAS_PYSHP:
            raise ImportError(
                "pyshp is required for Shapefile export. "
                "Install with: pip install osmfast[shapefile]"
            )
        self.include_all_tags = include_all_tags
        self.tag_filter = tag_filter
        self.semantic_filters = SemanticFilters()

    def get_format_name(self) -> str:
        return 'shapefile'

    def export(self, context: ExtractionContext,
               output_file: str) -> Dict[str, Any]:
        """Export to Shapefile format.

        Creates multiple shapefiles split by geometry type.

        Args:
            context: ExtractionContext with parsed data
            output_file: Base output file path (extension will be stripped)

        Returns:
            Result dict with metadata including paths to created files
        """
        context.parse_and_filter()

        # Remove any extension from output path
        base_path = os.path.splitext(output_file)[0]

        # Extract semantic features
        features = self.semantic_filters.extract_all_features(
            context.nodes,
            context.ways,
            context.node_coordinates,
            include_all_tags=self.include_all_tags,
            tag_filter=self.tag_filter
        )

        # Categorize features by geometry type
        points = []
        lines = []
        polygons = []

        for category_features in features.values():
            for feature in category_features:
                if feature.geometry_type == 'point':
                    points.append(feature)
                elif feature.geometry_type == 'line':
                    lines.append(feature)
                else:  # polygon
                    polygons.append(feature)

        # Create shapefiles for each geometry type
        created_files = []

        if points:
            path = f"{base_path}_points"
            self._write_shapefile(points, path, shapefile.POINT, 'point')
            created_files.append(f"{path}.shp")

        if lines:
            path = f"{base_path}_lines"
            self._write_shapefile(lines, path, shapefile.POLYLINE, 'line')
            created_files.append(f"{path}.shp")

        if polygons:
            path = f"{base_path}_polygons"
            self._write_shapefile(polygons, path, shapefile.POLYGON, 'polygon')
            created_files.append(f"{path}.shp")

        return {
            'metadata': context.build_metadata(
                format='shapefile',
                files_created=created_files,
                points_exported=len(points),
                lines_exported=len(lines),
                polygons_exported=len(polygons),
                total_features_exported=len(points) + len(lines) + len(polygons)
            )
        }

    def _write_shapefile(self, features: List, base_path: str,
                         geom_type: int, geom_name: str) -> None:
        """Write features to a shapefile.

        Args:
            features: List of SemanticFeature objects
            base_path: Output path without extension
            geom_type: shapefile geometry type constant
            geom_name: Geometry name for logging ('point', 'line', 'polygon')
        """
        # Collect all property keys if including extra tags
        extra_fields = set()
        if self.include_all_tags or self.tag_filter is not None:
            for f in features:
                extra_fields.update(f.properties.keys())

        # Create writer
        w = shapefile.Writer(base_path, shapeType=geom_type)

        # Define standard fields
        for name, ftype, size in self.STANDARD_FIELDS:
            w.field(name, ftype, size)

        # Add extra fields (with name truncation for DBF compatibility)
        field_mapping = {}  # original -> truncated
        for field in sorted(extra_fields):
            truncated = self._truncate_field_name(field, field_mapping.values())
            field_mapping[field] = truncated
            w.field(truncated, 'C', 100)

        # Write features
        for feature in features:
            self._write_feature(w, feature, geom_type, field_mapping)

        # Close and save
        w.close()

        # Write .prj file for WGS84
        with open(f"{base_path}.prj", 'w', encoding='utf-8') as prj:
            prj.write(WGS84_PRJ)

    def _truncate_field_name(self, name: str,
                             existing: List[str]) -> str:
        """Truncate field name to DBF limit, ensuring uniqueness.

        Args:
            name: Original field name
            existing: Already used truncated names

        Returns:
            Unique truncated field name (max 10 chars)
        """
        truncated = name[:self.MAX_FIELD_NAME]

        # Ensure uniqueness
        if truncated not in existing:
            return truncated

        # Add numeric suffix if needed
        counter = 1
        while True:
            suffix = str(counter)
            max_base = self.MAX_FIELD_NAME - len(suffix)
            candidate = f"{name[:max_base]}{suffix}"
            if candidate not in existing:
                return candidate
            counter += 1

    def _write_feature(self, writer, feature, geom_type: int,
                       field_mapping: Dict[str, str]) -> None:
        """Write a single feature to the shapefile.

        Args:
            writer: shapefile.Writer instance
            feature: SemanticFeature object
            geom_type: shapefile geometry type constant
            field_mapping: Map of original field names to truncated names
        """
        # Write geometry
        if geom_type == shapefile.POINT:
            # Point: [lon, lat]
            writer.point(feature.coordinates[0], feature.coordinates[1])

        elif geom_type == shapefile.POLYLINE:
            # LineString: [[lon, lat], ...]
            writer.line([feature.coordinates])

        elif geom_type == shapefile.POLYGON:
            # Polygon: [[lon, lat], ...]
            # Shapefiles use clockwise winding for outer rings (opposite of GeoJSON)
            coords = ensure_winding_order(feature.coordinates, 'cw')
            writer.poly([coords])

        # Write attributes
        record = {
            'osm_id': str(feature.id),
            'osm_type': 'node' if feature.geometry_type == 'point' else 'way',
            'category': feature.feature_type or '',
            'subcateg': feature.feature_subtype or '',
            'name': feature.name or '',
        }

        # Add extra fields
        if self.include_all_tags or self.tag_filter is not None:
            for orig, trunc in field_mapping.items():
                value = feature.properties.get(orig, '')
                # Truncate long values to prevent DBF errors
                record[trunc] = str(value)[:254] if value else ''

        writer.record(**record)

    @staticmethod
    def is_available() -> bool:
        """Check if pyshp is installed.

        Returns:
            True if shapefile export is available
        """
        return HAS_PYSHP


def shapefile_available() -> bool:
    """Check if shapefile export is available.

    Returns:
        True if pyshp is installed
    """
    return HAS_PYSHP
