"""
Pure Python PNG renderer - zero external dependencies.

Uses only Python standard library (zlib for compression).
"""

import zlib
import struct
import math
from typing import List, Tuple, Optional, Dict, Any

from .styles import StyleManager, Color, color_to_css


class PNGRenderer:
    """
    Pure Python PNG image renderer.

    Creates valid PNG files using only the standard library.
    Supports basic drawing primitives: points, lines, polygons.
    """

    def __init__(self, width: int, height: int, background: Color = (255, 255, 255)):
        """
        Initialize renderer with canvas size.

        Args:
            width: Image width in pixels
            height: Image height in pixels
            background: Background color as RGB tuple
        """
        self.width = width
        self.height = height
        # Initialize pixel buffer with background color
        self.pixels = [[background for _ in range(width)] for _ in range(height)]

    def set_pixel(self, x: int, y: int, color: Color):
        """Set a single pixel color."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = color

    def get_pixel(self, x: int, y: int) -> Color:
        """Get pixel color at position."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.pixels[y][x]
        return (0, 0, 0)

    def blend_pixel(self, x: int, y: int, color: Color, alpha: float):
        """Blend a pixel with alpha transparency."""
        if 0 <= x < self.width and 0 <= y < self.height:
            bg = self.pixels[y][x]
            r = int(bg[0] * (1 - alpha) + color[0] * alpha)
            g = int(bg[1] * (1 - alpha) + color[1] * alpha)
            b = int(bg[2] * (1 - alpha) + color[2] * alpha)
            self.pixels[y][x] = (r, g, b)

    def draw_point(self, x: int, y: int, color: Color, size: int = 3):
        """Draw a circular point/marker."""
        for dy in range(-size, size + 1):
            for dx in range(-size, size + 1):
                dist_sq = dx * dx + dy * dy
                if dist_sq <= size * size:
                    # Simple anti-aliasing at edges
                    if dist_sq >= (size - 1) * (size - 1):
                        alpha = 1.0 - (math.sqrt(dist_sq) - size + 1)
                        self.blend_pixel(x + dx, y + dy, color, max(0, min(1, alpha)))
                    else:
                        self.set_pixel(x + dx, y + dy, color)

    def draw_line(self, x1: int, y1: int, x2: int, y2: int, color: Color, width: int = 1):
        """
        Draw a line using Bresenham's algorithm with width support.
        """
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        while True:
            # Draw thick line by drawing multiple points
            if width == 1:
                self.set_pixel(x1, y1, color)
            else:
                half_w = width // 2
                for wy in range(-half_w, half_w + 1):
                    for wx in range(-half_w, half_w + 1):
                        if wx * wx + wy * wy <= half_w * half_w + half_w:
                            self.set_pixel(x1 + wx, y1 + wy, color)

            if x1 == x2 and y1 == y2:
                break

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy

    def draw_polyline(self, points: List[Tuple[int, int]], color: Color, width: int = 1):
        """Draw a polyline (connected line segments)."""
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            self.draw_line(x1, y1, x2, y2, color, width)

    def draw_polygon_outline(self, points: List[Tuple[int, int]], color: Color, width: int = 1):
        """Draw polygon outline."""
        if len(points) < 3:
            return
        # Draw all edges including closing edge
        for i in range(len(points)):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % len(points)]
            self.draw_line(x1, y1, x2, y2, color, width)

    def fill_polygon(self, points: List[Tuple[int, int]], color: Color):
        """
        Fill a polygon using scanline algorithm.
        """
        if len(points) < 3:
            return

        # Find bounding box
        min_y = max(0, min(p[1] for p in points))
        max_y = min(self.height - 1, max(p[1] for p in points))
        min_x = max(0, min(p[0] for p in points))
        max_x = min(self.width - 1, max(p[0] for p in points))

        # Scanline fill
        for y in range(min_y, max_y + 1):
            # Find intersections with polygon edges
            intersections = []
            n = len(points)
            for i in range(n):
                x1, y1 = points[i]
                x2, y2 = points[(i + 1) % n]

                # Check if edge crosses this scanline
                if (y1 <= y < y2) or (y2 <= y < y1):
                    if y2 != y1:
                        x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                        intersections.append(x)

            # Sort intersections and fill between pairs
            intersections.sort()
            for i in range(0, len(intersections) - 1, 2):
                x_start = max(min_x, int(intersections[i]))
                x_end = min(max_x, int(intersections[i + 1]))
                for x in range(x_start, x_end + 1):
                    self.set_pixel(x, y, color)

    def draw_polygon(self, points: List[Tuple[int, int]], fill_color: Color,
                     outline_color: Optional[Color] = None, outline_width: int = 1):
        """Draw a filled polygon with optional outline."""
        self.fill_polygon(points, fill_color)
        if outline_color:
            self.draw_polygon_outline(points, outline_color, outline_width)

    def draw_rectangle(self, x: int, y: int, width: int, height: int,
                       fill_color: Color, outline_color: Optional[Color] = None):
        """Draw a filled rectangle."""
        for py in range(y, min(y + height, self.height)):
            for px in range(x, min(x + width, self.width)):
                if px >= 0 and py >= 0:
                    self.set_pixel(px, py, fill_color)

        if outline_color:
            # Top and bottom edges
            for px in range(x, min(x + width, self.width)):
                if px >= 0:
                    if y >= 0 and y < self.height:
                        self.set_pixel(px, y, outline_color)
                    if y + height - 1 >= 0 and y + height - 1 < self.height:
                        self.set_pixel(px, y + height - 1, outline_color)
            # Left and right edges
            for py in range(y, min(y + height, self.height)):
                if py >= 0:
                    if x >= 0 and x < self.width:
                        self.set_pixel(x, py, outline_color)
                    if x + width - 1 >= 0 and x + width - 1 < self.width:
                        self.set_pixel(x + width - 1, py, outline_color)

    def draw_text_simple(self, x: int, y: int, text: str, color: Color, scale: int = 1):
        """
        Draw simple bitmap text using a basic 5x7 font.
        Limited character set but works without external fonts.
        """
        # Simple 5x7 bitmap font (subset of ASCII)
        FONT = {
            'A': [0x1F, 0x05, 0x05, 0x05, 0x1F],
            'B': [0x1F, 0x15, 0x15, 0x15, 0x0A],
            'C': [0x0E, 0x11, 0x11, 0x11, 0x11],
            'D': [0x1F, 0x11, 0x11, 0x11, 0x0E],
            'E': [0x1F, 0x15, 0x15, 0x15, 0x11],
            'F': [0x1F, 0x05, 0x05, 0x05, 0x01],
            'G': [0x0E, 0x11, 0x15, 0x15, 0x1D],
            'H': [0x1F, 0x04, 0x04, 0x04, 0x1F],
            'I': [0x11, 0x11, 0x1F, 0x11, 0x11],
            'J': [0x08, 0x10, 0x10, 0x10, 0x0F],
            'K': [0x1F, 0x04, 0x0A, 0x11, 0x00],
            'L': [0x1F, 0x10, 0x10, 0x10, 0x10],
            'M': [0x1F, 0x02, 0x04, 0x02, 0x1F],
            'N': [0x1F, 0x02, 0x04, 0x08, 0x1F],
            'O': [0x0E, 0x11, 0x11, 0x11, 0x0E],
            'P': [0x1F, 0x05, 0x05, 0x05, 0x02],
            'Q': [0x0E, 0x11, 0x15, 0x09, 0x16],
            'R': [0x1F, 0x05, 0x05, 0x0D, 0x12],
            'S': [0x12, 0x15, 0x15, 0x15, 0x09],
            'T': [0x01, 0x01, 0x1F, 0x01, 0x01],
            'U': [0x0F, 0x10, 0x10, 0x10, 0x0F],
            'V': [0x07, 0x08, 0x10, 0x08, 0x07],
            'W': [0x1F, 0x08, 0x04, 0x08, 0x1F],
            'X': [0x11, 0x0A, 0x04, 0x0A, 0x11],
            'Y': [0x01, 0x02, 0x1C, 0x02, 0x01],
            'Z': [0x11, 0x19, 0x15, 0x13, 0x11],
            '0': [0x0E, 0x19, 0x15, 0x13, 0x0E],
            '1': [0x00, 0x12, 0x1F, 0x10, 0x00],
            '2': [0x12, 0x19, 0x15, 0x15, 0x12],
            '3': [0x11, 0x15, 0x15, 0x15, 0x0A],
            '4': [0x07, 0x04, 0x04, 0x1F, 0x04],
            '5': [0x17, 0x15, 0x15, 0x15, 0x09],
            '6': [0x0E, 0x15, 0x15, 0x15, 0x08],
            '7': [0x01, 0x01, 0x19, 0x05, 0x03],
            '8': [0x0A, 0x15, 0x15, 0x15, 0x0A],
            '9': [0x02, 0x15, 0x15, 0x15, 0x0E],
            ' ': [0x00, 0x00, 0x00, 0x00, 0x00],
            '.': [0x00, 0x18, 0x18, 0x00, 0x00],
            ',': [0x00, 0x20, 0x10, 0x00, 0x00],
            ':': [0x00, 0x0A, 0x00, 0x00, 0x00],
            '-': [0x04, 0x04, 0x04, 0x04, 0x04],
            '_': [0x10, 0x10, 0x10, 0x10, 0x10],
            '=': [0x0A, 0x0A, 0x0A, 0x0A, 0x0A],
            'm': [0x1E, 0x02, 0x1E, 0x02, 0x1C],
            'k': [0x1F, 0x04, 0x0A, 0x10, 0x00],
        }

        cursor_x = x
        for char in text.upper():
            if char in FONT:
                glyph = FONT[char]
                for col, bits in enumerate(glyph):
                    for row in range(7):
                        if bits & (1 << row):
                            for sy in range(scale):
                                for sx in range(scale):
                                    self.set_pixel(
                                        cursor_x + col * scale + sx,
                                        y + row * scale + sy,
                                        color
                                    )
                cursor_x += 6 * scale
            else:
                cursor_x += 6 * scale  # Space for unknown chars

    def save_png(self, filename: str):
        """
        Save image as PNG file.

        Uses zlib compression (built into Python) to create valid PNG.
        """
        def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
            """Create a PNG chunk with CRC."""
            chunk = chunk_type + data
            crc = zlib.crc32(chunk) & 0xffffffff
            return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)

        # PNG signature
        signature = b'\x89PNG\r\n\x1a\n'

        # IHDR chunk (image header)
        # Width, Height, Bit depth (8), Color type (2=RGB), Compression, Filter, Interlace
        ihdr_data = struct.pack('>IIBBBBB', self.width, self.height, 8, 2, 0, 0, 0)
        ihdr = make_chunk(b'IHDR', ihdr_data)

        # IDAT chunk (image data)
        raw_data = bytearray()
        for row in self.pixels:
            raw_data.append(0)  # Filter type: None
            for r, g, b in row:
                raw_data.extend([r, g, b])

        compressed = zlib.compress(bytes(raw_data), 9)  # Max compression
        idat = make_chunk(b'IDAT', compressed)

        # IEND chunk (image end)
        iend = make_chunk(b'IEND', b'')

        # Write file
        with open(filename, 'wb') as f:
            f.write(signature + ihdr + idat + iend)


class GeoTransform:
    """
    Transforms geographic coordinates to pixel coordinates.
    """

    def __init__(self, width: int, height: int,
                 min_lat: float, max_lat: float,
                 min_lon: float, max_lon: float,
                 padding: int = 20):
        """
        Initialize geo transform.

        Args:
            width: Image width in pixels
            height: Image height in pixels
            min_lat, max_lat: Latitude bounds
            min_lon, max_lon: Longitude bounds
            padding: Padding in pixels around the edges
        """
        self.width = width
        self.height = height
        self.padding = padding

        # Available drawing area
        self.draw_width = width - 2 * padding
        self.draw_height = height - 2 * padding

        # Geo bounds
        self.min_lat = min_lat
        self.max_lat = max_lat
        self.min_lon = min_lon
        self.max_lon = max_lon

        # Calculate scale (use same scale for x and y to maintain aspect ratio)
        lat_range = max_lat - min_lat
        lon_range = max_lon - min_lon

        # Adjust for latitude (Mercator-like projection for small areas)
        lat_center = (min_lat + max_lat) / 2
        lon_scale = math.cos(math.radians(lat_center))

        # Pixels per degree
        scale_x = self.draw_width / (lon_range * lon_scale) if lon_range > 0 else 1
        scale_y = self.draw_height / lat_range if lat_range > 0 else 1

        # Use smaller scale to fit everything
        self.scale = min(scale_x, scale_y)
        self.lon_scale = lon_scale

        # Center offset
        self.center_lon = (min_lon + max_lon) / 2
        self.center_lat = (min_lat + max_lat) / 2

    def geo_to_pixel(self, lat: float, lon: float) -> Tuple[int, int]:
        """Convert geographic coordinates to pixel coordinates."""
        x = self.width // 2 + int((lon - self.center_lon) * self.lon_scale * self.scale)
        y = self.height // 2 - int((lat - self.center_lat) * self.scale)
        return x, y

    def get_scale_meters_per_pixel(self) -> float:
        """Get approximate meters per pixel at center latitude."""
        # Approximate meters per degree of longitude at center latitude
        meters_per_degree = 111320 * math.cos(math.radians(self.center_lat))
        return meters_per_degree / (self.scale * self.lon_scale)


class MapRenderer:
    """
    High-level map renderer that renders OSM data to PNG.

    Supports layer visibility controls and various rendering options.
    """

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

    def __init__(self, width: int, height: int, style: str = "default",
                 layers: Optional[Dict[str, bool]] = None,
                 line_scale: float = 1.0,
                 poi_size: int = 4,
                 tree_size: int = 3):
        """
        Initialize map renderer.

        Args:
            width: Image width in pixels
            height: Image height in pixels
            style: Color style name
            layers: Dict of layer visibility (e.g., {'buildings': True, 'pois': False})
            line_scale: Multiplier for line widths (default 1.0)
            poi_size: Size of POI markers in pixels (default 4)
            tree_size: Size of tree markers in pixels (default 3)
        """
        self.width = width
        self.height = height
        self.style_manager = StyleManager(style)
        self.png: Optional[PNGRenderer] = None
        self.transform: Optional[GeoTransform] = None

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
               show_legend: bool = True,
               show_scale: bool = True,
               title: Optional[str] = None,
               padding: float = 0.02,
               zoom: float = 1.0) -> PNGRenderer:
        """
        Render OSM data to PNG.

        Args:
            nodes: List of OSM nodes
            ways: List of OSM ways
            node_coords: Dictionary mapping node IDs to (lat, lon)
            bbox: Optional bounding box (min_lat, max_lat, min_lon, max_lon)
            show_legend: Whether to show legend
            show_scale: Whether to show scale bar
            title: Optional title text
            padding: Padding around bounds as fraction (default 0.02 = 2%)
            zoom: Zoom factor (1.0 = normal, 1.5 = 50% more zoomed in, 2.0 = 2x zoom)

        Returns:
            PNGRenderer with rendered image
        """
        # Calculate bounding box if not provided
        if bbox is None:
            bbox = self._calculate_bbox(nodes, ways, node_coords)

        min_lat, max_lat, min_lon, max_lon = bbox

        # Add padding to bounds
        lat_pad = (max_lat - min_lat) * padding
        lon_pad = (max_lon - min_lon) * padding
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

        # Initialize renderer and transform
        self.png = PNGRenderer(self.width, self.height, self.style_manager.get_background())
        self.transform = GeoTransform(self.width, self.height, min_lat, max_lat, min_lon, max_lon)

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

        # Render decorations
        if show_scale:
            self._render_scale_bar()
        if show_legend:
            self._render_legend()
        if title:
            self._render_title(title)

        return self.png

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
            return (0, 1, 0, 1)  # Default bbox

        return (min(lats), max(lats), min(lons), max(lons))

    def _get_way_coords(self, way: Any, node_coords: Dict[str, Tuple[float, float]]) -> List[Tuple[int, int]]:
        """Get pixel coordinates for a way."""
        points = []
        for ref in way.node_refs:
            if ref in node_coords:
                lat, lon = node_coords[ref]
                x, y = self.transform.geo_to_pixel(lat, lon)
                points.append((x, y))
        return points

    def _render_landuse(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render landuse polygons."""
        for way in ways:
            if 'landuse' in way.tags and way.is_closed:
                points = self._get_way_coords(way, node_coords)
                if len(points) >= 3:
                    color = self.style_manager.get_landuse_color(way.tags['landuse'])
                    self.png.fill_polygon(points, color)

    def _render_natural(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render natural features."""
        for way in ways:
            if 'natural' in way.tags:
                points = self._get_way_coords(way, node_coords)
                if len(points) >= 3 and way.is_closed:
                    color = self.style_manager.get_natural_color(way.tags['natural'])
                    self.png.fill_polygon(points, color)

    def _render_water(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render water features."""
        water_color = self.style_manager.get_water_color()

        for way in ways:
            points = self._get_way_coords(way, node_coords)

            # Water areas
            if way.tags.get('natural') == 'water' or way.tags.get('water'):
                if len(points) >= 3 and way.is_closed:
                    self.png.fill_polygon(points, water_color)

            # Waterways (rivers, streams)
            if 'waterway' in way.tags:
                color = self.style_manager.get_waterway_color(way.tags['waterway'])
                width = 2 if way.tags['waterway'] == 'river' else 1
                if len(points) >= 2:
                    self.png.draw_polyline(points, color, width)

    def _render_buildings(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render buildings."""
        fill_color, outline_color = self.style_manager.get_building_color()

        for way in ways:
            if 'building' in way.tags and way.is_closed:
                points = self._get_way_coords(way, node_coords)
                if len(points) >= 3:
                    self.png.draw_polygon(points, fill_color, outline_color, 1)

    def _render_railways(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render railways."""
        for way in ways:
            if 'railway' in way.tags:
                points = self._get_way_coords(way, node_coords)
                if len(points) >= 2:
                    color = self.style_manager.get_railway_color(way.tags['railway'])
                    self.png.draw_polyline(points, color, 2)

    def _render_highways(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render highways (roads)."""
        # Sort by importance (less important first)
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
                width = self.style_manager.get_highway_width(hw_type)

                # Draw outline first (casing)
                if width > 1:
                    self.png.draw_polyline(points, outline_color, int(width * self.line_scale) + 2)
                # Draw fill
                self.png.draw_polyline(points, fill_color, int(width * self.line_scale))

    def _render_bikelanes(self, ways: List[Any], node_coords: Dict[str, Tuple[float, float]]):
        """Render bike lanes and cycleways."""
        bikelane_color = (255, 0, 255)  # Magenta

        for way in ways:
            is_cycleway = way.tags.get('highway') == 'cycleway' or 'cycleway' in way.tags
            if is_cycleway:
                points = self._get_way_coords(way, node_coords)
                if len(points) >= 2:
                    width = max(2, int(3 * self.line_scale))
                    self.png.draw_polyline(points, bikelane_color, width)

    def _render_trees(self, nodes: List[Any]):
        """Render trees as green dots."""
        tree_color = (34, 139, 34)  # Forest green

        for node in nodes:
            if node.tags.get('natural') == 'tree':
                x, y = self.transform.geo_to_pixel(node.lat, node.lon)
                self.png.draw_point(x, y, tree_color, size=self.tree_size)

    def _render_pois(self, nodes: List[Any]):
        """Render points of interest."""
        for node in nodes:
            # Skip nodes without significant tags
            if not any(k in node.tags for k in ['amenity', 'shop', 'tourism', 'leisure', 'historic']):
                continue

            x, y = self.transform.geo_to_pixel(node.lat, node.lon)
            color = self.style_manager.get_poi_color(node.tags)
            self.png.draw_point(x, y, color, size=self.poi_size)

    def _render_scale_bar(self):
        """Render scale bar."""
        # Calculate scale bar length
        meters_per_pixel = self.transform.get_scale_meters_per_pixel()

        # Find nice round distance
        target_pixels = self.width // 5  # Aim for ~20% of width
        target_meters = target_pixels * meters_per_pixel

        # Round to nice number
        nice_distances = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000]
        distance = min(nice_distances, key=lambda d: abs(d - target_meters))

        bar_pixels = int(distance / meters_per_pixel)
        bar_color = self.style_manager.get_scale_bar_color()

        # Position at bottom left
        x = 20
        y = self.height - 30

        # Draw bar
        self.png.draw_rectangle(x, y, bar_pixels, 4, bar_color)
        self.png.draw_rectangle(x, y, 2, 10, bar_color)
        self.png.draw_rectangle(x + bar_pixels - 2, y, 2, 10, bar_color)

        # Draw label
        if distance >= 1000:
            label = f"{distance // 1000}km"
        else:
            label = f"{distance}m"
        self.png.draw_text_simple(x, y + 12, label, bar_color)

    def _render_legend(self):
        """Render map legend."""
        bg_color, border_color = self.style_manager.get_legend_colors()
        text_color, _ = self.style_manager.get_text_colors()

        # Legend position and size
        x = self.width - 120
        y = 10
        w = 110
        h = 100

        # Draw background
        self.png.draw_rectangle(x, y, w, h, bg_color, border_color)

        # Legend items
        items = [
            ("ROADS", self.style_manager.get_highway_color("primary")[0]),
            ("BUILDINGS", self.style_manager.get_building_color()[0]),
            ("WATER", self.style_manager.get_water_color()),
            ("AMENITY", self.style_manager.style["amenity"]),
            ("SHOP", self.style_manager.style["shop"]),
        ]

        for i, (label, color) in enumerate(items):
            iy = y + 12 + i * 18
            # Color swatch
            self.png.draw_rectangle(x + 8, iy, 12, 12, color, border_color)
            # Label
            self.png.draw_text_simple(x + 26, iy + 2, label, text_color)

    def _render_title(self, title: str):
        """Render title text."""
        text_color, halo_color = self.style_manager.get_text_colors()
        # Simple centered title at top
        self.png.draw_text_simple(10, 10, title, text_color, scale=2)

    def save(self, filename: str):
        """Save rendered image to file."""
        if self.png:
            self.png.save_png(filename)
