"""High-performance pattern compilation cache.

Provides ultra-fast regex pattern caching with LRU eviction and
pre-compiled critical patterns for maximum performance.
"""
import re
from typing import Dict, Any
from collections import defaultdict


class OptimizedPatternCache:
    """Ultra-fast pattern compilation cache with intelligent management."""

    def __init__(self, max_size: int = 100):
        """Initialize cache.

        Args:
            max_size: Maximum number of cached patterns
        """
        self.max_size = max_size
        self._cache: Dict[tuple, re.Pattern] = {}
        self._usage_count: Dict[tuple, int] = defaultdict(int)
        self._compile_time_saved = 0.0

        # Pre-compile critical patterns for maximum performance
        self._precompile_critical_patterns()

    def _precompile_critical_patterns(self) -> None:
        """Pre-compile the most critical patterns for instant access."""
        critical_patterns = {
            # Node patterns - highest priority
            'node_with_tags': rb'<node\s+id="([^"]+)"\s+.*?lat="([^"]+)"\s+.*?lon="([^"]+)"[^>]*>(.*?)</node>',
            'node_self_closing': rb'<node\s+id="([^"]+)"\s+.*?lat="([^"]+)"\s+.*?lon="([^"]+)"[^>]*/\s*>',

            # Way patterns - medium priority
            'way_with_content': rb'<way\s+id="([^"]+)"[^>]*>(.*?)</way>',

            # Tag extraction - high priority
            'tags': rb'<tag\s+k="([^"]+)"\s+v="([^"]+)"[^>]*/?>',
            'node_refs': rb'<nd\s+ref="([^"]+)"[^>]*/>',

            # Semantic patterns - application specific
            'amenity_nodes': rb'<node[^>]+id="([^"]+)"[^>]+lat="([^"]+)"[^>]+lon="([^"]+)"[^>]*>.*?<tag\s+k="amenity"\s+v="([^"]+)"[^>]*/?>.*?(?:</node>|/>)',
            'highway_ways': rb'<way[^>]+id="([^"]+)"[^>]*>.*?<tag\s+k="highway"\s+v="([^"]+)"[^>]*/>.*?</way>',
            'building_ways': rb'<way[^>]+id="([^"]+)"[^>]*>.*?<tag\s+k="building"\s+v="([^"]+)"[^>]*/>.*?</way>',

            # Relation patterns - for multipolygon support
            'relation_with_content': rb'<relation\s+id="([^"]+)"[^>]*>(.*?)</relation>',
            'relation_members': rb'<member\s+type="([^"]+)"\s+ref="([^"]+)"\s+role="([^"]*)"[^>]*/>',
        }

        for name, pattern in critical_patterns.items():
            self._cache[(pattern, re.DOTALL)] = re.compile(pattern, re.DOTALL)
            self._usage_count[(pattern, re.DOTALL)] = 1000  # High initial count

    def get_pattern(self, pattern: bytes, flags: int = re.DOTALL) -> re.Pattern:
        """Get compiled pattern with ultra-fast cache lookup.

        Args:
            pattern: Raw regex pattern as bytes
            flags: Regex compilation flags

        Returns:
            Compiled regex Pattern object
        """
        cache_key = (pattern, flags)

        if cache_key in self._cache:
            self._usage_count[cache_key] += 1
            self._compile_time_saved += 0.001  # Estimated time saved
            return self._cache[cache_key]

        # Compile new pattern
        compiled = re.compile(pattern, flags)

        # Cache management - LRU eviction if needed
        if len(self._cache) >= self.max_size:
            # Remove least used pattern (but not critical ones)
            lru_key = min(self._usage_count.items(), key=lambda x: x[1])[0]
            if self._usage_count[lru_key] < 1000:  # Don't evict critical patterns
                del self._cache[lru_key]
                del self._usage_count[lru_key]

        self._cache[cache_key] = compiled
        self._usage_count[cache_key] = 1
        return compiled

    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics.

        Returns:
            Dict with cache statistics
        """
        total_usage = sum(self._usage_count.values())
        return {
            'cached_patterns': len(self._cache),
            'total_usage': total_usage,
            'compile_time_saved': self._compile_time_saved,
            'hit_rate': ((total_usage - len(self._cache)) / max(total_usage, 1)) * 100,
            'critical_patterns_cached': len([k for k, v in self._usage_count.items() if v >= 1000])
        }

    def clear(self) -> None:
        """Clear all cached patterns and re-initialize critical patterns."""
        self._cache.clear()
        self._usage_count.clear()
        self._compile_time_saved = 0.0
        self._precompile_critical_patterns()
