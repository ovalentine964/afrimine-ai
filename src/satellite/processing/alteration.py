"""
Alteration Mapping Module

Generates alteration heatmaps and classifies alteration zones
from spectral indices. Core mineral exploration workflow.
"""
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
from scipy import ndimage

from .band_math import BandMathEngine, SpectralIndex
from ..utils.config import OUTPUT_DIR, ALTERATION_COLORMAPS
from ..utils.helpers import normalize_array

logger = logging.getLogger("afrimine.satellite.alteration")


class AlterationMapper:
    """
    Maps hydrothermal alteration from Sentinel-2 spectral indices.

    Alteration assemblages detected:
    - Phyllic (sericite/pyrite): strong clay + moderate iron oxide
    - Argillic (kaolinite/illite): strong clay, weak iron oxide
    - Propylitic (chlorite/epidote): chlorite index
    - Silicification: silica index
    - Iron oxide cap (gossan): strong iron oxide
    """

    def __init__(self, band_math: BandMathEngine = None):
        self.engine = band_math or BandMathEngine()
        self.output_dir = OUTPUT_DIR / "alteration"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def compute_indices(self, data: np.ndarray) -> Dict[str, SpectralIndex]:
        """Compute all alteration-relevant spectral indices."""
        return self.engine.compute_all(data)

    def classify_alteration_zones(self, indices: Dict[str, SpectralIndex],
                                  thresholds: Dict[str, float] = None) -> np.ndarray:
        """
        Classify pixels into alteration zone types.

        Args:
            indices: Dict of computed spectral indices
            thresholds: Custom threshold values for classification

        Returns:
            Integer array where:
            0 = unaltered
            1 = iron oxide cap (gossan)
            2 = phyllic alteration
            3 = argillic alteration
            4 = propylitic alteration
            5 = silicification
        """
        thresholds = thresholds or {
            "iron_oxide_high": 0.7,
            "iron_oxide_low": 0.4,
            "clay_high": 0.65,
            "clay_low": 0.4,
            "chlorite_high": 0.6,
            "silica_high": 0.65,
        }

        io = indices["iron_oxide"].normalized
        clay = indices["clay_mineral"].normalized
        chlorite = indices["chlorite"].normalized
        silica = indices["silica"].normalized

        # Initialize as unaltered
        classification = np.zeros_like(io, dtype=np.uint8)

        # Propylitic (chlorite-rich)
        mask_prop = chlorite >= thresholds["chlorite_high"]
        classification[mask_prop] = 4

        # Argillic (clay-rich, low iron)
        mask_arg = (
            (clay >= thresholds["clay_high"]) &
            (io < thresholds["iron_oxide_low"])
        )
        classification[mask_arg] = 3

        # Phyllic (clay + moderate iron)
        mask_phyl = (
            (clay >= thresholds["clay_low"]) &
            (io >= thresholds["iron_oxide_low"]) &
            (io < thresholds["iron_oxide_high"])
        )
        classification[mask_phyl] = 2

        # Silicification
        mask_sil = silica >= thresholds["silica_high"]
        classification[mask_sil] = 5

        # Iron oxide cap (gossan) — highest priority
        mask_gossan = io >= thresholds["iron_oxide_high"]
        classification[mask_gossan] = 1

        # Statistics
        total = classification.size
        for zone_id, zone_name in enumerate([
            "unaltered", "gossan", "phyllic", "argillic", "propylitic", "silicified"
        ]):
            count = np.sum(classification == zone_id)
            pct = 100 * count / total if total > 0 else 0
            logger.info(f"  {zone_name}: {count} pixels ({pct:.1f}%)")

        return classification

    def compute_alteration_intensity(self, indices: Dict[str, SpectralIndex],
                                     weights: Dict[str, float] = None) -> np.ndarray:
        """
        Compute weighted alteration intensity score (0-1).

        Combines multiple indices into a single "how altered is this pixel" score.
        Useful for prospectivity mapping.
        """
        weights = weights or {
            "iron_oxide": 0.30,
            "clay_mineral": 0.25,
            "silica": 0.20,
            "chlorite": 0.15,
            "ndvi": 0.10,  # vegetation stress as secondary indicator
        }

        intensity = np.zeros_like(list(indices.values())[0].data, dtype=np.float32)
        total_weight = 0.0

        for name, weight in weights.items():
            if name in indices and indices[name].normalized is not None:
                # For NDVI, low values indicate stress → invert
                if name == "ndvi":
                    intensity += weight * (1.0 - indices[name].normalized)
                else:
                    intensity += weight * indices[name].normalized
                total_weight += weight

        if total_weight > 0:
            intensity /= total_weight

        logger.info(
            f"Alteration intensity: min={intensity.min():.3f}, "
            f"max={intensity.max():.3f}, mean={intensity.mean():.3f}"
        )
        return intensity

    def detect_anomalies(self, intensity: np.ndarray,
                         method: str = "mean_std",
                         n_std: float = 2.0) -> Tuple[np.ndarray, float]:
        """
        Detect anomalous alteration zones.

        Args:
            intensity: Alteration intensity array
            method: 'mean_std' or 'percentile'
            n_std: Number of standard deviations for threshold

        Returns:
            Tuple of (anomaly_mask, threshold_value)
        """
        if method == "mean_std":
            mean = np.nanmean(intensity)
            std = np.nanstd(intensity)
            threshold = mean + n_std * std
        elif method == "percentile":
            threshold = np.nanpercentile(intensity, 95)
        else:
            raise ValueError(f"Unknown method: {method}")

        anomaly_mask = intensity >= threshold
        n_anomalies = np.sum(anomaly_mask)
        logger.info(
            f"Anomaly detection ({method}): threshold={threshold:.3f}, "
            f"anomalous pixels={n_anomalies} ({100*n_anomalies/intensity.size:.1f}%)"
        )
        return anomaly_mask, threshold

    def focal_statistics(self, data: np.ndarray,
                         kernel_size: int = 5,
                         stat: str = "mean") -> np.ndarray:
        """
        Apply focal (moving window) statistics.

        Useful for smoothing indices before anomaly detection.
        """
        kernel = np.ones((kernel_size, kernel_size)) / (kernel_size ** 2)

        if stat == "mean":
            return ndimage.uniform_filter(data, size=kernel_size)
        elif stat == "median":
            return ndimage.median_filter(data, size=kernel_size)
        elif stat == "std":
            mean = ndimage.uniform_filter(data, size=kernel_size)
            mean_sq = ndimage.uniform_filter(data ** 2, size=kernel_size)
            return np.sqrt(mean_sq - mean ** 2)
        else:
            raise ValueError(f"Unknown stat: {stat}")

    def save_indices_geotiff(self, indices: Dict[str, SpectralIndex],
                             transform, crs,
                             filename: str = "alteration_indices.tif"):
        """
        Save all spectral indices as a multi-band GeoTIFF.
        """
        import rasterio

        bands = []
        band_names = []
        for name, idx in indices.items():
            if idx.normalized is not None:
                bands.append(idx.normalized)
                band_names.append(name)

        stacked = np.stack(bands, axis=0)
        path = self.output_dir / filename

        profile = {
            "driver": "GTiff",
            "dtype": "float32",
            "width": stacked.shape[2],
            "height": stacked.shape[1],
            "count": stacked.shape[0],
            "crs": crs,
            "transform": transform,
            "compress": "lzw",
        }

        with rasterio.open(path, "w", **profile) as dst:
            for i, name in enumerate(band_names):
                dst.write(stacked[i], i + 1)
                dst.set_band_description(i + 1, name)

        logger.info(f"Saved alteration indices: {path}")
        return path

    def generate_report(self, indices: Dict[str, SpectralIndex],
                        classification: np.ndarray,
                        intensity: np.ndarray,
                        region_name: str = "Unknown") -> str:
        """
        Generate text summary of alteration mapping results.
        """
        zone_names = {
            0: "Unaltered", 1: "Gossan (Iron Cap)", 2: "Phyllic",
            3: "Argillic", 4: "Propylitic", 5: "Silicified"
        }

        total = classification.size
        report_lines = [
            f"ALTERATION MAPPING REPORT — {region_name}",
            "=" * 50,
            "",
            "Spectral Index Statistics:",
            "-" * 30,
        ]

        for name, idx in indices.items():
            d = idx.data
            report_lines.append(
                f"  {name:15s} | min={np.nanmin(d):.4f}  "
                f"max={np.nanmax(d):.4f}  mean={np.nanmean(d):.4f}  "
                f"std={np.nanstd(d):.4f}"
            )

        report_lines.extend(["", "Alteration Zone Classification:", "-" * 30])

        for zone_id, zone_name in zone_names.items():
            count = np.sum(classification == zone_id)
            pct = 100 * count / total
            report_lines.append(f"  {zone_name:20s}: {count:>8d} pixels ({pct:5.1f}%)")

        report_lines.extend([
            "",
            "Alteration Intensity:",
            "-" * 30,
            f"  Mean:   {np.nanmean(intensity):.4f}",
            f"  Max:    {np.nanmax(intensity):.4f}",
            f"  Std:    {np.nanstd(intensity):.4f}",
            "",
        ])

        report = "\n".join(report_lines)
        logger.info(f"\n{report}")
        return report
