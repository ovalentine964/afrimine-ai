"""
Spatial utility functions: coordinate transforms, distance calcs, geometry ops.
"""
from typing import Tuple, List, Optional
import numpy as np


def haversine_distance(lat1: float, lon1: float,
                       lat2: float, lon2: float) -> float:
    """Haversine distance between two points in meters."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = (np.sin(dphi / 2) ** 2 +
         np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2)
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def pixel_to_geo(col: int, row: int, transform) -> Tuple[float, float]:
    """Convert pixel (col, row) to geographic coordinates."""
    x = transform.c + col * transform.a + row * transform.b
    y = transform.f + col * transform.d + row * transform.e
    return x, y


def geo_to_pixel(x: float, y: float, transform) -> Tuple[int, int]:
    """Convert geographic coordinates to pixel (col, row)."""
    from rasterio.transform import rowcol
    row, col = rowcol(transform, x, y)
    return int(col), int(row)


def create_buffer_geometry(center: Tuple[float, float],
                           radius_m: float) -> dict:
    """Create circular buffer geometry around a point (lon, lat)."""
    from shapely.geometry import Point
    from shapely.ops import transform as shapely_transform
    from functools import partial
    import pyproj

    point = Point(center[0], center[1])
    # Project to UTM for metric buffer
    proj_wgs84 = pyproj.CRS("EPSG:4326")
    # Determine UTM zone
    utm_zone = int((center[0] + 180) / 6) + 1
    hemisphere = "north" if center[1] >= 0 else "south"
    utm_crs = pyproj.CRS(f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84")

    project_to_utm = pyproj.Transformer.from_crs(
        proj_wgs84, utm_crs, always_xy=True
    ).transform
    project_to_wgs = pyproj.Transformer.from_crs(
        utm_crs, proj_wgs84, always_xy=True
    ).transform

    point_utm = shapely_transform(project_to_utm, point)
    buffer_utm = point_utm.buffer(radius_m)
    buffer_wgs = shapely_transform(project_to_wgs, buffer_utm)

    from shapely.geometry import mapping
    return mapping(buffer_wgs)


def points_within_distance(points: np.ndarray,
                           target: Tuple[float, float],
                           max_distance_m: float) -> np.ndarray:
    """Return boolean mask of points within distance of target."""
    distances = np.array([
        haversine_distance(p[1], p[0], target[1], target[0])
        for p in points
    ])
    return distances <= max_distance_m


def compute_lineament_orientation(dx: float, dy: float) -> float:
    """Compute orientation angle of a lineament in degrees (0-180)."""
    angle = np.degrees(np.arctan2(dy, dx)) % 180
    return angle
