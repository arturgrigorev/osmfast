"""Ultra-fast OSM parser using memory-mapped I/O.

Provides high-performance parsing of OSM XML files using memory mapping
and pre-compiled regex patterns.
"""
import mmap
import time
from typing import Dict, List, Tuple, Iterator, Any

from typing import Optional, Union
from osm_core.models.elements import OSMNode, OSMWay, OSMRelation
from osm_core.parsing.pattern_cache import OptimizedPatternCache


class UltraFastOSMParser:
    """Ultra-high performance OSM parser using memory-mapping + cached patterns."""

    def __init__(self):
        """Initialize parser with pattern cache."""
        self.pattern_cache = OptimizedPatternCache()

        # Performance statistics
        self.stats = {
            'bytes_processed': 0,
            'elements_parsed': 0,
            'tags_extracted': 0,
            'parsing_time': 0,
            'memory_mapped_time': 0,
            'cache_hits': 0
        }

        # Coordinate cache for way geometry reconstruction
        self.node_coordinates: Dict[str, Tuple[float, float]] = {}

    def extract_tags(self, element_content: bytes) -> Dict[str, str]:
        """Ultra-fast tag extraction using cached patterns.

        Args:
            element_content: Raw bytes of element content

        Returns:
            Dict of tag key-value pairs
        """
        tags = {}
        tag_pattern = self.pattern_cache.get_pattern(
            rb'<tag\s+k="([^"]+)"\s+v="([^"]+)"[^>]*/?>'
        )

        for match in tag_pattern.finditer(element_content):
            try:
                key = match.group(1).decode('utf-8')
                value = match.group(2).decode('utf-8')
                tags[key] = value
                self.stats['tags_extracted'] += 1
            except UnicodeDecodeError:
                continue

        return tags

    def extract_node_refs(self, way_content: bytes) -> List[str]:
        """Ultra-fast node reference extraction.

        Args:
            way_content: Raw bytes of way content

        Returns:
            List of node reference IDs
        """
        node_refs = []
        ref_pattern = self.pattern_cache.get_pattern(
            rb'<nd\s+ref="([^"]+)"[^>]*/>'
        )

        for match in ref_pattern.finditer(way_content):
            try:
                node_refs.append(match.group(1).decode('utf-8'))
            except UnicodeDecodeError:
                continue

        return node_refs

    def parse_nodes_ultra_fast(self, mmap_data: mmap.mmap) -> Iterator[OSMNode]:
        """Ultra-fast node parsing using memory-mapped data.

        Args:
            mmap_data: Memory-mapped file data

        Yields:
            OSMNode objects with tags
        """
        # Match node opening tags - captures id, lat, lon and determines if self-closing
        # Using [^<>]*? (non-greedy) to stay within the opening tag only
        node_pattern = self.pattern_cache.get_pattern(
            rb'<node\s+id="([^"]+)"[^<>]*?lat="([^"]+)"[^<>]*?lon="([^"]+)"[^<>]*?(/>|>)'
        )

        # Pattern for finding </node> closing tag
        close_pattern = self.pattern_cache.get_pattern(rb'</node>')

        for match in node_pattern.finditer(mmap_data):
            try:
                node_id = match.group(1).decode('utf-8')
                lat = float(match.group(2).decode('utf-8'))
                lon = float(match.group(3).decode('utf-8'))
                is_self_closing = match.group(4) == b'/>'

                # Cache coordinates for way processing
                self.node_coordinates[node_id] = (lat, lon)

                # Extract tags
                if is_self_closing:
                    # Self-closing node - tags are in the element itself (rare)
                    tags = self.extract_tags(match.group(0))
                else:
                    # Complex node - find content until </node>
                    end_pos = match.end()
                    close_match = close_pattern.search(mmap_data, end_pos)
                    if close_match:
                        content = mmap_data[end_pos:close_match.start()]
                        tags = self.extract_tags(content)
                    else:
                        tags = {}

                if tags:  # Only yield nodes with tags
                    yield OSMNode(id=node_id, lat=lat, lon=lon, tags=tags)
                    self.stats['elements_parsed'] += 1

            except (ValueError, UnicodeDecodeError):
                continue

    def parse_ways_ultra_fast(self, mmap_data: mmap.mmap) -> Iterator[OSMWay]:
        """Ultra-fast way parsing using memory-mapped data.

        Args:
            mmap_data: Memory-mapped file data

        Yields:
            OSMWay objects with tags and node references
        """
        way_pattern = self.pattern_cache.get_pattern(
            rb'<way\s+id="([^"]+)"[^>]*>(.*?)</way>'
        )

        for match in way_pattern.finditer(mmap_data):
            try:
                way_id = match.group(1).decode('utf-8')
                way_content = match.group(2)

                # Extract node references
                node_refs = self.extract_node_refs(way_content)

                # Extract tags
                tags = self.extract_tags(way_content)

                if tags and node_refs:  # Only yield ways with tags and nodes
                    yield OSMWay(id=way_id, node_refs=node_refs, tags=tags)
                    self.stats['elements_parsed'] += 1

            except UnicodeDecodeError:
                continue

    def extract_members(self, relation_content: bytes) -> List[Dict[str, str]]:
        """Extract member references from relation content.

        Args:
            relation_content: Raw bytes of relation content

        Returns:
            List of member dicts with 'type', 'ref', and 'role' keys
        """
        members = []
        member_pattern = self.pattern_cache.get_pattern(
            rb'<member\s+type="([^"]+)"\s+ref="([^"]+)"\s+role="([^"]*)"[^>]*/>'
        )

        for match in member_pattern.finditer(relation_content):
            try:
                members.append({
                    'type': match.group(1).decode('utf-8'),
                    'ref': match.group(2).decode('utf-8'),
                    'role': match.group(3).decode('utf-8')
                })
            except UnicodeDecodeError:
                continue

        return members

    def parse_relations_ultra_fast(self, mmap_data: mmap.mmap) -> Iterator[OSMRelation]:
        """Ultra-fast relation parsing using memory-mapped data.

        Args:
            mmap_data: Memory-mapped file data

        Yields:
            OSMRelation objects with members and tags
        """
        relation_pattern = self.pattern_cache.get_pattern(
            rb'<relation\s+id="([^"]+)"[^>]*>(.*?)</relation>'
        )

        for match in relation_pattern.finditer(mmap_data):
            try:
                relation_id = match.group(1).decode('utf-8')
                relation_content = match.group(2)

                # Extract members
                members = self.extract_members(relation_content)

                # Extract tags
                tags = self.extract_tags(relation_content)

                if tags and members:  # Only yield relations with tags and members
                    yield OSMRelation(id=relation_id, members=members, tags=tags)
                    self.stats['elements_parsed'] += 1

            except UnicodeDecodeError:
                continue

    def parse_file_ultra_fast(
        self,
        file_path: str,
        include_relations: bool = False
    ) -> Union[Tuple[List[OSMNode], List[OSMWay]],
               Tuple[List[OSMNode], List[OSMWay], List[OSMRelation]]]:
        """Ultra-fast complete file parsing.

        Args:
            file_path: Path to OSM XML file
            include_relations: If True, also parse relations

        Returns:
            Tuple of (nodes, ways) or (nodes, ways, relations) if include_relations
        """
        start_time = time.time()

        nodes = []
        ways = []
        relations = []

        with open(file_path, 'rb') as f:
            mmap_start = time.time()
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                self.stats['memory_mapped_time'] = time.time() - mmap_start
                self.stats['bytes_processed'] = len(mm)

                # Parse all nodes
                for node in self.parse_nodes_ultra_fast(mm):
                    nodes.append(node)

                # Parse all ways
                for way in self.parse_ways_ultra_fast(mm):
                    ways.append(way)

                # Parse relations if requested
                if include_relations:
                    for relation in self.parse_relations_ultra_fast(mm):
                        relations.append(relation)

        self.stats['parsing_time'] = time.time() - start_time

        if include_relations:
            return nodes, ways, relations
        return nodes, ways

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics.

        Returns:
            Dict with performance metrics
        """
        cache_stats = self.pattern_cache.get_stats()

        processing_rate = (self.stats['elements_parsed'] /
                           max(self.stats['parsing_time'], 0.001))

        return {
            'elements_parsed': self.stats['elements_parsed'],
            'processing_rate_elem_per_sec': processing_rate,
            'bytes_processed': self.stats['bytes_processed'],
            'parsing_time': self.stats['parsing_time'],
            'memory_mapped_time': self.stats['memory_mapped_time'],
            'tags_extracted': self.stats['tags_extracted'],
            'nodes_cached_for_geometry': len(self.node_coordinates),
            'pattern_cache_stats': cache_stats,
            'performance_class': 'ultra_fast'
        }

    def reset_stats(self) -> None:
        """Reset all statistics."""
        self.stats = {
            'bytes_processed': 0,
            'elements_parsed': 0,
            'tags_extracted': 0,
            'parsing_time': 0,
            'memory_mapped_time': 0,
            'cache_hits': 0
        }
        self.node_coordinates.clear()
