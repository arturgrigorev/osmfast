"""Base classes for export functionality.

Provides ExtractionContext for unified parsing/filtering and
BaseExporter abstract class for format-specific exporters.
"""
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from osm_core.models.elements import OSMNode, OSMWay, OSMRelation
    from osm_core.parsing.mmap_parser import UltraFastOSMParser
    from osm_core.filters.osm_filter import OSMFilter


class ExtractionContext:
    """Shared context for extraction operations.

    Centralizes parsing and filtering logic to eliminate duplication
    across different export methods.
    """

    def __init__(self, osm_file_path: str,
                 parser: 'UltraFastOSMParser',
                 osm_filter: 'OSMFilter',
                 include_relations: bool = False):
        """Initialize extraction context.

        Args:
            osm_file_path: Path to OSM file
            parser: Parser instance
            osm_filter: Filter instance
            include_relations: If True, also parse relations (for multipolygon support)
        """
        self.osm_file_path = osm_file_path
        self.parser = parser
        self.osm_filter = osm_filter
        self.include_relations = include_relations
        self.start_time = time.time()
        self.nodes: List['OSMNode'] = []
        self.ways: List['OSMWay'] = []
        self.relations: List['OSMRelation'] = []
        self.processing_time: float = 0.0
        self._parsed = False

    def parse_and_filter(self) -> 'ExtractionContext':
        """Parse file and apply filters.

        Returns:
            Self for method chaining
        """
        if self._parsed:
            return self

        # Parse the file
        if self.include_relations:
            self.nodes, self.ways, self.relations = self.parser.parse_file_ultra_fast(
                self.osm_file_path, include_relations=True
            )
        else:
            self.nodes, self.ways = self.parser.parse_file_ultra_fast(self.osm_file_path)

        # Apply filters if active
        if self.osm_filter.has_active_filters():
            # Filter ways first (may collect used nodes)
            self.ways = self.osm_filter.filter_ways(self.ways)
            self.nodes = self.osm_filter.filter_nodes(self.nodes)

        self.processing_time = time.time() - self.start_time
        self._parsed = True
        return self

    @property
    def node_coordinates(self) -> Dict[str, tuple]:
        """Get node coordinate cache from parser."""
        return self.parser.node_coordinates

    @property
    def total_elements(self) -> int:
        """Get total number of elements."""
        return len(self.nodes) + len(self.ways) + len(self.relations)

    def build_metadata(self, **extras) -> Dict[str, Any]:
        """Build common metadata structure.

        Args:
            **extras: Additional metadata fields

        Returns:
            Metadata dictionary
        """
        elements = {
            'nodes': len(self.nodes),
            'ways': len(self.ways),
            'total': self.total_elements
        }
        if self.relations:
            elements['relations'] = len(self.relations)

        return {
            'file_path': self.osm_file_path,
            'processing_time_seconds': self.processing_time,
            'elements': elements,
            **extras
        }


class BaseExporter(ABC):
    """Abstract base class for exporters."""

    @abstractmethod
    def export(self, context: ExtractionContext,
               output_file: str) -> Dict[str, Any]:
        """Export data to file.

        Args:
            context: ExtractionContext with parsed data
            output_file: Output file path

        Returns:
            Metadata dictionary
        """
        pass

    @abstractmethod
    def get_format_name(self) -> str:
        """Get the format name (e.g., 'json', 'geojson').

        Returns:
            Format name string
        """
        pass
