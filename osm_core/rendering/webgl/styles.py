"""
WebGL 3D style configuration.

Provides color schemes, height estimation, and style presets for 3D rendering.
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional


@dataclass
class WebGL3DStyle:
    """Configuration for 3D WebGL rendering style."""

    # Building colors
    building_fill: Tuple[int, int, int]
    building_edge: Tuple[int, int, int]

    # Environment colors
    ground_color: Tuple[int, int, int]
    background_color: Tuple[int, int, int]
    grid_color: int

    # Lighting settings
    ambient_intensity: float = 0.5
    directional_intensity: float = 0.8
    hemisphere_intensity: float = 0.3
    hemisphere_ground: int = 0x444444

    # Optional road color overrides
    road_colors: Optional[Dict[str, Tuple[int, int, int]]] = None


# Style presets for different themes
STYLE_PRESETS: Dict[str, WebGL3DStyle] = {
    "default": WebGL3DStyle(
        building_fill=(250, 245, 240),
        building_edge=(0, 0, 0),
        ground_color=(185, 182, 175),
        background_color=(240, 238, 235),
        grid_color=0x999999,
        ambient_intensity=0.85,
        directional_intensity=0.95,
        hemisphere_intensity=0.4,
        hemisphere_ground=0xeeeeee,
        road_colors={
            "motorway": (220, 60, 60),
            "trunk": (230, 120, 50),
            "primary": (50, 100, 180),
            "secondary": (80, 160, 80),
            "tertiary": (160, 140, 100),
            "residential": (120, 120, 120),
            "default": (100, 100, 100),
        }
    ),
    "dark": WebGL3DStyle(
        building_fill=(35, 35, 55),
        building_edge=(0, 255, 255),
        ground_color=(20, 20, 35),
        background_color=(15, 15, 25),
        grid_color=0x333355,
        ambient_intensity=0.5,
        directional_intensity=0.8,
        hemisphere_intensity=0.3,
        hemisphere_ground=0x444444,
        road_colors=None,
    ),
    "light": WebGL3DStyle(
        building_fill=(255, 255, 255),
        building_edge=(0, 0, 0),
        ground_color=(200, 200, 195),
        background_color=(245, 245, 245),
        grid_color=0xaaaaaa,
        ambient_intensity=0.9,
        directional_intensity=1.0,
        hemisphere_intensity=0.5,
        hemisphere_ground=0xffffff,
        road_colors={
            "motorway": (200, 40, 60),
            "trunk": (180, 50, 70),
            "primary": (30, 120, 180),
            "secondary": (40, 160, 80),
            "tertiary": (120, 120, 120),
            "residential": (90, 90, 90),
            "default": (70, 70, 70),
        }
    ),
    "blueprint": WebGL3DStyle(
        building_fill=(0, 60, 120),
        building_edge=(100, 200, 255),
        ground_color=(0, 40, 90),
        background_color=(0, 30, 70),
        grid_color=0x336699,
        ambient_intensity=0.5,
        directional_intensity=0.8,
        hemisphere_intensity=0.3,
        hemisphere_ground=0x444444,
        road_colors=None,
    ),
}

# Sun study style (fixed configuration)
SUN_STUDY_STYLE = WebGL3DStyle(
    building_fill=(250, 245, 240),
    building_edge=(0, 0, 0),
    ground_color=(160, 155, 148),
    background_color=(240, 238, 235),
    grid_color=0x999999,
    ambient_intensity=0.2,
    directional_intensity=2.0,
    hemisphere_intensity=0.15,
    hemisphere_ground=0x8b7355,
    road_colors={
        "motorway": (220, 60, 60),
        "trunk": (230, 120, 50),
        "primary": (50, 100, 180),
        "secondary": (80, 160, 80),
        "tertiary": (160, 140, 100),
        "residential": (120, 120, 120),
        "default": (100, 100, 100),
    }
)


def get_3d_style(style_name: str) -> WebGL3DStyle:
    """
    Get 3D style configuration by name.

    Args:
        style_name: Style name (default, dark, light, blueprint)

    Returns:
        WebGL3DStyle configuration
    """
    return STYLE_PRESETS.get(style_name, STYLE_PRESETS["default"])


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """
    Convert RGB to hex string for JavaScript.

    Args:
        r: Red component (0-255)
        g: Green component (0-255)
        b: Blue component (0-255)

    Returns:
        Hex string like "0xff00ff"
    """
    return f"0x{r:02x}{g:02x}{b:02x}"


def generate_road_colors_js(custom_colors: Optional[Dict[str, Tuple[int, int, int]]] = None) -> str:
    """
    Generate JavaScript object for road colors.

    Args:
        custom_colors: Optional dict of road_type -> (r, g, b)

    Returns:
        JavaScript object literal string
    """
    if custom_colors:
        parts = []
        for road_type, rgb in custom_colors.items():
            hex_val = f"0x{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            parts.append(f"{road_type}: {hex_val}")
        return "{" + ", ".join(parts) + "}"
    else:
        # Default pastel colors
        return """{
            motorway: 0xe892a2,
            trunk: 0xf9b29c,
            primary: 0xfcd6a4,
            secondary: 0xf7fabf,
            tertiary: 0xffffff,
            residential: 0xffffff,
            default: 0xcccccc
        }"""


# Building height estimation constants
DEFAULT_BUILDING_HEIGHT = 10
METERS_PER_FLOOR = 3.0

# Height estimates by building type
BUILDING_HEIGHT_ESTIMATES = {
    "house": 8,
    "residential": 12,
    "apartments": 20,
    "commercial": 15,
    "retail": 6,
    "industrial": 10,
    "warehouse": 8,
    "garage": 3,
    "shed": 3,
    "roof": 4,
    "church": 15,
    "cathedral": 30,
    "hospital": 18,
    "school": 10,
    "university": 15,
    "office": 25,
    "hotel": 20,
    "skyscraper": 100,
    "tower": 40,
}


def estimate_building_height(tags: Dict[str, str]) -> float:
    """
    Estimate building height from OSM tags.

    Args:
        tags: OSM tags dictionary

    Returns:
        Estimated height in meters
    """
    # Try explicit height
    if "height" in tags:
        try:
            height_str = tags["height"].replace("m", "").strip()
            return float(height_str)
        except ValueError:
            pass

    # Try building:levels
    if "building:levels" in tags:
        try:
            levels = int(tags["building:levels"])
            return levels * METERS_PER_FLOOR
        except ValueError:
            pass

    # Estimate by building type
    building_type = tags.get("building", "yes")
    return BUILDING_HEIGHT_ESTIMATES.get(building_type, DEFAULT_BUILDING_HEIGHT)
