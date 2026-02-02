"""
Color styles and themes for map rendering.
"""

from typing import Dict, Tuple, Optional


# Color type: RGB tuple (0-255)
Color = Tuple[int, int, int]


def hex_to_rgb(hex_color: int) -> Color:
    """Convert hex color (0xRRGGBB) to RGB tuple."""
    return ((hex_color >> 16) & 0xFF, (hex_color >> 8) & 0xFF, hex_color & 0xFF)


def rgb_to_hex(r: int, g: int, b: int) -> int:
    """Convert RGB to hex color."""
    return (r << 16) | (g << 8) | b


def color_to_css(color: Color) -> str:
    """Convert RGB tuple to CSS color string."""
    return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"


# =============================================================================
# Style Definitions
# =============================================================================

STYLES = {
    "default": {
        "name": "Default",
        "background": (255, 255, 255),  # White
        "water": (170, 211, 223),       # Light blue
        "landuse": {
            "forest": (173, 209, 158),
            "grass": (205, 235, 176),
            "meadow": (205, 235, 176),
            "residential": (224, 223, 223),
            "commercial": (240, 224, 224),
            "industrial": (235, 219, 232),
            "farmland": (238, 240, 213),
            "default": (232, 232, 232),
        },
        "natural": {
            "water": (170, 211, 223),
            "wood": (173, 209, 158),
            "scrub": (200, 215, 171),
            "beach": (255, 241, 186),
            "default": (200, 215, 171),
        },
        "building": (217, 208, 201),
        "building_outline": (180, 167, 156),
        "highway": {
            "motorway": (232, 146, 162),
            "motorway_link": (232, 146, 162),
            "trunk": (249, 178, 156),
            "trunk_link": (249, 178, 156),
            "primary": (252, 214, 164),
            "primary_link": (252, 214, 164),
            "secondary": (247, 250, 191),
            "secondary_link": (247, 250, 191),
            "tertiary": (255, 255, 255),
            "tertiary_link": (255, 255, 255),
            "residential": (255, 255, 255),
            "unclassified": (255, 255, 255),
            "service": (255, 255, 255),
            "living_street": (237, 237, 237),
            "pedestrian": (237, 237, 237),
            "footway": (250, 128, 114),
            "path": (250, 128, 114),
            "cycleway": (0, 148, 255),
            "track": (191, 179, 150),
            "default": (200, 200, 200),
        },
        "highway_outline": {
            "motorway": (200, 100, 120),
            "trunk": (200, 140, 120),
            "primary": (200, 170, 130),
            "secondary": (200, 200, 150),
            "default": (180, 180, 180),
        },
        "railway": {
            "rail": (150, 150, 150),
            "subway": (120, 120, 180),
            "tram": (100, 100, 100),
            "default": (130, 130, 130),
        },
        "waterway": {
            "river": (170, 211, 223),
            "stream": (170, 211, 223),
            "canal": (170, 211, 223),
            "default": (170, 211, 223),
        },
        "amenity": (255, 107, 107),      # Red
        "shop": (172, 57, 172),          # Purple
        "tourism": (0, 153, 255),        # Blue
        "leisure": (140, 200, 140),      # Light green
        "poi_default": (255, 165, 0),    # Orange
        "text": (0, 0, 0),
        "text_halo": (255, 255, 255),
        "grid": (200, 200, 200),
        "scale_bar": (0, 0, 0),
        "legend_bg": (255, 255, 255),
        "legend_border": (100, 100, 100),
    },

    "dark": {
        "name": "Dark",
        "background": (26, 26, 46),      # Dark blue-gray
        "water": (22, 33, 62),           # Dark navy
        "landuse": {
            "forest": (30, 60, 40),
            "grass": (35, 55, 35),
            "residential": (40, 40, 55),
            "commercial": (50, 40, 50),
            "industrial": (45, 40, 55),
            "default": (35, 35, 50),
        },
        "natural": {
            "water": (22, 33, 62),
            "wood": (30, 60, 40),
            "default": (35, 50, 40),
        },
        "building": (45, 45, 68),
        "building_outline": (60, 60, 85),
        "highway": {
            "motorway": (120, 80, 100),
            "trunk": (110, 90, 80),
            "primary": (100, 100, 80),
            "secondary": (80, 80, 70),
            "tertiary": (70, 70, 80),
            "residential": (60, 60, 75),
            "footway": (100, 70, 70),
            "cycleway": (50, 80, 120),
            "default": (55, 55, 70),
        },
        "highway_outline": {
            "default": (40, 40, 55),
        },
        "railway": {
            "rail": (80, 80, 100),
            "default": (70, 70, 90),
        },
        "waterway": {
            "default": (22, 33, 62),
        },
        "amenity": (255, 107, 107),
        "shop": (200, 100, 200),
        "tourism": (100, 180, 255),
        "leisure": (80, 150, 80),
        "poi_default": (255, 180, 100),
        "text": (200, 200, 220),
        "text_halo": (26, 26, 46),
        "grid": (50, 50, 70),
        "scale_bar": (200, 200, 220),
        "legend_bg": (35, 35, 55),
        "legend_border": (80, 80, 100),
    },

    "light": {
        "name": "Light",
        "background": (250, 250, 248),
        "water": (200, 230, 245),
        "landuse": {
            "forest": (220, 240, 210),
            "grass": (230, 245, 220),
            "residential": (248, 248, 248),
            "default": (245, 245, 245),
        },
        "natural": {
            "water": (200, 230, 245),
            "wood": (220, 240, 210),
            "default": (230, 240, 220),
        },
        "building": (240, 238, 235),
        "building_outline": (210, 205, 200),
        "highway": {
            "motorway": (255, 200, 200),
            "trunk": (255, 220, 200),
            "primary": (255, 235, 210),
            "secondary": (255, 245, 230),
            "tertiary": (255, 255, 255),
            "residential": (255, 255, 255),
            "footway": (255, 200, 190),
            "cycleway": (200, 220, 255),
            "default": (250, 250, 250),
        },
        "highway_outline": {
            "default": (220, 220, 220),
        },
        "railway": {
            "default": (180, 180, 180),
        },
        "waterway": {
            "default": (180, 215, 235),
        },
        "amenity": (255, 100, 100),
        "shop": (180, 80, 180),
        "tourism": (80, 160, 255),
        "leisure": (120, 200, 120),
        "poi_default": (255, 150, 50),
        "text": (60, 60, 60),
        "text_halo": (255, 255, 255),
        "grid": (230, 230, 230),
        "scale_bar": (60, 60, 60),
        "legend_bg": (255, 255, 255),
        "legend_border": (180, 180, 180),
    },

    "blueprint": {
        "name": "Blueprint",
        "background": (0, 51, 102),       # Dark blue
        "water": (0, 40, 80),
        "landuse": {
            "default": (0, 51, 102),
        },
        "natural": {
            "default": (0, 51, 102),
        },
        "building": (0, 51, 102),
        "building_outline": (100, 180, 255),
        "highway": {
            "motorway": (255, 255, 255),
            "trunk": (255, 255, 255),
            "primary": (200, 220, 255),
            "secondary": (150, 180, 220),
            "tertiary": (100, 150, 200),
            "residential": (80, 130, 180),
            "footway": (100, 150, 200),
            "default": (80, 130, 180),
        },
        "highway_outline": {
            "default": (0, 51, 102),
        },
        "railway": {
            "default": (150, 200, 255),
        },
        "waterway": {
            "default": (100, 180, 255),
        },
        "amenity": (255, 200, 100),
        "shop": (255, 150, 200),
        "tourism": (150, 255, 200),
        "leisure": (100, 255, 150),
        "poi_default": (255, 255, 150),
        "text": (255, 255, 255),
        "text_halo": (0, 51, 102),
        "grid": (50, 100, 150),
        "scale_bar": (255, 255, 255),
        "legend_bg": (0, 40, 80),
        "legend_border": (100, 180, 255),
    },
}


class StyleManager:
    """Manages color styles for rendering."""

    def __init__(self, style_name: str = "default"):
        if style_name not in STYLES:
            raise ValueError(f"Unknown style: {style_name}. Available: {list(STYLES.keys())}")
        self.style = STYLES[style_name]
        self.style_name = style_name

    def get_background(self) -> Color:
        """Get background color."""
        return self.style["background"]

    def get_water_color(self) -> Color:
        """Get water color."""
        return self.style["water"]

    def get_building_color(self) -> Tuple[Color, Color]:
        """Get building fill and outline colors."""
        return self.style["building"], self.style["building_outline"]

    def get_highway_color(self, highway_type: str) -> Tuple[Color, Color]:
        """Get highway fill and outline colors."""
        hw_colors = self.style["highway"]
        outline_colors = self.style["highway_outline"]

        fill = hw_colors.get(highway_type, hw_colors.get("default", (200, 200, 200)))
        outline = outline_colors.get(highway_type, outline_colors.get("default", (150, 150, 150)))

        return fill, outline

    def get_highway_width(self, highway_type: str) -> int:
        """Get highway line width based on type."""
        widths = {
            "motorway": 5,
            "motorway_link": 4,
            "trunk": 4,
            "trunk_link": 3,
            "primary": 4,
            "primary_link": 3,
            "secondary": 3,
            "secondary_link": 2,
            "tertiary": 2,
            "tertiary_link": 2,
            "residential": 2,
            "unclassified": 2,
            "service": 1,
            "living_street": 2,
            "pedestrian": 2,
            "footway": 1,
            "path": 1,
            "cycleway": 1,
            "track": 1,
        }
        return widths.get(highway_type, 1)

    def get_landuse_color(self, landuse_type: str) -> Color:
        """Get landuse color."""
        landuse_colors = self.style["landuse"]
        return landuse_colors.get(landuse_type, landuse_colors.get("default", (232, 232, 232)))

    def get_natural_color(self, natural_type: str) -> Color:
        """Get natural feature color."""
        natural_colors = self.style["natural"]
        return natural_colors.get(natural_type, natural_colors.get("default", (200, 215, 171)))

    def get_railway_color(self, railway_type: str) -> Color:
        """Get railway color."""
        railway_colors = self.style["railway"]
        return railway_colors.get(railway_type, railway_colors.get("default", (130, 130, 130)))

    def get_waterway_color(self, waterway_type: str) -> Color:
        """Get waterway color."""
        waterway_colors = self.style["waterway"]
        return waterway_colors.get(waterway_type, waterway_colors.get("default", (170, 211, 223)))

    def get_poi_color(self, tags: Dict[str, str]) -> Color:
        """Get POI color based on tags."""
        if "amenity" in tags:
            return self.style["amenity"]
        elif "shop" in tags:
            return self.style["shop"]
        elif "tourism" in tags:
            return self.style["tourism"]
        elif "leisure" in tags:
            return self.style["leisure"]
        return self.style["poi_default"]

    def get_text_colors(self) -> Tuple[Color, Color]:
        """Get text and halo colors."""
        return self.style["text"], self.style["text_halo"]

    def get_scale_bar_color(self) -> Color:
        """Get scale bar color."""
        return self.style["scale_bar"]

    def get_legend_colors(self) -> Tuple[Color, Color]:
        """Get legend background and border colors."""
        return self.style["legend_bg"], self.style["legend_border"]


def get_available_styles() -> list:
    """Get list of available style names."""
    return list(STYLES.keys())
