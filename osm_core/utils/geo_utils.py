"""Geographic utility functions."""
import math
from typing import List, Tuple

# Earth radius in meters (WGS84 mean radius)
EARTH_RADIUS_M = 6371008.8


def calculate_polygon_area(coordinates: List[List[float]]) -> float:
    """Calculate approximate polygon area in square meters using shoelace formula.

    Uses WGS84 approximation for coordinate to meter conversion.

    Args:
        coordinates: List of [lon, lat] coordinate pairs (GeoJSON format)

    Returns:
        Area in square meters (approximate)

    Examples:
        >>> # Approximate 1km x 1km square
        >>> coords = [[0, 0], [0.009, 0], [0.009, 0.009], [0, 0.009], [0, 0]]
        >>> area = calculate_polygon_area(coords)
        >>> 900000 < area < 1100000  # ~1 sq km
        True
    """
    if len(coordinates) < 3:
        return 0.0

    # Approximate conversion: 1 degree latitude ≈ 111,320 meters
    lat_to_m = 111320.0

    # Average latitude for longitude correction
    avg_lat = sum(coord[1] for coord in coordinates) / len(coordinates)
    lon_to_m = 111320.0 * abs(math.cos(math.radians(avg_lat)))

    # Shoelace formula for polygon area
    area = 0.0
    n = len(coordinates)

    for i in range(n):
        j = (i + 1) % n
        # Convert to meters
        x1, y1 = coordinates[i][0] * lon_to_m, coordinates[i][1] * lat_to_m
        x2, y2 = coordinates[j][0] * lon_to_m, coordinates[j][1] * lat_to_m
        area += x1 * y2 - x2 * y1

    return abs(area) / 2.0


def point_in_bbox(lat: float, lon: float, top: float, left: float,
                  bottom: float, right: float) -> bool:
    """Check if a point is within a bounding box.

    Args:
        lat: Point latitude
        lon: Point longitude
        top: Maximum latitude
        left: Minimum longitude
        bottom: Minimum latitude
        right: Maximum longitude

    Returns:
        True if point is within bounds
    """
    return bottom <= lat <= top and left <= lon <= right


def calculate_center(min_lat: float, max_lat: float,
                     min_lon: float, max_lon: float) -> tuple:
    """Calculate the center point of a bounding box.

    Args:
        min_lat: Minimum latitude
        max_lat: Maximum latitude
        min_lon: Minimum longitude
        max_lon: Maximum longitude

    Returns:
        Tuple of (center_lat, center_lon)
    """
    return ((min_lat + max_lat) / 2, (min_lon + max_lon) / 2)


def get_signed_area(coordinates: List[List[float]]) -> float:
    """Calculate signed area of a ring using shoelace formula.

    Positive area indicates counter-clockwise winding.
    Negative area indicates clockwise winding.

    Args:
        coordinates: List of [lon, lat] coordinate pairs (GeoJSON format)

    Returns:
        Signed area (positive = CCW, negative = CW)
    """
    if len(coordinates) < 3:
        return 0.0

    area = 0.0
    n = len(coordinates)

    for i in range(n):
        j = (i + 1) % n
        area += coordinates[i][0] * coordinates[j][1]
        area -= coordinates[j][0] * coordinates[i][1]

    return area / 2.0


def get_ring_winding(coordinates: List[List[float]]) -> str:
    """Determine ring winding order using signed area.

    Args:
        coordinates: List of [lon, lat] coordinate pairs

    Returns:
        'ccw' for counter-clockwise, 'cw' for clockwise
    """
    area = get_signed_area(coordinates)
    return 'ccw' if area > 0 else 'cw'


def ensure_winding_order(coordinates: List[List[float]],
                         desired: str = 'ccw') -> List[List[float]]:
    """Ensure ring has the desired winding order.

    RFC 7946 requires:
    - Exterior rings: counter-clockwise (CCW)
    - Interior rings (holes): clockwise (CW)

    Args:
        coordinates: Ring coordinates as [[lon, lat], ...]
        desired: 'ccw' for counter-clockwise or 'cw' for clockwise

    Returns:
        Coordinates with correct winding (reversed if necessary)
    """
    if len(coordinates) < 3:
        return coordinates

    current = get_ring_winding(coordinates)

    if current != desired:
        return list(reversed(coordinates))

    return coordinates


def point_in_ring(point: List[float], ring: List[List[float]]) -> bool:
    """Test if a point is inside a polygon ring using ray casting.

    Args:
        point: [lon, lat] coordinate
        ring: Ring coordinates as [[lon, lat], ...]

    Returns:
        True if point is inside ring
    """
    x, y = point[0], point[1]
    n = len(ring)
    inside = False

    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]

        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside

        j = i

    return inside


def ring_contains_ring(outer: List[List[float]],
                       inner: List[List[float]]) -> bool:
    """Test if outer ring contains inner ring.

    Used for assigning holes to their containing outer ring
    in multipolygon geometry assembly.

    Args:
        outer: Outer ring coordinates
        inner: Inner ring coordinates (potential hole)

    Returns:
        True if inner is inside outer (all points of inner are inside outer)
    """
    if not inner:
        return False

    # Check if first point of inner is inside outer
    # For valid geometries, if one point is inside, all should be
    return point_in_ring(inner[0], outer)


def get_ring_centroid(coordinates: List[List[float]]) -> List[float]:
    """Calculate the centroid of a polygon ring.

    Args:
        coordinates: Ring coordinates as [[lon, lat], ...]

    Returns:
        [lon, lat] centroid coordinate
    """
    if not coordinates:
        return [0.0, 0.0]

    n = len(coordinates)
    sum_lon = sum(c[0] for c in coordinates)
    sum_lat = sum(c[1] for c in coordinates)

    return [sum_lon / n, sum_lat / n]


# =============================================================================
# LINE GEOMETRY CALCULATIONS
# =============================================================================

def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate great-circle distance between two points using Haversine formula.

    Args:
        lon1: Longitude of first point (degrees)
        lat1: Latitude of first point (degrees)
        lon2: Longitude of second point (degrees)
        lat2: Latitude of second point (degrees)

    Returns:
        Distance in meters
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    # Haversine formula
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return EARTH_RADIUS_M * c


def calculate_line_length(coordinates: List[List[float]]) -> float:
    """Calculate total length of a line in meters.

    Args:
        coordinates: List of [lon, lat] coordinate pairs

    Returns:
        Total length in meters
    """
    if len(coordinates) < 2:
        return 0.0

    total_length = 0.0
    for i in range(len(coordinates) - 1):
        lon1, lat1 = coordinates[i][0], coordinates[i][1]
        lon2, lat2 = coordinates[i + 1][0], coordinates[i + 1][1]
        total_length += haversine_distance(lon1, lat1, lon2, lat2)

    return total_length


def calculate_straight_line_distance(coordinates: List[List[float]]) -> float:
    """Calculate straight-line distance from start to end of a line.

    Args:
        coordinates: List of [lon, lat] coordinate pairs

    Returns:
        Straight-line distance in meters
    """
    if len(coordinates) < 2:
        return 0.0

    start = coordinates[0]
    end = coordinates[-1]
    return haversine_distance(start[0], start[1], end[0], end[1])


def calculate_sinuosity(coordinates: List[List[float]]) -> float:
    """Calculate sinuosity (curvature ratio) of a line.

    Sinuosity = actual_length / straight_line_distance
    - 1.0 = perfectly straight
    - >1.0 = curved (higher = more curved)

    Args:
        coordinates: List of [lon, lat] coordinate pairs

    Returns:
        Sinuosity ratio (1.0 for straight lines)
    """
    if len(coordinates) < 2:
        return 1.0

    actual_length = calculate_line_length(coordinates)
    straight_distance = calculate_straight_line_distance(coordinates)

    if straight_distance < 0.001:  # Avoid division by zero for very short segments
        return 1.0

    return actual_length / straight_distance


def calculate_bearing(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate initial bearing from point 1 to point 2.

    Args:
        lon1: Longitude of first point (degrees)
        lat1: Latitude of first point (degrees)
        lon2: Longitude of second point (degrees)
        lat2: Latitude of second point (degrees)

    Returns:
        Bearing in degrees (0-360, where 0=North, 90=East)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)

    x = math.sin(dlon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)

    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def calculate_line_bearing(coordinates: List[List[float]]) -> float:
    """Calculate bearing from start to end of a line.

    Args:
        coordinates: List of [lon, lat] coordinate pairs

    Returns:
        Bearing in degrees (0-360)
    """
    if len(coordinates) < 2:
        return 0.0

    start = coordinates[0]
    end = coordinates[-1]
    return calculate_bearing(start[0], start[1], end[0], end[1])


def calculate_line_midpoint(coordinates: List[List[float]]) -> Tuple[float, float]:
    """Calculate the midpoint of a line (by distance, not index).

    Args:
        coordinates: List of [lon, lat] coordinate pairs

    Returns:
        (lon, lat) tuple of midpoint
    """
    if len(coordinates) < 2:
        if coordinates:
            return (coordinates[0][0], coordinates[0][1])
        return (0.0, 0.0)

    total_length = calculate_line_length(coordinates)
    if total_length < 0.001:
        mid_idx = len(coordinates) // 2
        return (coordinates[mid_idx][0], coordinates[mid_idx][1])

    half_length = total_length / 2
    cumulative = 0.0

    for i in range(len(coordinates) - 1):
        lon1, lat1 = coordinates[i][0], coordinates[i][1]
        lon2, lat2 = coordinates[i + 1][0], coordinates[i + 1][1]
        segment_length = haversine_distance(lon1, lat1, lon2, lat2)

        if cumulative + segment_length >= half_length:
            # Midpoint is on this segment
            remaining = half_length - cumulative
            ratio = remaining / segment_length if segment_length > 0 else 0
            mid_lon = lon1 + ratio * (lon2 - lon1)
            mid_lat = lat1 + ratio * (lat2 - lat1)
            return (mid_lon, mid_lat)

        cumulative += segment_length

    # Fallback to endpoint
    return (coordinates[-1][0], coordinates[-1][1])
