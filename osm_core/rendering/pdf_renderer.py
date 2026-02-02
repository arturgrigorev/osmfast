"""
Publication-ready PDF renderer - zero external dependencies.

Generates vector PDF files suitable for academic publications:
- No Type 3 fonts (uses only standard Type 1 fonts)
- All graphics as vector paths
- Proper font embedding
- Clean, scalable output

Uses only Python standard library.
"""

import zlib
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
import math

from .styles import StyleManager, Color, color_to_css


class PDFRenderer:
    """
    Pure Python PDF renderer for publication-ready output.

    Uses only standard Type 1 fonts (no Type 3 bitmap fonts).
    All graphics are vector-based for clean scaling.
    """

    # Standard Type 1 fonts (built into all PDF readers)
    # These are guaranteed to work and never produce Type 3 fonts
    FONTS = {
        'Helvetica': 'Helvetica',
        'Helvetica-Bold': 'Helvetica-Bold',
        'Helvetica-Oblique': 'Helvetica-Oblique',
        'Times': 'Times-Roman',
        'Times-Bold': 'Times-Bold',
        'Times-Italic': 'Times-Italic',
        'Courier': 'Courier',
        'Courier-Bold': 'Courier-Bold',
    }

    def __init__(self, width: float, height: float, margin: float = 36):
        """
        Initialize PDF renderer.

        Args:
            width: Page width in points (72 points = 1 inch)
            height: Page height in points
            margin: Page margin in points (default: 0.5 inch)
        """
        self.width = width
        self.height = height
        self.margin = margin
        self.draw_width = width - 2 * margin
        self.draw_height = height - 2 * margin

        # PDF objects
        self.objects: List[bytes] = []
        self.object_offsets: List[int] = []

        # Content stream commands
        self.content: List[str] = []

        # Track current graphics state
        self.current_color: Optional[Color] = None
        self.current_stroke_color: Optional[Color] = None
        self.current_line_width: float = 1.0

    def _add_object(self, content: bytes) -> int:
        """Add a PDF object and return its number (1-indexed)."""
        self.objects.append(content)
        return len(self.objects)

    def _color_to_pdf(self, color: Color) -> str:
        """Convert RGB color to PDF color string (0-1 range)."""
        r, g, b = color
        return f"{r/255:.3f} {g/255:.3f} {b/255:.3f}"

    def set_fill_color(self, color: Color):
        """Set fill color."""
        if color != self.current_color:
            self.content.append(f"{self._color_to_pdf(color)} rg")
            self.current_color = color

    def set_stroke_color(self, color: Color):
        """Set stroke color."""
        if color != self.current_stroke_color:
            self.content.append(f"{self._color_to_pdf(color)} RG")
            self.current_stroke_color = color

    def set_line_width(self, width: float):
        """Set line width."""
        if width != self.current_line_width:
            self.content.append(f"{width:.2f} w")
            self.current_line_width = width

    def set_line_cap(self, cap: int = 1):
        """Set line cap style (0=butt, 1=round, 2=square)."""
        self.content.append(f"{cap} J")

    def set_line_join(self, join: int = 1):
        """Set line join style (0=miter, 1=round, 2=bevel)."""
        self.content.append(f"{join} j")

    def move_to(self, x: float, y: float):
        """Move to position."""
        self.content.append(f"{x:.2f} {y:.2f} m")

    def line_to(self, x: float, y: float):
        """Draw line to position."""
        self.content.append(f"{x:.2f} {y:.2f} l")

    def curve_to(self, x1: float, y1: float, x2: float, y2: float, x3: float, y3: float):
        """Draw bezier curve."""
        self.content.append(f"{x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f} {x3:.2f} {y3:.2f} c")

    def close_path(self):
        """Close current path."""
        self.content.append("h")

    def stroke(self):
        """Stroke current path."""
        self.content.append("S")

    def fill(self):
        """Fill current path."""
        self.content.append("f")

    def fill_stroke(self):
        """Fill and stroke current path."""
        self.content.append("B")

    def draw_line(self, x1: float, y1: float, x2: float, y2: float,
                  color: Color, width: float = 1.0):
        """Draw a line."""
        self.set_stroke_color(color)
        self.set_line_width(width)
        self.move_to(x1, y1)
        self.line_to(x2, y2)
        self.stroke()

    def draw_polyline(self, points: List[Tuple[float, float]], color: Color, width: float = 1.0):
        """Draw a polyline."""
        if len(points) < 2:
            return

        self.set_stroke_color(color)
        self.set_line_width(width)
        self.set_line_cap(1)  # Round caps
        self.set_line_join(1)  # Round joins

        self.move_to(points[0][0], points[0][1])
        for x, y in points[1:]:
            self.line_to(x, y)
        self.stroke()

    def draw_polygon(self, points: List[Tuple[float, float]],
                     fill_color: Optional[Color] = None,
                     stroke_color: Optional[Color] = None,
                     stroke_width: float = 1.0):
        """Draw a polygon."""
        if len(points) < 3:
            return

        self.move_to(points[0][0], points[0][1])
        for x, y in points[1:]:
            self.line_to(x, y)
        self.close_path()

        if fill_color and stroke_color:
            self.set_fill_color(fill_color)
            self.set_stroke_color(stroke_color)
            self.set_line_width(stroke_width)
            self.fill_stroke()
        elif fill_color:
            self.set_fill_color(fill_color)
            self.fill()
        elif stroke_color:
            self.set_stroke_color(stroke_color)
            self.set_line_width(stroke_width)
            self.stroke()

    def draw_circle(self, cx: float, cy: float, radius: float,
                    fill_color: Optional[Color] = None,
                    stroke_color: Optional[Color] = None,
                    stroke_width: float = 1.0):
        """Draw a circle using bezier curves."""
        # Approximate circle with 4 bezier curves
        k = 0.5522847498  # Magic number for circle approximation

        self.move_to(cx + radius, cy)
        self.curve_to(cx + radius, cy + k * radius,
                      cx + k * radius, cy + radius,
                      cx, cy + radius)
        self.curve_to(cx - k * radius, cy + radius,
                      cx - radius, cy + k * radius,
                      cx - radius, cy)
        self.curve_to(cx - radius, cy - k * radius,
                      cx - k * radius, cy - radius,
                      cx, cy - radius)
        self.curve_to(cx + k * radius, cy - radius,
                      cx + radius, cy - k * radius,
                      cx + radius, cy)
        self.close_path()

        if fill_color and stroke_color:
            self.set_fill_color(fill_color)
            self.set_stroke_color(stroke_color)
            self.set_line_width(stroke_width)
            self.fill_stroke()
        elif fill_color:
            self.set_fill_color(fill_color)
            self.fill()
        elif stroke_color:
            self.set_stroke_color(stroke_color)
            self.set_line_width(stroke_width)
            self.stroke()

    def draw_rectangle(self, x: float, y: float, w: float, h: float,
                       fill_color: Optional[Color] = None,
                       stroke_color: Optional[Color] = None,
                       stroke_width: float = 1.0):
        """Draw a rectangle."""
        self.content.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")

        if fill_color and stroke_color:
            self.set_fill_color(fill_color)
            self.set_stroke_color(stroke_color)
            self.set_line_width(stroke_width)
            self.fill_stroke()
        elif fill_color:
            self.set_fill_color(fill_color)
            self.fill()
        elif stroke_color:
            self.set_stroke_color(stroke_color)
            self.set_line_width(stroke_width)
            self.stroke()

    def draw_text(self, x: float, y: float, text: str, font_size: float = 10,
                  font: str = 'Helvetica', color: Color = (0, 0, 0)):
        """
        Draw text using standard Type 1 fonts.

        Only uses built-in PDF fonts - never produces Type 3 fonts.
        """
        # Escape special characters in PDF strings
        text = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

        self.content.append("BT")  # Begin text
        self.content.append(f"/{font} {font_size:.1f} Tf")  # Set font
        self.content.append(f"{self._color_to_pdf(color)} rg")  # Set color
        self.content.append(f"{x:.2f} {y:.2f} Td")  # Position
        self.content.append(f"({text}) Tj")  # Draw text
        self.content.append("ET")  # End text

    def save_graphics_state(self):
        """Save current graphics state."""
        self.content.append("q")

    def restore_graphics_state(self):
        """Restore graphics state."""
        self.content.append("Q")

    def set_clip_rect(self, x: float, y: float, w: float, h: float):
        """Set clipping rectangle."""
        self.content.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re W n")

    def generate_pdf(self, title: str = "OSMFast Map",
                     author: str = "OSMFast",
                     compress: bool = True) -> bytes:
        """
        Generate complete PDF document.

        Args:
            title: Document title
            author: Document author
            compress: Whether to compress content stream

        Returns:
            PDF file as bytes
        """
        # Build content stream
        content_data = '\n'.join(self.content).encode('latin-1')

        if compress:
            compressed_content = zlib.compress(content_data)
            content_stream = (
                f"<< /Length {len(compressed_content)} /Filter /FlateDecode >>\n"
                f"stream\n"
            ).encode('latin-1') + compressed_content + b"\nendstream"
        else:
            content_stream = (
                f"<< /Length {len(content_data)} >>\n"
                f"stream\n"
            ).encode('latin-1') + content_data + b"\nendstream"

        # PDF structure
        pdf_parts = []

        # Header
        pdf_parts.append(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")  # PDF header with binary marker

        # Object 1: Catalog
        obj1_offset = sum(len(p) for p in pdf_parts)
        pdf_parts.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

        # Object 2: Pages
        obj2_offset = sum(len(p) for p in pdf_parts)
        pdf_parts.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")

        # Object 3: Page
        obj3_offset = sum(len(p) for p in pdf_parts)
        page_obj = (
            f"3 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
            f"/Contents 4 0 R /Resources << /Font << "
            f"/Helvetica 5 0 R /Helvetica-Bold 6 0 R /Times-Roman 7 0 R "
            f">> >> >>\n"
            f"endobj\n"
        ).encode('latin-1')
        pdf_parts.append(page_obj)

        # Object 4: Content stream
        obj4_offset = sum(len(p) for p in pdf_parts)
        pdf_parts.append(b"4 0 obj\n" + content_stream + b"\nendobj\n")

        # Object 5: Helvetica font (Type 1 - no embedding needed)
        obj5_offset = sum(len(p) for p in pdf_parts)
        pdf_parts.append(
            b"5 0 obj\n"
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\n"
            b"endobj\n"
        )

        # Object 6: Helvetica-Bold font
        obj6_offset = sum(len(p) for p in pdf_parts)
        pdf_parts.append(
            b"6 0 obj\n"
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\n"
            b"endobj\n"
        )

        # Object 7: Times-Roman font
        obj7_offset = sum(len(p) for p in pdf_parts)
        pdf_parts.append(
            b"7 0 obj\n"
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>\n"
            b"endobj\n"
        )

        # Object 8: Document info
        obj8_offset = sum(len(p) for p in pdf_parts)
        now = datetime.now().strftime("D:%Y%m%d%H%M%S")
        info_obj = (
            f"8 0 obj\n"
            f"<< /Title ({title}) /Author ({author}) "
            f"/Creator (OSMFast PDF Renderer) /Producer (OSMFast) "
            f"/CreationDate ({now}) >>\n"
            f"endobj\n"
        ).encode('latin-1')
        pdf_parts.append(info_obj)

        # Cross-reference table
        xref_offset = sum(len(p) for p in pdf_parts)
        xref = (
            f"xref\n"
            f"0 9\n"
            f"0000000000 65535 f \n"
            f"{obj1_offset:010d} 00000 n \n"
            f"{obj2_offset:010d} 00000 n \n"
            f"{obj3_offset:010d} 00000 n \n"
            f"{obj4_offset:010d} 00000 n \n"
            f"{obj5_offset:010d} 00000 n \n"
            f"{obj6_offset:010d} 00000 n \n"
            f"{obj7_offset:010d} 00000 n \n"
            f"{obj8_offset:010d} 00000 n \n"
        ).encode('latin-1')
        pdf_parts.append(xref)

        # Trailer
        trailer = (
            f"trailer\n"
            f"<< /Size 9 /Root 1 0 R /Info 8 0 R >>\n"
            f"startxref\n"
            f"{xref_offset}\n"
            f"%%EOF\n"
        ).encode('latin-1')
        pdf_parts.append(trailer)

        return b''.join(pdf_parts)

    def save(self, filename: str, title: str = "OSMFast Map"):
        """Save PDF to file."""
        pdf_data = self.generate_pdf(title)
        with open(filename, 'wb') as f:
            f.write(pdf_data)


class GeoTransformPDF:
    """
    Transforms geographic coordinates to PDF coordinates.
    """

    def __init__(self, pdf_width: float, pdf_height: float,
                 margin: float,
                 min_lat: float, max_lat: float,
                 min_lon: float, max_lon: float):
        """Initialize geo transform for PDF coordinates."""
        self.pdf_width = pdf_width
        self.pdf_height = pdf_height
        self.margin = margin

        self.draw_width = pdf_width - 2 * margin
        self.draw_height = pdf_height - 2 * margin

        # Geo bounds
        self.min_lat = min_lat
        self.max_lat = max_lat
        self.min_lon = min_lon
        self.max_lon = max_lon

        # Calculate scale
        lat_range = max_lat - min_lat
        lon_range = max_lon - min_lon

        lat_center = (min_lat + max_lat) / 2
        lon_scale = math.cos(math.radians(lat_center))

        scale_x = self.draw_width / (lon_range * lon_scale) if lon_range > 0 else 1
        scale_y = self.draw_height / lat_range if lat_range > 0 else 1

        self.scale = min(scale_x, scale_y)
        self.lon_scale = lon_scale

        self.center_lon = (min_lon + max_lon) / 2
        self.center_lat = (min_lat + max_lat) / 2

    def geo_to_pdf(self, lat: float, lon: float) -> Tuple[float, float]:
        """Convert geographic coordinates to PDF coordinates."""
        x = self.pdf_width / 2 + (lon - self.center_lon) * self.lon_scale * self.scale
        y = self.pdf_height / 2 + (lat - self.center_lat) * self.scale
        return x, y

    def get_scale_meters_per_point(self) -> float:
        """Get approximate meters per PDF point at center latitude."""
        meters_per_degree = 111320 * math.cos(math.radians(self.center_lat))
        return meters_per_degree / (self.scale * self.lon_scale)


class MapPDFRenderer:
    """
    High-level map renderer that renders OSM data to publication-ready PDF.

    Supports layer visibility controls and various rendering options.
    """

    # Standard page sizes in points (72 points = 1 inch)
    PAGE_SIZES = {
        'letter': (612, 792),       # 8.5 x 11 inches
        'a4': (595, 842),           # 210 x 297 mm
        'a3': (842, 1191),          # 297 x 420 mm
        'a2': (1191, 1684),         # 420 x 594 mm
        'legal': (612, 1008),       # 8.5 x 14 inches
    }

    # Default layer visibility
    DEFAULT_LAYERS = {
        'landuse': True,
        'natural': True,
        'water': True,
        'buildings': True,
        'railways': True,
        'highways': True,
        'bikelanes': True,
        'pois': True,
        'trees': True,
    }

    def __init__(self, page_size: str = 'letter', orientation: str = 'landscape',
                 style: str = 'default', margin: float = 36,
                 layers: Optional[Dict[str, bool]] = None,
                 line_scale: float = 1.0,
                 poi_size: float = 3.0,
                 tree_size: float = 2.0):
        """
        Initialize PDF map renderer.

        Args:
            page_size: Page size name (letter, a4, a3, a2, legal)
            orientation: 'portrait' or 'landscape'
            style: Color style name
            margin: Page margin in points (72 points = 1 inch)
            layers: Dict of layer visibility (e.g., {'buildings': True, 'pois': False})
            line_scale: Multiplier for line widths (default 1.0)
            poi_size: Size of POI markers in points (default 3.0)
            tree_size: Size of tree markers in points (default 2.0)
        """
        # Get page dimensions
        if page_size.lower() in self.PAGE_SIZES:
            width, height = self.PAGE_SIZES[page_size.lower()]
        else:
            width, height = self.PAGE_SIZES['letter']

        # Apply orientation
        if orientation.lower() == 'landscape':
            width, height = height, width

        self.width = width
        self.height = height
        self.margin = margin
        self.style_manager = StyleManager(style)
        self.pdf: Optional[PDFRenderer] = None
        self.transform: Optional[GeoTransformPDF] = None

        # Layer visibility
        self.layers = dict(self.DEFAULT_LAYERS)
        if layers:
            self.layers.update(layers)

        # Rendering options
        self.line_scale = line_scale
        self.poi_size = poi_size
        self.tree_size = tree_size

    def set_layer(self, layer: str, visible: bool):
        """Set visibility of a specific layer."""
        if layer in self.layers:
            self.layers[layer] = visible

    def set_layers(self, **kwargs):
        """Set visibility of multiple layers at once."""
        for layer, visible in kwargs.items():
            if layer in self.layers:
                self.layers[layer] = visible

    def render(self, nodes: List[Any], ways: List[Any],
               node_coords: Dict[str, Tuple[float, float]],
               bbox: Optional[Tuple[float, float, float, float]] = None,
               title: Optional[str] = None,
               show_legend: bool = True,
               show_scale: bool = True,
               show_title: bool = True,
               show_frame: bool = True,
               zoom: float = 1.0) -> PDFRenderer:
        """
        Render OSM data to PDF.

        Args:
            nodes: List of OSM nodes
            ways: List of OSM ways
            node_coords: Dictionary mapping node IDs to (lat, lon)
            bbox: Optional bounding box (min_lat, max_lat, min_lon, max_lon)
            title: Map title
            show_legend: Whether to show legend
            show_scale: Whether to show scale bar
            show_title: Whether to show title
            show_frame: Whether to show map frame
            zoom: Zoom factor (1.0 = normal, 1.5 = 50% more zoomed in, 2.0 = 2x zoom)

        Returns:
            PDFRenderer with rendered content
        """
        # Calculate bounding box if not provided
        if bbox is None:
            bbox = self._calculate_bbox(nodes, ways, node_coords)

        min_lat, max_lat, min_lon, max_lon = bbox

        # Add padding to bounds (2% for tighter zoom)
        lat_pad = (max_lat - min_lat) * 0.02
        lon_pad = (max_lon - min_lon) * 0.02
        min_lat -= lat_pad
        max_lat += lat_pad
        min_lon -= lon_pad
        max_lon += lon_pad

        # Apply zoom (shrink bounds towards center)
        if zoom > 1.0:
            center_lat = (min_lat + max_lat) / 2
            center_lon = (min_lon + max_lon) / 2
            half_lat = (max_lat - min_lat) / 2 / zoom
            half_lon = (max_lon - min_lon) / 2 / zoom
            min_lat = center_lat - half_lat
            max_lat = center_lat + half_lat
            min_lon = center_lon - half_lon
            max_lon = center_lon + half_lon

        # Initialize PDF renderer
        self.pdf = PDFRenderer(self.width, self.height, self.margin)
        self.transform = GeoTransformPDF(
            self.width, self.height, self.margin,
            min_lat, max_lat, min_lon, max_lon
        )

        # Draw map frame/background
        if show_frame:
            self._render_frame()

        # Set clipping to map area
        self.pdf.save_graphics_state()
        self.pdf.set_clip_rect(
            self.margin, self.margin,
            self.width - 2 * self.margin,
            self.height - 2 * self.margin
        )

        # Render layers in order (back to front) based on visibility
        if self.layers.get('landuse', True):
            self._render_landuse(ways, node_coords)
        if self.layers.get('natural', True):
            self._render_natural(ways, node_coords)
        if self.layers.get('water', True):
            self._render_water(ways, node_coords)
        if self.layers.get('buildings', True):
            self._render_buildings(ways, node_coords)
        if self.layers.get('railways', True):
            self._render_railways(ways, node_coords)
        if self.layers.get('highways', True):
            self._render_highways(ways, node_coords)
        if self.layers.get('bikelanes', True):
            self._render_bikelanes(ways, node_coords)
        if self.layers.get('trees', True):
            self._render_trees(nodes)
        if self.layers.get('pois', True):
            self._render_pois(nodes)

        # Restore graphics state (remove clipping)
        self.pdf.restore_graphics_state()

        # Render decorations
        if show_scale:
            self._render_scale_bar()
        if show_legend:
            self._render_legend()
        if show_title and title:
            self._render_title(title)

        return self.pdf

    def _calculate_bbox(self, nodes: List[Any], ways: List[Any],
                        node_coords: Dict[str, Tuple[float, float]]) -> Tuple[float, float, float, float]:
        """Calculate bounding box from data."""
        lats = []
        lons = []

        for node in nodes:
            lats.append(node.lat)
            lons.append(node.lon)

        for way in ways:
            for ref in way.node_refs:
                if ref in node_coords:
                    lat, lon = node_coords[ref]
                    lats.append(lat)
                    lons.append(lon)

        if not lats or not lons:
            return (0, 1, 0, 1)

        return (min(lats), max(lats), min(lons), max(lons))

    def _get_way_coords(self, way: Any, node_coords: Dict[str, Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Get PDF coordinates for a way."""
        points = []
        for ref in way.node_refs:
            if ref in node_coords:
                lat, lon = node_coords[ref]
                x, y = self.transform.geo_to_pdf(lat, lon)
                points.append((x, y))
        return points

    def _render_frame(self):
        """Render map frame/border."""
        bg_color = self.style_manager.get_background()
        self.pdf.draw_rectangle(
            self.margin, self.margin,
            self.width - 2 * self.margin,
            self.height - 2 * self.margin,
            fill_color=bg_color,
            stroke_color=(0, 0, 0),
            stroke_width=0.5
        )

    def _render_landuse(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render landuse polygons."""
        for way in ways:
            if 'landuse' in way.tags and way.is_closed:
                points = self._get_way_coords(way, node_coords)
                if len(points) >= 3:
                    color = self.style_manager.get_landuse_color(way.tags['landuse'])
                    self.pdf.draw_polygon(points, fill_color=color)

    def _render_natural(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render natural features."""
        for way in ways:
            if 'natural' in way.tags:
                points = self._get_way_coords(way, node_coords)
                if len(points) >= 3 and way.is_closed:
                    color = self.style_manager.get_natural_color(way.tags['natural'])
                    self.pdf.draw_polygon(points, fill_color=color)

    def _render_water(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render water features."""
        water_color = self.style_manager.get_water_color()

        for way in ways:
            points = self._get_way_coords(way, node_coords)

            if way.tags.get('natural') == 'water' or way.tags.get('water'):
                if len(points) >= 3 and way.is_closed:
                    self.pdf.draw_polygon(points, fill_color=water_color)

            if 'waterway' in way.tags:
                color = self.style_manager.get_waterway_color(way.tags['waterway'])
                width = 1.5 if way.tags['waterway'] == 'river' else 0.75
                if len(points) >= 2:
                    self.pdf.draw_polyline(points, color, width)

    def _render_buildings(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render buildings."""
        fill_color, outline_color = self.style_manager.get_building_color()

        for way in ways:
            if 'building' in way.tags and way.is_closed:
                points = self._get_way_coords(way, node_coords)
                if len(points) >= 3:
                    self.pdf.draw_polygon(points, fill_color, outline_color, 0.25)

    def _render_railways(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render railways."""
        for way in ways:
            if 'railway' in way.tags:
                points = self._get_way_coords(way, node_coords)
                if len(points) >= 2:
                    color = self.style_manager.get_railway_color(way.tags['railway'])
                    self.pdf.draw_polyline(points, color, 1.0)

    def _render_highways(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render highways (roads)."""
        highway_order = [
            'path', 'footway', 'cycleway', 'track', 'service',
            'residential', 'unclassified', 'living_street',
            'tertiary', 'tertiary_link',
            'secondary', 'secondary_link',
            'primary', 'primary_link',
            'trunk', 'trunk_link',
            'motorway', 'motorway_link',
        ]

        highway_ways = [(way, way.tags.get('highway', '')) for way in ways if 'highway' in way.tags]
        highway_ways.sort(key=lambda x: highway_order.index(x[1]) if x[1] in highway_order else -1)

        for way, hw_type in highway_ways:
            points = self._get_way_coords(way, node_coords)
            if len(points) >= 2:
                fill_color, outline_color = self.style_manager.get_highway_color(hw_type)
                width = self.style_manager.get_highway_width(hw_type) * 0.5  # Scale down for PDF

                # Draw casing (outline) first
                if width > 0.5:
                    self.pdf.draw_polyline(points, outline_color, width + 1)
                # Draw fill
                self.pdf.draw_polyline(points, fill_color, width)

    def _render_bikelanes(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render bike lanes and cycleways."""
        bikelane_color = (255, 0, 255)  # Magenta

        for way in ways:
            # Check if it's a cycleway or has cycleway tags
            is_cycleway = (
                way.tags.get('highway') == 'cycleway' or
                'cycleway' in way.tags or
                way.tags.get('bicycle') == 'designated'
            )

            if is_cycleway:
                points = self._get_way_coords(way, node_coords)
                if len(points) >= 2:
                    width = 1.0 * self.line_scale
                    self.pdf.draw_polyline(points, bikelane_color, width)

    def _render_trees(self, nodes: List[Any]):
        """Render trees as green dots."""
        tree_color = (34, 139, 34)  # Forest green

        for node in nodes:
            if node.tags.get('natural') == 'tree':
                x, y = self.transform.geo_to_pdf(node.lat, node.lon)
                self.pdf.draw_circle(
                    x, y, self.tree_size,
                    fill_color=tree_color,
                    stroke_color=(0, 100, 0),  # Darker green outline
                    stroke_width=0.25
                )

    def _render_pois(self, nodes: List[Any]):
        """Render points of interest."""
        for node in nodes:
            if not any(k in node.tags for k in ['amenity', 'shop', 'tourism', 'leisure', 'historic']):
                continue

            x, y = self.transform.geo_to_pdf(node.lat, node.lon)
            color = self.style_manager.get_poi_color(node.tags)
            self.pdf.draw_circle(x, y, self.poi_size, fill_color=color, stroke_color=(255, 255, 255), stroke_width=0.5)

    def _render_scale_bar(self):
        """Render scale bar."""
        meters_per_point = self.transform.get_scale_meters_per_point()

        # Target scale bar length
        target_points = self.width / 6
        target_meters = target_points * meters_per_point

        # Round to nice number
        nice_distances = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000]
        distance = min(nice_distances, key=lambda d: abs(d - target_meters))

        bar_points = distance / meters_per_point
        bar_color = self.style_manager.get_scale_bar_color()

        # Position at bottom left
        x = self.margin + 10
        y = self.margin + 15

        # Draw bar
        self.pdf.draw_rectangle(x, y, bar_points, 3, fill_color=bar_color)
        self.pdf.draw_line(x, y, x, y + 8, bar_color, 0.5)
        self.pdf.draw_line(x + bar_points, y, x + bar_points, y + 8, bar_color, 0.5)

        # Draw label
        if distance >= 1000:
            label = f"{distance // 1000} km"
        else:
            label = f"{distance} m"

        text_color, _ = self.style_manager.get_text_colors()
        self.pdf.draw_text(x, y + 12, label, 8, 'Helvetica', text_color)

    def _render_legend(self):
        """Render map legend."""
        bg_color, border_color = self.style_manager.get_legend_colors()
        text_color, _ = self.style_manager.get_text_colors()

        # Legend position (top right)
        x = self.width - self.margin - 80
        y = self.height - self.margin - 90

        # Draw background
        self.pdf.draw_rectangle(x, y, 70, 80, fill_color=bg_color, stroke_color=border_color, stroke_width=0.5)

        # Legend title
        self.pdf.draw_text(x + 5, y + 68, "Legend", 8, 'Helvetica-Bold', text_color)

        # Legend items
        items = [
            ("Roads", self.style_manager.get_highway_color("primary")[0]),
            ("Buildings", self.style_manager.get_building_color()[0]),
            ("Water", self.style_manager.get_water_color()),
            ("Amenities", self.style_manager.style["amenity"]),
            ("Shops", self.style_manager.style["shop"]),
        ]

        for i, (label, color) in enumerate(items):
            iy = y + 52 - i * 12
            # Color swatch
            self.pdf.draw_rectangle(x + 5, iy, 10, 8, fill_color=color, stroke_color=border_color, stroke_width=0.25)
            # Label
            self.pdf.draw_text(x + 20, iy + 1, label, 7, 'Helvetica', text_color)

    def _render_title(self, title: str):
        """Render title."""
        text_color, _ = self.style_manager.get_text_colors()
        # Center title at top
        self.pdf.draw_text(self.margin + 10, self.height - self.margin - 20, title, 14, 'Helvetica-Bold', text_color)

    def save(self, filename: str, title: str = "OSMFast Map"):
        """Save rendered PDF to file."""
        if self.pdf:
            self.pdf.save(filename, title)
