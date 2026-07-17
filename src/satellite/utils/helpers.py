"""
Shared helper functions for the satellite pipeline.
"""
import logging
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any

import numpy as np

from .config import CACHE_DIR, OUTPUT_DIR

logger = logging.getLogger("afrimine.satellite")


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure logging for the satellite pipeline."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logger


def bbox_to_geometry(bbox: Tuple[float, float, float, float]) -> Dict:
    """
    Convert bounding box (west, south, east, north) to GeoJSON geometry.
    """
    west, south, east, north = bbox
    return {
        "type": "Polygon",
        "coordinates": [[
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south],
        ]],
    }


def bbox_to_ee_geometry(bbox: Tuple[float, float, float, float]):
    """Convert bounding box to Earth Engine geometry."""
    try:
        import ee
    except ImportError:
        raise RuntimeError(
            "earthengine-api not installed. Cannot create EE geometry. "
            "Install with: pip install earthengine-api"
        )
    return ee.Geometry.Rectangle([bbox[0], bbox[1], bbox[2], bbox[3]])


def cache_key(params: Dict[str, Any]) -> str:
    """Generate deterministic cache key from parameters."""
    serialized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode()).hexdigest()


def get_cached(cache_id: str, cache_dir: Path = CACHE_DIR) -> Optional[Path]:
    """Check if a cached file exists."""
    cache_path = cache_dir / f"{cache_id}.tif"
    if cache_path.exists():
        logger.info(f"Cache hit: {cache_path}")
        return cache_path
    return None


def save_to_cache(data: np.ndarray, profile: Dict, cache_id: str,
                  cache_dir: Path = CACHE_DIR) -> Path:
    """Save raster data to cache."""
    import rasterio
    cache_path = cache_dir / f"{cache_id}.tif"
    with rasterio.open(cache_path, "w", **profile) as dst:
        if data.ndim == 2:
            dst.write(data, 1)
        else:
            for i in range(data.shape[0]):
                dst.write(data[i], i + 1)
    logger.info(f"Cached: {cache_path}")
    return cache_path


def safe_divide(numerator: np.ndarray, denominator: np.ndarray,
                fill_value: float = 0.0) -> np.ndarray:
    """Division that handles zeros without RuntimeWarning."""
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(denominator != 0, numerator / denominator, fill_value)
    return result.astype(np.float32)


def normalize_array(arr: np.ndarray, low: float = 0.02, high: float = 0.98) -> np.ndarray:
    """Normalize array using percentile stretching."""
    p_low = np.nanpercentile(arr, low * 100)
    p_high = np.nanpercentile(arr, high * 100)
    if p_high - p_low == 0:
        return np.zeros_like(arr, dtype=np.float32)
    normalized = (arr - p_low) / (p_high - p_low)
    return np.clip(normalized, 0, 1).astype(np.float32)


def date_range(days_back: int = 30) -> Tuple[str, str]:
    """Return (start_date, end_date) string pair for recent imagery."""
    end = datetime.utcnow()
    start = end - timedelta(days=days_back)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def mask_clouds_s2(image):
    """
    Apply cloud mask to Sentinel-2 image using QA60 band.
    """
    try:
        import ee
    except ImportError:
        logger.error("earthengine-api not installed; cannot mask clouds.")
        return image
    qa = image.select("QA60")
    # Bits 10 and 11 are clouds and cirrus
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = (
        qa.bitwiseAnd(cloud_bit_mask).eq(0)
        .And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    )
    return image.updateMask(mask).divide(10000)


def print_banner():
    """Print startup banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║           AfriMine AI — Satellite Analysis Pipeline          ║
║       Mineral Detection for Kenyan Mining Families          ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)
