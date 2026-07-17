"""
Change Detection Module

Compares satellite imagery from different dates to detect:
- Mining activity expansion
- Vegetation loss (deforestation from artisanal mining)
- New tailings ponds
- Land surface changes
"""
import logging
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from ..utils.config import OUTPUT_DIR
from ..utils.helpers import normalize_array, safe_divide

logger = logging.getLogger("afrimine.satellite.change_detection")


@dataclass
class ChangeResult:
    """Container for change detection results."""
    change_magnitude: np.ndarray     # Overall change intensity
    change_direction: np.ndarray     # Positive/negative change
    binary_mask: np.ndarray          # Significant change mask
    ndvi_change: Optional[np.ndarray] = None
    statistics: Dict = None


class ChangeDetector:
    """
    Multi-temporal change detection for monitoring mining activity.

    Methods:
    - Image differencing (band-by-band)
    - NDVI change (vegetation loss detection)
    - Ratio-based change detection
    - Chi-square change detection
    - Binary change map generation
    """

    def __init__(self, output_dir=None):
        self.output_dir = output_dir or (OUTPUT_DIR / "change_detection")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def image_differencing(self, image_before: np.ndarray,
                           image_after: np.ndarray) -> np.ndarray:
        """
        Simple image differencing: after - before.

        Args:
            image_before: Multi-band image (bands, H, W) from earlier date
            image_after: Multi-band image from later date

        Returns:
            Difference array (same shape as input)
        """
        if image_before.shape != image_after.shape:
            raise ValueError(
                f"Shape mismatch: {image_before.shape} vs {image_after.shape}"
            )

        diff = image_after.astype(np.float32) - image_before.astype(np.float32)

        logger.info(
            f"Image differencing: mean_abs_diff={np.mean(np.abs(diff)):.4f}"
        )
        return diff

    def ratio_change(self, image_before: np.ndarray,
                     image_after: np.ndarray,
                     epsilon: float = 1e-6) -> np.ndarray:
        """
        Ratio-based change: after / (before + epsilon).

        More robust to illumination differences than simple differencing.
        Values > 1 indicate increase, < 1 indicate decrease.
        """
        ratio = (image_after + epsilon) / (image_before + epsilon)

        logger.info(f"Ratio change: mean={np.mean(ratio):.4f}")
        return ratio

    def ndvi_change_detection(self, ndvi_before: np.ndarray,
                              ndvi_after: np.ndarray,
                              threshold: float = -0.15) -> ChangeResult:
        """
        Detect vegetation loss using NDVI change.

        Args:
            ndvi_before: NDVI from earlier date
            ndvi_after: NDVI from later date
            threshold: Negative threshold for significant vegetation loss

        Returns:
            ChangeResult focused on vegetation changes
        """
        ndvi_diff = ndvi_after - ndvi_before

        # Vegetation loss: significant negative change
        veg_loss = ndvi_diff < threshold

        # Vegetation gain: significant positive change
        veg_gain = ndvi_diff > abs(threshold)

        # Statistics
        total = ndvi_diff.size
        n_loss = np.sum(veg_loss)
        n_gain = np.sum(veg_gain)

        stats = {
            "ndvi_mean_change": float(np.mean(ndvi_diff)),
            "ndvi_std_change": float(np.std(ndvi_diff)),
            "vegetation_loss_pixels": int(n_loss),
            "vegetation_loss_percent": float(100 * n_loss / total),
            "vegetation_gain_pixels": int(n_gain),
            "vegetation_gain_percent": float(100 * n_gain / total),
            "threshold": threshold,
        }

        logger.info(
            f"NDVI change: mean={stats['ndvi_mean_change']:.4f}, "
            f"veg_loss={stats['vegetation_loss_percent']:.1f}%, "
            f"veg_gain={stats['vegetation_gain_percent']:.1f}%"
        )

        return ChangeResult(
            change_magnitude=np.abs(ndvi_diff),
            change_direction=ndvi_diff,
            binary_mask=veg_loss,
            ndvi_change=ndvi_diff,
            statistics=stats,
        )

    def chi_square_change(self, image_before: np.ndarray,
                          image_after: np.ndarray,
                          window_size: int = 5) -> np.ndarray:
        """
        Chi-square change detection.

        More statistically robust than simple differencing.
        Uses local statistics within a moving window.
        """
        if image_before.ndim == 3:
            # Process each band and combine
            chi_maps = []
            for b in range(image_before.shape[0]):
                chi = self._chi_square_2d(
                    image_before[b], image_after[b], window_size
                )
                chi_maps.append(chi)
            return np.mean(chi_maps, axis=0)
        else:
            return self._chi_square_2d(image_before, image_after, window_size)

    def _chi_square_2d(self, before: np.ndarray, after: np.ndarray,
                       window: int) -> np.ndarray:
        """Chi-square distance between local distributions."""
        diff = (after - before) ** 2
        sigma_sq = ndimage.uniform_filter(
            (before - ndimage.uniform_filter(before, size=window)) ** 2,
            size=window
        )
        sigma_sq = np.maximum(sigma_sq, 1e-10)
        chi = ndimage.uniform_filter(diff, size=window) / sigma_sq
        return chi

    def comprehensive_change(self, bands_before: np.ndarray,
                             bands_after: np.ndarray,
                             ndvi_before: np.ndarray = None,
                             ndvi_after: np.ndarray = None,
                             threshold_method: str = "otsu") -> ChangeResult:
        """
        Comprehensive change detection combining multiple methods.

        Args:
            bands_before: Multi-band before image (bands, H, W)
            bands_after: Multi-band after image
            ndvi_before: Optional pre-computed NDVI
            ndvi_after: Optional pre-computed NDVI
            threshold_method: 'otsu', 'mean_std', or 'percentile'

        Returns:
            ChangeResult with combined analysis
        """
        # 1. Image differencing
        diff = self.image_differencing(bands_before, bands_after)
        diff_magnitude = np.sqrt(np.sum(diff ** 2, axis=0)) if diff.ndim == 3 else np.abs(diff)

        # 2. Ratio change
        ratio = self.ratio_change(bands_before, bands_after)
        if ratio.ndim == 3:
            ratio_magnitude = np.mean(np.abs(ratio - 1), axis=0)
        else:
            ratio_magnitude = np.abs(ratio - 1)

        # 3. Chi-square
        chi = self.chi_square_change(bands_before, bands_after)

        # Combine change indicators (normalize each to 0-1)
        norm_diff = normalize_array(diff_magnitude)
        norm_ratio = normalize_array(ratio_magnitude)
        norm_chi = normalize_array(chi)

        combined = (norm_diff + norm_ratio + norm_chi) / 3.0

        # Threshold
        if threshold_method == "otsu":
            threshold = self._otsu_threshold(combined)
        elif threshold_method == "mean_std":
            threshold = np.mean(combined) + 2 * np.std(combined)
        else:
            threshold = np.percentile(combined, 95)

        binary = combined > threshold

        # NDVI change if available
        ndvi_change = None
        ndvi_stats = {}
        if ndvi_before is not None and ndvi_after is not None:
            ndvi_result = self.ndvi_change_detection(ndvi_before, ndvi_after)
            ndvi_change = ndvi_result.ndvi_change
            ndvi_stats = ndvi_result.statistics

        stats = {
            "combined_mean": float(np.mean(combined)),
            "combined_std": float(np.std(combined)),
            "threshold": float(threshold),
            "changed_pixels": int(np.sum(binary)),
            "changed_percent": float(100 * np.sum(binary) / binary.size),
            "method": threshold_method,
            **ndvi_stats,
        }

        logger.info(
            f"Comprehensive change: {stats['changed_percent']:.1f}% changed "
            f"(threshold={threshold:.3f})"
        )

        return ChangeResult(
            change_magnitude=combined,
            change_direction=diff_magnitude,
            binary_mask=binary,
            ndvi_change=ndvi_change,
            statistics=stats,
        )

    def detect_mining_expansion(self, change_result: ChangeResult,
                                ndvi_threshold: float = -0.2,
                                area_threshold: float = 0.01) -> Dict:
        """
        Detect potential mining expansion from change results.

        Mining activity typically shows:
        - NDVI decrease (vegetation clearing)
        - Increase in bare soil exposure
        - New linear features (roads, trenches)

        Returns:
            Dict with mining expansion indicators
        """
        if change_result.ndvi_change is None:
            logger.warning("No NDVI change data available for mining detection")
            return {"mining_likely": False, "confidence": 0.0}

        ndvi_change = change_result.ndvi_change
        veg_loss_mask = ndvi_change < ndvi_threshold

        # Cluster analysis: find contiguous areas of vegetation loss
        labeled, n_clusters = ndimage.label(veg_loss_mask)

        # Filter small clusters (noise)
        min_cluster_size = int(ndvi_change.size * area_threshold)
        significant_clusters = []

        for i in range(1, n_clusters + 1):
            cluster_size = np.sum(labeled == i)
            if cluster_size >= min_cluster_size:
                cluster_mask = labeled == i
                centroid = ndimage.center_of_mass(ndvi_change, labeled, i)
                mean_change = np.mean(ndvi_change[cluster_mask])
                significant_clusters.append({
                    "id": i,
                    "size_pixels": int(cluster_size),
                    "centroid": centroid,
                    "mean_ndvi_change": float(mean_change),
                })

        # Estimate confidence
        total_loss_area = np.sum(veg_loss_mask) / ndvi_change.size
        confidence = min(total_loss_area * 10, 1.0) if total_loss_area > 0 else 0.0

        result = {
            "mining_likely": len(significant_clusters) > 0,
            "confidence": confidence,
            "n_change_clusters": n_clusters,
            "n_significant_clusters": len(significant_clusters),
            "clusters": significant_clusters,
            "total_veg_loss_area_pct": float(100 * total_loss_area),
        }

        logger.info(
            f"Mining detection: likely={result['mining_likely']}, "
            f"confidence={confidence:.2f}, "
            f"clusters={len(significant_clusters)}"
        )
        return result

    @staticmethod
    def _otsu_threshold(data: np.ndarray) -> float:
        """Compute Otsu's optimal threshold."""
        from skimage.filters import threshold_otsu
        try:
            return threshold_otsu(data)
        except Exception:
            return np.mean(data) + np.std(data)
