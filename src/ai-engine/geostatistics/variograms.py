"""
AfriMine AI — Variogram Analysis
Experimental variogram computation and model fitting for spatial data.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class VariogramAnalyzer:
    """
    Compute and fit experimental variograms for spatial mineral grade data.
    """

    def __init__(self, n_lags: int = 12, max_distance: Optional[float] = None):
        self.n_lags = n_lags
        self.max_distance = max_distance

    def compute_experimental(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        values: np.ndarray,
    ) -> dict:
        """
        Compute the experimental (empirical) variogram.

        Returns:
            {lags, semivariance, n_pairs, model_params}
        """
        n = len(values)
        distances = []
        semivariances = []

        # Compute pairwise distances and semivariances
        for i in range(n):
            for j in range(i + 1, n):
                d = np.sqrt((lons[i] - lons[j]) ** 2 + (lats[i] - lats[j]) ** 2)
                gamma = 0.5 * (values[i] - values[j]) ** 2
                distances.append(d)
                semivariances.append(gamma)

        distances = np.array(distances, dtype=np.float64)
        semivariances = np.array(semivariances, dtype=np.float64)

        if self.max_distance is None:
            self.max_distance = float(np.percentile(distances, 80))

        # Bin into lags
        lag_edges = np.linspace(0, self.max_distance, self.n_lags + 1)
        lag_centers = (lag_edges[:-1] + lag_edges[1:]) / 2
        binned_gamma = np.zeros(self.n_lags)
        binned_counts = np.zeros(self.n_lags, dtype=int)

        for k in range(self.n_lags):
            mask = (distances >= lag_edges[k]) & (distances < lag_edges[k + 1])
            if np.any(mask):
                binned_gamma[k] = np.mean(semivariances[mask])
                binned_counts[k] = np.sum(mask)

        # Remove empty lags
        valid = binned_counts > 0
        lags = lag_centers[valid]
        gamma = binned_gamma[valid]
        counts = binned_counts[valid]

        # Fit variogram model
        model_params = self._fit_model(lags, gamma)

        return {
            "lags": lags.tolist(),
            "semivariance": gamma.tolist(),
            "n_pairs": counts.tolist(),
            "model": model_params,
        }

    def _fit_model(self, lags: np.ndarray, gamma: np.ndarray) -> dict:
        """Fit a variogram model to experimental data."""
        if len(lags) < 3:
            return {"model": "insufficient_data"}

        # Estimate nugget (y-intercept), sill (plateau), range (distance to sill)
        nugget = gamma[0] * 0.5 if len(gamma) > 0 else 0
        sill = np.max(gamma)
        range_val = lags[-1] * 0.5

        # Try to find range (where gamma reaches ~95% of sill)
        for i, g in enumerate(gamma):
            if g >= 0.95 * sill:
                range_val = lags[i]
                break

        # Refine using least-squares fit
        try:
            from scipy.optimize import curve_fit

            def spherical(h, nug, sil, rng):
                result = np.where(
                    h <= rng,
                    nug + sil * (1.5 * h / rng - 0.5 * (h / rng) ** 3),
                    nug + sil
                )
                return result

            popt, _ = curve_fit(
                spherical, lags, gamma,
                p0=[nugget, sill, range_val],
                bounds=([0, 0, 0], [sill * 2, sill * 2, lags[-1] * 2]),
                maxfev=5000,
            )
            nugget, sill, range_val = popt
            fit_quality = "least_squares"
        except Exception:
            fit_quality = "heuristic"

        return {
            "model": "spherical",
            "nugget": round(float(nugget), 6),
            "sill": round(float(sill), 6),
            "range": round(float(range_val), 6),
            "fit_method": fit_quality,
        }

    def _safe_float(self, val) -> float:
        """Convert numpy scalar or array to plain Python float."""
        if isinstance(val, np.ndarray):
            return float(val.item()) if val.size == 1 else float(val.flat[0])
        return float(val)

    def compute_directional(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        values: np.ndarray,
        directions: list[float] = [0, 45, 90, 135],
        tolerance: float = 22.5,
    ) -> dict:
        """
        Compute directional variograms to detect anisotropy.

        Args:
            directions: Azimuth angles in degrees (0=N, 90=E)
            tolerance: Angular tolerance in degrees
        """
        results = {}
        for direction in directions:
            lags_list = []
            gamma_list = []

            for i in range(len(values)):
                for j in range(i + 1, len(values)):
                    dx = lons[j] - lons[i]
                    dy = lats[j] - lats[i]
                    d = np.sqrt(dx ** 2 + dy ** 2)

                    if d < 1e-10 or (self.max_distance and d > self.max_distance):
                        continue

                    # Compute azimuth
                    azimuth = np.degrees(np.arctan2(dx, dy)) % 360
                    angle_diff = min(abs(azimuth - direction), 360 - abs(azimuth - direction))

                    if angle_diff <= tolerance:
                        lags_list.append(d)
                        gamma_list.append(0.5 * (values[i] - values[j]) ** 2)

            if lags_list:
                lags_arr = np.array(lags_list)
                gamma_arr = np.array(gamma_list)
                # Bin
                n_bins = min(self.n_lags, len(lags_arr) // 3 + 1)
                bin_edges = np.linspace(0, np.percentile(lags_arr, 80), n_bins + 1)
                bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
                bin_gamma = np.zeros(n_bins)
                bin_counts = np.zeros(n_bins, dtype=int)
                for k in range(n_bins):
                    mask = (lags_arr >= bin_edges[k]) & (lags_arr < bin_edges[k + 1])
                    if np.any(mask):
                        bin_gamma[k] = np.mean(gamma_arr[mask])
                        bin_counts[k] = np.sum(mask)

                valid = bin_counts > 0
                results[f"{direction}deg"] = {
                    "direction": direction,
                    "lags": bin_centers[valid].tolist(),
                    "semivariance": bin_gamma[valid].tolist(),
                    "n_pairs": bin_counts[valid].tolist(),
                }

        return results

    def detect_anisotropy(self, directional_variograms: dict) -> dict:
        """Detect anisotropy from directional variograms."""
        ranges = {}
        for key, vg in directional_variograms.items():
            if vg.get("lags") and vg.get("semivariance"):
                ranges[key] = max(vg["lags"])

        if not ranges:
            return {"anisotropic": False}

        max_range_key = max(ranges, key=ranges.get)
        min_range_key = min(ranges, key=ranges.get)
        ratio = ranges[max_range_key] / max(ranges[min_range_key], 1e-10)

        return {
            "anisotropic": ratio > 1.5,
            "ratio": round(ratio, 2),
            "major_direction": max_range_key,
            "minor_direction": min_range_key,
            "ranges": ranges,
        }
