"""
Sentinel-2 imagery downloader from Google Earth Engine.

Downloads, clips, and caches satellite imagery for specified Kenyan mining regions.
"""
import logging
import time
from pathlib import Path
from typing import Tuple, List, Optional, Dict
from datetime import datetime

import numpy as np

# Lazy ee import — module works in offline mode without it
try:
    import ee
    EE_AVAILABLE = True
except ImportError:
    ee = None  # type: ignore
    EE_AVAILABLE = False

from ..utils.config import (
    SentinelConfig, CACHE_DIR, OUTPUT_DIR, KenyaBounds
)
from ..utils.helpers import (
    bbox_to_ee_geometry, mask_clouds_s2, cache_key, get_cached, date_range
)

logger = logging.getLogger("afrimine.satellite.downloader")

# Retry configuration for network requests
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # seconds, exponential backoff


class SentinelDownloader:
    """
    Downloads Sentinel-2 Surface Reflectance imagery from Google Earth Engine.

    Features:
    - Cloud masking via QA60 band
    - Median composite for date ranges
    - Local GeoTIFF caching
    - Support for all Kenyan mining regions
    """

    def __init__(self, config: SentinelConfig = None):
        if not EE_AVAILABLE:
            raise RuntimeError(
                "earthengine-api not installed. Cannot create SentinelDownloader. "
                "Use offline mode or install: pip install earthengine-api"
            )
        self.config = config or SentinelConfig()
        self.collection = self.config.COLLECTION
        self.cache_dir = CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_collection(self, bbox: Tuple[float, float, float, float],
                       start_date: str, end_date: str,
                       max_cloud: float = None) -> ee.ImageCollection:
        """
        Get filtered Sentinel-2 ImageCollection.

        Args:
            bbox: (west, south, east, north) bounding box
            start_date: Start date string (YYYY-MM-DD)
            end_date: End date string (YYYY-MM-DD)
            max_cloud: Maximum cloud cover percentage

        Returns:
            Filtered ee.ImageCollection
        """
        max_cloud = max_cloud or self.config.MAX_CLOUD_COVER
        region = bbox_to_ee_geometry(bbox)

        collection = (
            ee.ImageCollection(self.collection)
            .filterBounds(region)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
        )

        count = collection.size().getInfo()
        logger.info(
            f"Found {count} Sentinel-2 images "
            f"({start_date} to {end_date}, cloud<{max_cloud}%)"
        )
        return collection

    def download_composite(self, bbox: Tuple[float, float, float, float],
                           start_date: str, end_date: str,
                           bands: List[str] = None,
                           max_cloud: float = None,
                           apply_cloud_mask: bool = True,
                           scale: int = None) -> Dict:
        """
        Download median composite as NumPy array + metadata.

        Args:
            bbox: Bounding box (west, south, east, north)
            start_date: Start date
            end_date: End date
            bands: List of band names (default: config bands)
            max_cloud: Max cloud cover
            apply_cloud_mask: Whether to apply QA60 cloud mask
            scale: Pixel resolution in meters

        Returns:
            Dict with keys: 'data' (ndarray), 'transform', 'crs', 'bounds', 'bands'
        """
        bands = bands or self.config.BANDS
        scale = scale or self.config.SCALE

        # Check cache
        params = {
            "bbox": bbox, "start": start_date, "end": end_date,
            "bands": sorted(bands), "scale": scale, "cloud_mask": apply_cloud_mask
        }
        cid = cache_key(params)
        cached = get_cached(cid, self.cache_dir)
        if cached:
            return self._load_cached(cached)

        collection = self.get_collection(bbox, start_date, end_date, max_cloud)

        if apply_cloud_mask:
            collection = collection.map(mask_clouds_s2)

        # Select bands and create median composite
        composite = collection.select(bands).median()

        # Clip to region
        region = bbox_to_ee_geometry(bbox)
        composite = composite.clip(region)

        # Download as numpy array
        result = self._download_array(composite, region, scale, bands)

        # Cache
        self._save_cache(result, cid)

        return result

    def download_single(self, image_id: str,
                        bands: List[str] = None,
                        bbox: Tuple[float, float, float, float] = None,
                        scale: int = None) -> Dict:
        """
        Download a single Sentinel-2 image by ID.

        Args:
            image_id: GEE image ID (e.g., 'COPERNICUS/S2_SR_HARMONIZED/20240101T...')
            bands: Band names to download
            bbox: Optional clipping region
            scale: Pixel resolution

        Returns:
            Dict with array data and metadata
        """
        bands = bands or self.config.BANDS
        scale = scale or self.config.SCALE

        image = ee.Image(image_id).select(bands).divide(10000)

        if bbox:
            region = bbox_to_ee_geometry(bbox)
            image = image.clip(region)
        else:
            region = image.geometry()

        return self._download_array(image, region, scale, bands)

    def _download_array(self, image: ee.Image, region: ee.Geometry,
                        scale: int, bands: List[str]) -> Dict:
        """
        Download ee.Image as NumPy array via getInfo/getDownloadURL.
        Includes retry logic for transient network failures.
        """
        logger.info(f"Downloading {len(bands)} bands at {scale}m resolution...")

        # Use getDownloadURL for manageable sizes
        try:
            url = image.getDownloadURL({
                "region": region,
                "scale": scale,
                "format": "GEO_TIFF",
                "filePerBand": False,
            })

            import requests
            import rasterio
            from io import BytesIO

            # Retry with exponential backoff
            response = None
            for attempt in range(MAX_RETRIES):
                try:
                    response = requests.get(url, timeout=300)
                    response.raise_for_status()
                    break
                except requests.exceptions.RequestException as e:
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAY_BASE ** (attempt + 1)
                        logger.warning(
                            f"Download attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        raise

            with rasterio.open(BytesIO(response.content)) as src:
                data = src.read()
                transform = src.transform
                crs = src.crs
                bounds = src.bounds

            logger.info(
                f"Downloaded: shape={data.shape}, "
                f"crs={crs}, bounds={bounds}"
            )

            return {
                "data": data,
                "transform": transform,
                "crs": crs,
                "bounds": bounds,
                "bands": bands,
                "shape": data.shape,
            }

        except Exception as e:
            logger.warning(f"getDownloadURL failed ({e}), trying getInfo()...")
            return self._download_via_info(image, region, scale, bands)

    def _download_via_info(self, image: ee.Image, region: ee.Geometry,
                           scale: int, bands: List[str]) -> Dict:
        """
        Fallback: download pixel values via getInfo (for smaller regions).
        Includes retry logic for network failures.
        """
        sample = image.sampleRectangle(region=region, defaultValue=0)

        result = {}
        for band in bands:
            for attempt in range(MAX_RETRIES):
                try:
                    band_data = sample.get(band).getInfo()
                    result[band] = np.array(band_data, dtype=np.float32)
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAY_BASE ** (attempt + 1)
                        logger.warning(
                            f"getInfo() attempt {attempt + 1} for band {band} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        raise RuntimeError(
                            f"Failed to download band {band} after {MAX_RETRIES} attempts: {e}"
                        ) from e

        # Stack bands
        stacked = np.stack([result[b] for b in bands], axis=0)

        # Get transform from bounds
        bounds = region.bounds().getInfo()["coordinates"][0]
        west = min(p[0] for p in bounds)
        east = max(p[0] for p in bounds)
        south = min(p[1] for p in bounds)
        north = max(p[1] for p in bounds)

        h, w = stacked.shape[1], stacked.shape[2]
        from rasterio.transform import from_bounds
        transform = from_bounds(west, south, east, north, w, h)

        return {
            "data": stacked,
            "transform": transform,
            "crs": "EPSG:4326",
            "bounds": (west, south, east, north),
            "bands": bands,
            "shape": stacked.shape,
        }

    def _load_cached(self, path: Path) -> Dict:
        """Load cached GeoTIFF."""
        import rasterio
        with rasterio.open(path) as src:
            data = src.read()
            return {
                "data": data,
                "transform": src.transform,
                "crs": src.crs,
                "bounds": src.bounds,
                "bands": [f"B{i+1}" for i in range(data.shape[0])],
                "shape": data.shape,
            }

    def _save_cache(self, result: Dict, cache_id: str):
        """Save result to GeoTIFF cache."""
        import rasterio
        from rasterio.crs import CRS

        path = self.cache_dir / f"{cache_id}.tif"
        data = result["data"]

        crs = result["crs"]
        if isinstance(crs, str):
            crs = CRS.from_string(crs)

        profile = {
            "driver": "GTiff",
            "dtype": data.dtype,
            "width": data.shape[2],
            "height": data.shape[1],
            "count": data.shape[0],
            "crs": crs,
            "transform": result["transform"],
            "compress": "lzw",
        }

        with rasterio.open(path, "w", **profile) as dst:
            for i in range(data.shape[0]):
                dst.write(data[i], i + 1)
                dst.set_band_description(i + 1, result["bands"][i])

        logger.info(f"Cached GeoTIFF: {path} ({path.stat().st_size / 1e6:.1f} MB)")

    def list_available_images(self, bbox: Tuple[float, float, float, float],
                              start_date: str, end_date: str,
                              max_cloud: float = None) -> List[Dict]:
        """
        List available Sentinel-2 images with metadata.
        """
        max_cloud = max_cloud or self.config.MAX_CLOUD_COVER
        collection = self.get_collection(bbox, start_date, end_date, max_cloud)

        # Get metadata with retry
        def extract_metadata(image):
            props = image.toDictionary()
            return ee.Feature(None, {
                "id": image.id(),
                "date": image.date().format("YYYY-MM-dd"),
                "cloud_cover": props.get("CLOUDY_PIXEL_PERCENTAGE"),
                "solar_zenith": props.get("MEAN_SOLAR_ZENITH_ANGLE"),
            })

        for attempt in range(MAX_RETRIES):
            try:
                features = collection.map(extract_metadata).getInfo()["features"]
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY_BASE ** (attempt + 1)
                    logger.warning(f"list_available_images attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    raise

        images = [
            {
                "id": f["properties"]["id"],
                "date": f["properties"]["date"],
                "cloud_cover": f["properties"]["cloud_cover"],
            }
            for f in features
        ]

        logger.info(f"Listed {len(images)} available images")
        return images


def download_region_data(region_name: str,
                         start_date: str = None,
                         end_date: str = None,
                         bands: List[str] = None) -> Dict:
    """
    Convenience function: download imagery for a named Kenyan region.

    Args:
        region_name: One of 'turkana', 'kwale', 'migori', 'taita', 'homa_bay'
        start_date: Start date (default: 30 days ago)
        end_date: End date (default: today)
        bands: Bands to download

    Returns:
        Downloaded data dict

    Raises:
        RuntimeError: If earthengine-api is not installed
        ValueError: If region_name is unknown
    """
    if not EE_AVAILABLE:
        raise RuntimeError(
            "earthengine-api not installed. Cannot download region data. "
            "Use offline mode or install: pip install earthengine-api"
        )

    regions = {
        "turkana": KenyaBounds.TURKANA,
        "kwale": KenyaBounds.KWALE,
        "migori": KenyaBounds.MIGORI,
        "taita": KenyaBounds.TAITA,
        "homa_bay": KenyaBounds.HOMA_BAY,
    }

    if region_name.lower() not in regions:
        raise ValueError(f"Unknown region: {region_name}. Choose from: {list(regions.keys())}")

    bbox = regions[region_name.lower()]

    if not start_date or not end_date:
        start_date, end_date = date_range(30)

    downloader = SentinelDownloader()
    return downloader.download_composite(
        bbox=bbox,
        start_date=start_date,
        end_date=end_date,
        bands=bands,
    )
