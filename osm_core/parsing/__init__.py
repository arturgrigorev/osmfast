"""High-performance OSM parsing modules."""

from osm_core.parsing.mmap_parser import UltraFastOSMParser
from osm_core.parsing.pattern_cache import OptimizedPatternCache

__all__ = ['UltraFastOSMParser', 'OptimizedPatternCache']
