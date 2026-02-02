"""JSON and GeoJSON export functionality."""
import json
from typing import Dict, Any, List

from osm_core.export.base import ExtractionContext, BaseExporter
from osm_core.extraction.feature_extractor import SemanticFilters
from osm_core.utils.geo_utils import ensure_winding_order
from osm_core.utils.multipolygon import MultipolygonAssembler


class JSONExporter(BaseExporter):
    """Export to JSON format with semantic features."""

    def __init__(self):
        self.semantic_filters = SemanticFilters()

    def get_format_name(self) -> str:
        return 'json'

    def export(self, context: ExtractionContext,
               output_file: str) -> Dict[str, Any]:
        """Export semantic features to JSON.

        Args:
            context: ExtractionContext with parsed data
            output_file: Output file path

        Returns:
            Result dict with features and metadata
        """
        context.parse_and_filter()

        # Extract semantic features
        features = self.semantic_filters.extract_all_features(
            context.nodes,
            context.ways,
            context.node_coordinates
        )

        # Convert features to dicts
        features_dict = {
            'amenities': [f.to_dict() for f in features['amenities']],
            'highways': [f.to_dict() for f in features['highways']],
            'buildings': [f.to_dict() for f in features['buildings']]
        }

        total_features = sum(len(f) for f in features.values())

        # Build result
        result = {
            'features': features_dict,
            'metadata': context.build_metadata(
                features_extracted={
                    'amenities': len(features['amenities']),
                    'highways': len(features['highways']),
                    'buildings': len(features['buildings']),
                    'total': total_features
                },
                extraction_rate_features_per_second=(
                    total_features / max(context.processing_time, 0.001)
                )
            )
        }

        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, default=str)

        return result


class GeoJSONExporter(BaseExporter):
    """Export to GeoJSON format with RFC 7946 compliance.

    Supports:
    - RFC 7946 compliant winding order (CCW exterior, CW interior)
    - Multipolygon relations
    - Point, LineString, Polygon, and MultiPolygon geometries
    """

    def __init__(self, include_multipolygons: bool = True):
        """Initialize GeoJSON exporter.

        Args:
            include_multipolygons: If True, parse and include multipolygon relations
        """
        self.semantic_filters = SemanticFilters()
        self.include_multipolygons = include_multipolygons

    def get_format_name(self) -> str:
        return 'geojson'

    def export(self, context: ExtractionContext,
               output_file: str) -> Dict[str, Any]:
        """Export to GeoJSON FeatureCollection.

        Args:
            context: ExtractionContext with parsed data
            output_file: Output file path

        Returns:
            Result dict with metadata
        """
        # Enable relations if we need multipolygons
        if self.include_multipolygons:
            context.include_relations = True

        context.parse_and_filter()

        # Extract semantic features
        features = self.semantic_filters.extract_all_features(
            context.nodes,
            context.ways,
            context.node_coordinates
        )

        # Convert to GeoJSON features with RFC 7946 compliance
        geojson_features: List[Dict[str, Any]] = []

        for category_features in features.values():
            for feature in category_features:
                geojson_feat = feature.to_geojson_feature()
                self._ensure_rfc7946_compliance(geojson_feat)
                geojson_features.append(geojson_feat)

        # Process multipolygon relations
        multipolygon_count = 0
        if self.include_multipolygons and context.relations:
            mp_features = self._process_multipolygons(context)
            geojson_features.extend(mp_features)
            multipolygon_count = len(mp_features)

        # Build GeoJSON FeatureCollection
        geojson = {
            'type': 'FeatureCollection',
            'features': geojson_features,
            'properties': {
                'source': context.osm_file_path,
                'generator': 'osmfast',
                'feature_count': len(geojson_features),
                'rfc7946_compliant': True
            }
        }

        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, indent=2)

        return {
            'metadata': context.build_metadata(
                format='geojson',
                features_exported=len(geojson_features),
                multipolygons_exported=multipolygon_count,
                rfc7946_compliant=True
            )
        }

    def _ensure_rfc7946_compliance(self, feature: Dict[str, Any]) -> None:
        """Ensure geometry follows RFC 7946 winding order rules.

        RFC 7946 requires:
        - Exterior rings: counter-clockwise (CCW)
        - Interior rings (holes): clockwise (CW)

        Args:
            feature: GeoJSON Feature dict (modified in place)
        """
        geom = feature.get('geometry', {})
        geom_type = geom.get('type')
        coords = geom.get('coordinates')

        if not coords:
            return

        if geom_type == 'Polygon':
            # First ring is exterior (CCW), rest are holes (CW)
            if len(coords) > 0:
                coords[0] = ensure_winding_order(coords[0], 'ccw')
                for i in range(1, len(coords)):
                    coords[i] = ensure_winding_order(coords[i], 'cw')

        elif geom_type == 'MultiPolygon':
            for polygon in coords:
                if len(polygon) > 0:
                    polygon[0] = ensure_winding_order(polygon[0], 'ccw')
                    for i in range(1, len(polygon)):
                        polygon[i] = ensure_winding_order(polygon[i], 'cw')

    def _process_multipolygons(self, context: ExtractionContext) -> List[Dict[str, Any]]:
        """Extract multipolygon relations as GeoJSON features.

        Args:
            context: ExtractionContext with parsed relations

        Returns:
            List of GeoJSON Feature dicts
        """
        features = []

        # Build way lookup for assembler
        ways_by_id = {w.id: w for w in context.ways}

        # Create assembler
        assembler = MultipolygonAssembler(ways_by_id, context.node_coordinates)

        for relation in context.relations:
            if relation.tags.get('type') == 'multipolygon':
                geometry = assembler.assemble(relation)
                if geometry:
                    # Build properties from relation tags
                    properties = {
                        'id': relation.id,
                        'osm_type': 'relation',
                    }
                    # Add tags, excluding 'type' tag (it's always 'multipolygon')
                    for k, v in relation.tags.items():
                        if k != 'type':
                            properties[k] = v

                    features.append({
                        'type': 'Feature',
                        'geometry': geometry,
                        'properties': properties
                    })

        return features
