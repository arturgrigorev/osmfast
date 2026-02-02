"""OSM XML export functionality."""
from typing import Dict, Any

from osm_core.export.base import ExtractionContext, BaseExporter
from osm_core.utils.xml_utils import xml_escape


class XMLExporter(BaseExporter):
    """Export to OSM XML format."""

    def get_format_name(self) -> str:
        return 'xml'

    def export(self, context: ExtractionContext,
               output_file: str) -> Dict[str, Any]:
        """Export to OSM XML format.

        Args:
            context: ExtractionContext with parsed data
            output_file: Output file path

        Returns:
            Result dict with metadata
        """
        context.parse_and_filter()

        with open(output_file, 'w', encoding='utf-8') as f:
            # XML header
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<osm version="0.6" generator="osmfast">\n')

            # Write nodes
            for node in context.nodes:
                if node.tags:
                    f.write(f'  <node id="{node.id}" lat="{node.lat}" lon="{node.lon}">\n')
                    for k, v in node.tags.items():
                        f.write(f'    <tag k="{xml_escape(k)}" v="{xml_escape(v)}"/>\n')
                    f.write('  </node>\n')
                else:
                    f.write(f'  <node id="{node.id}" lat="{node.lat}" lon="{node.lon}"/>\n')

            # Write ways
            for way in context.ways:
                f.write(f'  <way id="{way.id}">\n')
                for node_ref in way.node_refs:
                    f.write(f'    <nd ref="{node_ref}"/>\n')
                for k, v in way.tags.items():
                    f.write(f'    <tag k="{xml_escape(k)}" v="{xml_escape(v)}"/>\n')
                f.write('  </way>\n')

            f.write('</osm>\n')

        return {
            'metadata': context.build_metadata(
                format='osm_xml',
                output_file=output_file
            )
        }


class OSMMerger:
    """Merge multiple OSM XML files."""

    @staticmethod
    def merge(input_files: list, output_file: str) -> Dict[str, Any]:
        """Merge multiple OSM files into one.

        Args:
            input_files: List of input file paths
            output_file: Output file path

        Returns:
            Metadata dictionary
        """
        import time
        import os
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        start_time = time.time()
        all_nodes = []
        all_ways = []

        # Parse all input files
        parser = UltraFastOSMParser()
        for input_file in input_files:
            if not os.path.exists(input_file):
                raise FileNotFoundError(f"Input file not found: {input_file}")

            nodes, ways = parser.parse_file_ultra_fast(input_file)
            all_nodes.extend(nodes)
            all_ways.extend(ways)

        # Remove duplicates by ID (keeping last occurrence)
        nodes_by_id = {node.id: node for node in all_nodes}
        ways_by_id = {way.id: way for way in all_ways}

        unique_nodes = list(nodes_by_id.values())
        unique_ways = list(ways_by_id.values())

        # Write merged output
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<osm version="0.6" generator="osmfast-merge">\n')

            for node in unique_nodes:
                f.write(f'  <node id="{node.id}" lat="{node.lat}" lon="{node.lon}">\n')
                for k, v in node.tags.items():
                    f.write(f'    <tag k="{xml_escape(k)}" v="{xml_escape(v)}"/>\n')
                f.write('  </node>\n')

            for way in unique_ways:
                f.write(f'  <way id="{way.id}">\n')
                for node_ref in way.node_refs:
                    f.write(f'    <nd ref="{node_ref}"/>\n')
                for k, v in way.tags.items():
                    f.write(f'    <tag k="{xml_escape(k)}" v="{xml_escape(v)}"/>\n')
                f.write('  </way>\n')

            f.write('</osm>\n')

        processing_time = time.time() - start_time
        total_elements = len(unique_nodes) + len(unique_ways)

        return {
            'metadata': {
                'input_files': input_files,
                'output_file': output_file,
                'processing_time_seconds': processing_time,
                'elements_merged': {
                    'nodes': len(unique_nodes),
                    'ways': len(unique_ways),
                    'total': total_elements
                },
                'merge_rate_elements_per_second': (
                    total_elements / processing_time if processing_time > 0 else 0
                )
            }
        }
