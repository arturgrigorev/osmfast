"""CSV export functionality."""
import csv
from typing import Dict, Any, List, Set

from osm_core.export.base import ExtractionContext, BaseExporter


class CSVExporter(BaseExporter):
    """Export to CSV format."""

    def __init__(self, include_metadata: bool = False):
        """Initialize CSV exporter.

        Args:
            include_metadata: Include metadata columns
        """
        self.include_metadata = include_metadata

    def get_format_name(self) -> str:
        return 'csv'

    def export(self, context: ExtractionContext,
               output_file: str) -> Dict[str, Any]:
        """Export to CSV format.

        Args:
            context: ExtractionContext with parsed data
            output_file: Output file path

        Returns:
            Result dict with metadata
        """
        context.parse_and_filter()

        # Collect all unique columns
        all_columns: Set[str] = {'id', 'type', 'lat', 'lon'}

        # Build rows
        rows: List[Dict[str, Any]] = []

        # Add nodes
        for node in context.nodes:
            row = {
                'id': node.id,
                'type': 'node',
                'lat': node.lat,
                'lon': node.lon
            }
            row.update(node.tags)
            all_columns.update(node.tags.keys())

            if self.include_metadata:
                row['has_tags'] = str(bool(node.tags))
                row['tag_count'] = len(node.tags)

            rows.append(row)

        # Add ways
        for way in context.ways:
            # Calculate center point if coordinates available
            coords = []
            for node_id in way.node_refs:
                if node_id in context.node_coordinates:
                    coords.append(context.node_coordinates[node_id])

            if coords:
                center_lat = sum(c[0] for c in coords) / len(coords)
                center_lon = sum(c[1] for c in coords) / len(coords)
            else:
                center_lat = center_lon = None

            row = {
                'id': way.id,
                'type': 'way',
                'lat': center_lat,
                'lon': center_lon
            }
            row.update(way.tags)
            all_columns.update(way.tags.keys())

            if self.include_metadata:
                row['has_tags'] = str(bool(way.tags))
                row['tag_count'] = len(way.tags)
                row['node_count'] = len(way.node_refs)
                row['is_closed'] = str(way.is_closed)

            rows.append(row)

        # Order columns: primary, then tags, then metadata
        primary_cols = ['id', 'type', 'lat', 'lon']
        tag_cols = sorted([
            col for col in all_columns
            if col not in primary_cols
            and not col.startswith('element_')
            and col not in ['has_tags', 'tag_count', 'node_count', 'is_closed']
        ])

        if self.include_metadata:
            metadata_cols = ['has_tags', 'tag_count', 'node_count', 'is_closed']
            all_columns.update(metadata_cols)
        else:
            metadata_cols = []

        ordered_columns = (
            primary_cols +
            tag_cols +
            [col for col in metadata_cols if col in all_columns]
        )

        # Write CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=ordered_columns,
                                    extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)

        return {
            'metadata': context.build_metadata(
                format='csv',
                columns=len(ordered_columns),
                rows=len(rows),
                include_metadata=self.include_metadata
            )
        }
