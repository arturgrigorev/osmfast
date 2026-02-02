"""
OSMFast rendering module.

Provides map visualization capabilities:
- PNG rendering (pure Python, zero dependencies)
- PDF rendering (publication-ready, no Type 3 fonts)
- Leaflet HTML generation (interactive browser maps)
- WebGL 3D rendering (buildings as 3D shapes)
"""

from .styles import StyleManager, get_available_styles, Color, color_to_css
from .png_renderer import PNGRenderer, GeoTransform, MapRenderer
from .pdf_renderer import PDFRenderer, GeoTransformPDF, MapPDFRenderer
from .leaflet_renderer import LeafletRenderer
from .webgl_renderer import WebGLRenderer

# WebGL submodule components (for advanced usage)
from .webgl import (
    WebGLDataCollector,
    WebGLHTMLGenerator,
    WebGLSunGenerator,
    WebGL3DStyle,
    STYLE_PRESETS,
    get_3d_style,
)

__all__ = [
    # Styles
    'StyleManager',
    'get_available_styles',
    'Color',
    'color_to_css',
    # PNG
    'PNGRenderer',
    'GeoTransform',
    'MapRenderer',
    # PDF
    'PDFRenderer',
    'GeoTransformPDF',
    'MapPDFRenderer',
    # Leaflet
    'LeafletRenderer',
    # WebGL
    'WebGLRenderer',
    'WebGLDataCollector',
    'WebGLHTMLGenerator',
    'WebGLSunGenerator',
    'WebGL3DStyle',
    'STYLE_PRESETS',
    'get_3d_style',
]
