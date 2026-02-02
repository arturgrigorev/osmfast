"""
WebGL 3D rendering submodule.

Provides modular components for generating WebGL 3D map visualizations:
- data_collector: OSM data aggregation for 3D rendering
- styles: 3D style presets and color management
- html_generator: Standard 3D HTML generation
- sun_generator: Sun study HTML with shadows
"""

from .data_collector import WebGLDataCollector
from .styles import (
    WebGL3DStyle,
    STYLE_PRESETS,
    get_3d_style,
    estimate_building_height,
    generate_road_colors_js,
    rgb_to_hex,
)
from .html_generator import WebGLHTMLGenerator
from .sun_generator import WebGLSunGenerator

__all__ = [
    'WebGLDataCollector',
    'WebGL3DStyle',
    'STYLE_PRESETS',
    'get_3d_style',
    'estimate_building_height',
    'generate_road_colors_js',
    'rgb_to_hex',
    'WebGLHTMLGenerator',
    'WebGLSunGenerator',
]
