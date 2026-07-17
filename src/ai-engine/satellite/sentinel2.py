"""
AfriMine AI — Sentinel-2 Satellite Image Processing
Processes Sentinel-2 multispectral imagery for mineral exploration.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# Sentinel-2 band definitions
SENTINEL2_BANDS = {
    "B02": {"name": "Blue", "wavelength_nm": 490, "resolution_m": 10},
    "B03": {"name": "Green", "wavelength_nm": 560, "resolution_m": 10},
    "B04": {"name": "Red", "wavelength_nm": 665, "resolution_m": 10},
    "B05": {"name": "Red Edge 1", "wavelength_nm": 705, "resolution_m": 20},
    "B06": {"name": "Red Edge 2", "wavelength_nm": 740, "resolution_m": 20},
    "B07": {"name": "Red Edge 3", "wavelength_nm": 783, "resolution_m": 20},
    "B08": {"name": "NIR", "wavelength_nm": 842, "resolution_m": 10},
    "B8A": {"name": "NIR Narrow", "wavelength_nm": 865, "resolution_m": 20},
    "B11": {"name": "SWIR 1", "wavelength_nm": 1610, "resolution_m": 20},
    "B12": {"name": "SWIR 2", "wavelength_nm": 2190, "resolution_m": 20},
}


class Sentinel2Processor:
    """
    Process Sentinel-2 multispectral imagery for mineral exploration.
    Computes spectral indices relevant to mineral detection.
    """

    def __init__(self, resolution_m: int = 10):
        self.resolution_m = resolution_m
        self.bands = {}

    def load_bands(self, band_data: dict[str, np.ndarray]):
        """
        Load band arrays.
        band_data: {band_name: 2D numpy array}
        """
        self.bands = band_data
        logger.info(f"Loaded {len(band_data)} bands: {list(band_data.keys())}")

    def load_from_directory(self, directory: str):
        """Load bands from a directory of GeoTIFF files."""
        try:
            import rasterio
        except ImportError:
            logger.warning("rasterio not installed — cannot load GeoTIFF")
            return

        dir_path = Path(directory)
        for band_name in SENTINEL2_BANDS:
            for ext in [".tif", ".jp2", ".TIF", ".JP2"]:
                candidates = list(dir_path.glob(f"*{band_name}*{ext}"))
                if candidates:
                    with rasterio.open(candidates[0]) as src:
                        self.bands[band_name] = src.read(1).astype(np.float32)
                    break

        logger.info(f"Loaded {len(self.bands)} bands from {directory}")

    def compute_ndvi(self) -> np.ndarray:
        """Normalized Difference Vegetation Index."""
        if "B08" in self.bands and "B04" in self.bands:
            nir = self.bands["B08"].astype(float)
            red = self.bands["B04"].astype(float)
            return np.where((nir + red) > 0, (nir - red) / (nir + red), 0)
        raise ValueError("NDVI requires B08 (NIR) and B04 (Red) bands")

    def compute_ndmi(self) -> np.ndarray:
        """Normalized Difference Moisture Index."""
        if "B08" in self.bands and "B11" in self.bands:
            nir = self.bands["B08"].astype(float)
            swir = self.bands["B11"].astype(float)
            return np.where((nir + swir) > 0, (nir - swir) / (nir + swir), 0)
        raise ValueError("NDMI requires B08 (NIR) and B11 (SWIR1) bands")

    def compute_ferric_iron(self) -> np.ndarray:
        """
        Ferric Iron Index — detects iron oxide minerals (hematite, goethite).
        High values indicate iron-rich surface materials.
        """
        if "B04" in self.bands and "B02" in self.bands:
            red = self.bands["B04"].astype(float)
            blue = self.bands["B02"].astype(float)
            return np.where((red + blue) > 0, red / blue, 0)
        raise ValueError("Ferric iron index requires B04 and B02")

    def compute_clay_minerals(self) -> np.ndarray:
        """
        Clay Mineral Index — detects clay alteration (kaolinite, illite).
        Uses SWIR bands sensitive to Al-OH and Mg-OH absorption.
        """
        if "B11" in self.bands and "B12" in self.bands:
            swir1 = self.bands["B11"].astype(float)
            swir2 = self.bands["B12"].astype(float)
            return np.where((swir1 + swir2) > 0, (swir1 - swir2) / (swir1 + swir2), 0)
        raise ValueError("Clay mineral index requires B11 and B12")

    def compute_iron_oxide_ratio(self) -> np.ndarray:
        """Iron Oxide Ratio — B11/B04 for laterite detection."""
        if "B11" in self.bands and "B04" in self.bands:
            swir = self.bands["B11"].astype(float)
            red = self.bands["B04"].astype(float)
            return np.where(red > 0, swir / red, 0)
        raise ValueError("Iron oxide ratio requires B11 and B04")

    def compute_silica_index(self) -> np.ndarray:
        """Silica Index — detects quartz-rich areas."""
        if "B11" in self.bands and "B08" in self.bands:
            swir = self.bands["B11"].astype(float)
            nir = self.bands["B08"].astype(float)
            return np.where(nir > 0, swir / nir, 0)
        raise ValueError("Silica index requires B11 and B08")

    def compute_alteration_indices(self) -> dict[str, np.ndarray]:
        """Compute all mineral alteration indices at once."""
        indices = {}
        try:
            indices["ndvi"] = self.compute_ndvi()
        except ValueError:
            pass
        try:
            indices["ndmi"] = self.compute_ndmi()
        except ValueError:
            pass
        try:
            indices["ferric_iron"] = self.compute_ferric_iron()
        except ValueError:
            pass
        try:
            indices["clay_minerals"] = self.compute_clay_minerals()
        except ValueError:
            pass
        try:
            indices["iron_oxide_ratio"] = self.compute_iron_oxide_ratio()
        except ValueError:
            pass
        try:
            indices["silica_index"] = self.compute_silica_index()
        except ValueError:
            pass

        logger.info(f"Computed {len(indices)} alteration indices")
        return indices

    def detect_alteration_zones(
        self,
        indices: Optional[dict[str, np.ndarray]] = None,
        threshold_percentile: float = 85,
    ) -> dict:
        """
        Detect potential mineral alteration zones from spectral indices.

        Returns:
            {zones, indices, statistics}
        """
        if indices is None:
            indices = self.compute_alteration_indices()

        zones = {}
        stats = {}

        for name, idx_array in indices.items():
            threshold = np.percentile(idx_array[~np.isnan(idx_array)], threshold_percentile)
            anomaly_mask = idx_array > threshold
            zones[name] = anomaly_mask
            stats[name] = {
                "mean": float(np.nanmean(idx_array)),
                "std": float(np.nanstd(idx_array)),
                "threshold": float(threshold),
                "anomaly_pixels": int(np.sum(anomaly_mask)),
                "anomaly_pct": float(np.sum(anomaly_mask) / anomaly_mask.size * 100),
            }

        # Composite alteration map: areas anomalous in multiple indices
        if len(zones) > 1:
            composite = np.zeros_like(list(zones.values())[0], dtype=int)
            for mask in zones.values():
                composite += mask.astype(int)
            composite_mask = composite >= max(2, len(zones) // 2)
            zones["composite_alteration"] = composite_mask
            stats["composite"] = {
                "anomaly_pixels": int(np.sum(composite_mask)),
                "anomaly_pct": float(np.sum(composite_mask) / composite_mask.size * 100),
                "multi_index_threshold": max(2, len(zones) // 2),
            }

        return {
            "zones": zones,
            "statistics": stats,
            "recommendation": self._zone_recommendation(stats),
        }

    def _zone_recommendation(self, stats: dict) -> str:
        """Generate recommendation based on detected alteration zones."""
        anomaly_indices = []
        for name, s in stats.items():
            if name != "composite" and s.get("anomaly_pct", 0) > 5:
                anomaly_indices.append(name)

        if not anomaly_indices:
            return "No significant alteration zones detected — area may lack surface mineral expression"

        recommendations = []
        if "ferric_iron" in anomaly_indices:
            recommendations.append("Iron oxide anomalies detected — potential for hematite/goethite or associated gold")
        if "clay_minerals" in anomaly_indices:
            recommendations.append("Clay alteration detected — potential hydrothermal system indicator")
        if "silica_index" in anomaly_indices:
            recommendations.append("Silica enrichment detected — potential silicification zones")

        return ". ".join(recommendations) + ". Recommend ground-truthing with field sampling."

    def extract_pixel_spectrum(self, row: int, col: int) -> dict:
        """Extract spectral signature at a specific pixel location."""
        spectrum = {}
        for band_name, band_data in self.bands.items():
            if row < band_data.shape[0] and col < band_data.shape[1]:
                spectrum[band_name] = float(band_data[row, col])
        return {
            "location": {"row": row, "col": col},
            "spectrum": spectrum,
            "band_info": {k: SENTINEL2_BANDS.get(k, {}) for k in spectrum},
        }

    def save_indices_geotiff(self, indices: dict[str, np.ndarray], output_dir: str, reference_profile: Optional[dict] = None):
        """Save computed indices as GeoTIFF files."""
        try:
            import rasterio
            from rasterio.transform import from_bounds
        except ImportError:
            logger.warning("rasterio not installed — saving as numpy arrays")
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            for name, arr in indices.items():
                np.save(str(out_dir / f"{name}.npy"), arr)
            return

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        for name, arr in indices.items():
            path = out_dir / f"{name}.tif"
            if reference_profile:
                profile = reference_profile.copy()
                profile.update(dtype="float32", count=1, driver="GTiff")
                with rasterio.open(str(path), "w", **profile) as dst:
                    dst.write(arr.astype(np.float32), 1)
            else:
                # Save without georeference
                with rasterio.open(
                    str(path), "w", driver="GTiff",
                    height=arr.shape[0], width=arr.shape[1],
                    count=1, dtype="float32",
                ) as dst:
                    dst.write(arr.astype(np.float32), 1)

        logger.info(f"Saved {len(indices)} index files to {output_dir}")
