"""
AfriMine AI — Geostatistical Kriging
Spatial interpolation of mineral grade data using Kriging methods.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class KrigingInterpolator:
    """
    Spatial interpolation engine for mineral grade data.
    Supports Ordinary Kriging and Universal Kriging via PyKrige.
    """

    def __init__(
        self,
        variogram_model: str = "spherical",
        n_lags: int = 12,
        nlags: Optional[int] = None,
    ):
        self.variogram_model = variogram_model
        self.n_lags = nlags or n_lags
        self.ok_model = None  # Ordinary Kriging
        self.uk_model = None  # Universal Kriging
        self.is_fitted = False

    def fit_ordinary(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        values: np.ndarray,
    ) -> dict:
        """
        Fit Ordinary Kriging model.

        Args:
            lons: Longitude coordinates
            lats: Latitude coordinates
            values: Observed grade values at each point

        Returns:
            Variogram parameters and fit diagnostics
        """
        try:
            from pykrige.ok import OrdinaryKriging

            self.ok_model = OrdinaryKriging(
                lons, lats, values,
                variogram_model=self.variogram_model,
                nlags=self.n_lags,
                enable_plotting=False,
                verbose=False,
            )
            self.is_fitted = True

            # Extract variogram parameters (ensure Python float, not numpy scalar)
            params = self.ok_model.variogram_model_parameters
            variogram_params = {
                "model": self.variogram_model,
                "nugget": float(params[0]) if len(params) > 0 else 0.0,
                "sill": float(params[1]) if len(params) > 1 else 0.0,
                "range": float(params[2]) if len(params) > 2 else 0.0,
                "n_points": int(len(values)),
                "mean_grade": float(np.mean(values)),
                "std_grade": float(np.std(values)),
            }

            logger.info(
                f"Ordinary Kriging fitted: {self.variogram_model}, "
                f"nugget={variogram_params['nugget']:.4f}, "
                f"sill={variogram_params['sill']:.4f}, "
                f"range={variogram_params['range']:.4f}"
            )
            return variogram_params

        except ImportError:
            logger.warning("PyKrige not installed — using fallback linear interpolation")
            self._fallback_data = {"lons": lons, "lats": lats, "values": values}
            self.is_fitted = True
            return {"model": "fallback_linear", "n_points": len(values)}

    def predict(
        self,
        grid_lons: np.ndarray,
        grid_lats: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Predict grade values on a grid.

        Returns:
            (predicted_values, kriging_variance)
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit_ordinary() first.")

        if self.ok_model is not None:
            z, ss = self.ok_model.execute("points", grid_lons.flatten(), grid_lats.flatten())
            return z.reshape(grid_lons.shape), ss.reshape(grid_lons.shape)

        # Fallback: inverse distance weighting
        return self._idw_predict(grid_lons, grid_lats)

    def predict_grid(
        self,
        lon_min: float, lon_max: float,
        lat_min: float, lat_max: float,
        resolution: int = 50,
    ) -> dict:
        """
        Generate a prediction grid over the area of interest.

        Returns:
            {grid_lon, grid_lat, predicted, variance, mask}
        """
        grid_lon = np.linspace(lon_min, lon_max, resolution)
        grid_lat = np.linspace(lat_min, lat_max, resolution)
        mesh_lon, mesh_lat = np.meshgrid(grid_lon, grid_lat)

        predicted, variance = self.predict(mesh_lon, mesh_lat)

        # Mask unreliable predictions (high variance)
        var_threshold = np.percentile(variance, 90)
        mask = variance < var_threshold

        return {
            "grid_lon": mesh_lon.tolist(),
            "grid_lat": mesh_lat.tolist(),
            "predicted": predicted.tolist(),
            "variance": variance.tolist(),
            "mask": mask.tolist(),
            "resolution": resolution,
            "bounds": {"lon_min": lon_min, "lon_max": lon_max, "lat_min": lat_min, "lat_max": lat_max},
        }

    def _idw_predict(self, grid_lon: np.ndarray, grid_lat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Inverse Distance Weighting fallback."""
        data = self._fallback_data
        lons, lats, values = data["lons"], data["lats"], data["values"]
        power = 2

        predicted = np.zeros_like(grid_lon, dtype=float)
        for i in range(grid_lon.shape[0]):
            for j in range(grid_lon.shape[1]):
                distances = np.sqrt(
                    (lons - grid_lon[i, j]) ** 2 + (lats - grid_lat[i, j]) ** 2
                )
                distances = np.maximum(distances, 1e-10)
                weights = 1.0 / distances ** power
                predicted[i, j] = np.sum(weights * values) / np.sum(weights)

        # Variance approximation: inverse of sum of weights
        variance = np.ones_like(predicted) * np.var(values)
        return predicted, variance


def kriging_from_samples(
    samples: list[dict],
    lon_key: str = "lon",
    lat_key: str = "lat",
    value_key: str = "grade",
    variogram_model: str = "spherical",
) -> dict:
    """
    Convenience function to run kriging from a list of sample dicts.

    Args:
        samples: list of {lon, lat, grade} dicts
    """
    lons = np.array([s[lon_key] for s in samples])
    lats = np.array([s[lat_key] for s in samples])
    values = np.array([s[value_key] for s in samples], dtype=float)

    kriger = KrigingInterpolator(variogram_model=variogram_model)
    params = kriger.fit_ordinary(lons, lats, values)

    # Generate grid
    lon_margin = (lons.max() - lons.min()) * 0.1
    lat_margin = (lats.max() - lats.min()) * 0.1
    grid = kriger.predict_grid(
        lons.min() - lon_margin, lons.max() + lon_margin,
        lats.min() - lat_margin, lats.max() + lat_margin,
    )

    return {
        "variogram": params,
        "grid": grid,
        "input_points": len(samples),
    }
