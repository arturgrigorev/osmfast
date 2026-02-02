"""
WebGL 3D map renderer.

Generates self-contained HTML files with Three.js WebGL visualization.
Buildings are rendered as 3D solid shapes with interactive tooltips.

This module provides a facade over the modular webgl/ subpackage.
"""

from typing import List, Dict, Any, Tuple

from .styles import StyleManager
from .webgl import (
    WebGLDataCollector,
    WebGLHTMLGenerator,
    WebGLSunGenerator,
    get_3d_style,
    rgb_to_hex,
)


class WebGLRenderer:
    """
    Generates interactive 3D WebGL maps using Three.js.

    Creates self-contained HTML files with 3D buildings, roads, and interactive features.
    This class provides backward-compatible API while delegating to modular components.
    """

    # Three.js CDN URLs
    THREE_JS = "https://unpkg.com/three@0.160.0/build/three.module.js"
    ORBIT_CONTROLS = "https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js"

    def __init__(self, style: str = "default"):
        """
        Initialize WebGL renderer.

        Args:
            style: Color style name (default, dark, light, blueprint)
        """
        self.style_name = style
        self.style_manager = StyleManager(style)
        self._style = get_3d_style(style)
        self._data = WebGLDataCollector(self.style_manager)

    # Data accessors (for backward compatibility)
    @property
    def buildings(self) -> List[Dict[str, Any]]:
        """Get collected buildings."""
        return self._data.buildings

    @property
    def roads(self) -> List[Dict[str, Any]]:
        """Get collected roads."""
        return self._data.roads

    @property
    def water(self) -> List[Dict[str, Any]]:
        """Get collected water features."""
        return self._data.water

    @property
    def pois(self) -> List[Dict[str, Any]]:
        """Get collected POIs."""
        return self._data.pois

    @property
    def trees(self) -> List[Dict[str, Any]]:
        """Get collected trees."""
        return self._data.trees

    @property
    def bikelanes(self) -> List[Dict[str, Any]]:
        """Get collected bike lanes."""
        return self._data.bikelanes

    @property
    def bounds(self) -> Dict[str, float]:
        """Get geographic bounds."""
        return self._data.bounds

    # Data collection methods (delegate to collector)
    def add_building(self, way: Any, node_coords: Dict[str, Tuple[float, float]]):
        """Add a building as 3D solid shape."""
        self._data.add_building(way, node_coords)

    def add_road(self, way: Any, node_coords: Dict[str, Tuple[float, float]]):
        """Add a road as a ground-level line."""
        self._data.add_road(way, node_coords)

    def add_water(self, way: Any, node_coords: Dict[str, Tuple[float, float]]):
        """Add water as a ground-level polygon."""
        self._data.add_water(way, node_coords)

    def add_poi(self, node: Any):
        """Add a POI marker."""
        self._data.add_poi(node)

    def add_tree(self, node: Any):
        """Add a tree marker."""
        self._data.add_tree(node)

    def add_bikelane(self, way: Any, node_coords: Dict[str, Tuple[float, float]]):
        """Add a bike lane as a line."""
        self._data.add_bikelane(way, node_coords)

    def generate_html(self, title: str = "OSMFast 3D Map") -> str:
        """
        Generate 3D WebGL HTML visualization.

        Args:
            title: Page title

        Returns:
            Self-contained HTML string with Three.js scene
        """
        generator = WebGLHTMLGenerator(
            data=self._data,
            style=self._style,
            style_name=self.style_name
        )
        return generator.generate(title)

    def generate_html_with_sun(self, title: str = "OSMFast Sun Study",
                                latitude: float = None) -> str:
        """
        Generate 3D WebGL HTML with sun position controls.

        Args:
            title: Page title
            latitude: Latitude for sun position calculation

        Returns:
            Self-contained HTML string with sun study controls
        """
        generator = WebGLSunGenerator(
            data=self._data,
            style=self._style,
            style_name=self.style_name
        )
        return generator.generate(title, latitude)

    def render(self, nodes: List[Any], ways: List[Any],
               node_coords: Dict[str, Tuple[float, float]],
               title: str = "OSMFast 3D Map") -> str:
        """
        Render OSM data to WebGL HTML.

        Args:
            nodes: List of OSM nodes
            ways: List of OSM ways
            node_coords: Dictionary mapping node IDs to (lat, lon)
            title: Page title

        Returns:
            HTML content as string
        """
        # Process data through collector
        self._data.process_osm_data(nodes, ways, node_coords)

        return self.generate_html(title)


# Re-export for backward compatibility
__all__ = ['WebGLRenderer', 'rgb_to_hex']
