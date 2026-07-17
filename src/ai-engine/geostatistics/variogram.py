"""
Variogram Analysis for AfriMine AI
===================================

Computes empirical variograms from drill-hole / grab-sample data,
fits theoretical models (spherical, exponential, Gaussian), performs
cross-validation for model selection, and detects anisotropy.

Dependencies: gstools, numpy, scipy, matplotlib
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize

try:
    import gstools as gs
except ImportError:
    gs = None  # graceful degradation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class VariogramModel(str, Enum):
    SPHERICAL = "spherical"
    EXPONENTIAL = "exponential"
    GAUSSIAN = "gaussian"


@dataclass
class VariogramParameters:
    """Fitted variogram parameters."""
    model: VariogramModel
    nugget: float
    sill: float
    range_: float
    anisotropy_ratio: float = 1.0
    anisotropy_angle: float = 0.0  # degrees
    r_squared: float = 0.0
    rmse: float = 0.0


@dataclass
class EmpiricalVariogram:
    """Result of empirical variogram computation."""
    lag_distances: np.ndarray
    semivariance: np.ndarray
    lag_tolerance: float
    n_pairs: np.ndarray
    direction: Optional[Tuple[float, float]] = None  # azimuth, dip


@dataclass
class AnisotropyResult:
    """Anisotropy detection result."""
    major_range: float
    minor_range: float
    vertical_range: float
    major_azimuth: float  # degrees
    major_dip: float
    anisotropy_ratio_horizontal: float
    anisotropy_ratio_vertical: float


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class VariogramAnalysis:
    """
    Full variogram analysis pipeline.

    Parameters
    ----------
    coords : np.ndarray, shape (n, 2 or 3)
        Sample coordinates [x, y] or [x, y, z].
    values : np.ndarray, shape (n,)
        Sample values (grades).
    """

    def __init__(self, coords: np.ndarray, values: np.ndarray):
        if gs is None:
            raise ImportError("gstools is required: pip install gstools")
        self.coords = np.asarray(coords, dtype=np.float64)
        self.values = np.asarray(values, dtype=np.float64)
        if self.coords.shape[0] != self.values.shape[0]:
            raise ValueError("coords and values must have the same length")
        self.ndim = self.coords.shape[1]
        self._empirical: Optional[EmpiricalVariogram] = None
        self._fitted: Optional[VariogramParameters] = None

    # ------------------------------------------------------------------
    # Empirical variogram
    # ------------------------------------------------------------------

    def compute_empirical(
        self,
        n_lags: int = 15,
        max_lag: Optional[float] = None,
        lag_tolerance: Optional[float] = None,
        direction: Optional[Tuple[float, float]] = None,
        bandwidth: Optional[float] = None,
    ) -> EmpiricalVariogram:
        """
        Compute the empirical (experimental) variogram.

        Parameters
        ----------
        n_lags : int
            Number of lag bins.
        max_lag : float, optional
            Maximum lag distance. Defaults to half the max pairwise distance.
        direction : tuple (azimuth, dip), optional
            Directional variogram. If None, omnidirectional.
        bandwidth : float, optional
            Angular bandwidth for directional variogram (degrees).

        Returns
        -------
        EmpiricalVariogram
        """
        pos = self.coords.T  # gstools expects (dim, n)

        # Build the bin edges
        if max_lag is None:
            from scipy.spatial.distance import pdist
            max_lag = np.percentile(pdist(self.coords), 50)
        bin_edges = np.linspace(0, max_lag, n_lags + 1)

        if direction is not None:
            azimuth, dip = direction
            # Directional variogram using gstools
            if self.ndim == 3:
                model_tmp = gs.Spherical(dim=3)
                model_tmp.angles = (np.radians(azimuth), np.radians(dip), 0)
                if bandwidth:
                    model_tmp.bandwidth = np.radians(bandwidth)
            else:
                model_tmp = gs.Spherical(dim=2)
                model_tmp.angles = np.radians(azimuth)
                if bandwidth:
                    model_tmp.bandwidth = np.radians(bandwidth)

        # Use gstools to compute the variogram
        bin_center, vario = gs.vario_estimate(
            pos,
            self.values,
            bin_edges=bin_edges,
            direction=direction,
            bandwidth=bandwidth,
        )

        # Count pairs per lag (approximation via gstools structured)
        n_pairs = np.zeros(n_lags)
        for i in range(len(self.values)):
            for j in range(i + 1, len(self.values)):
                dist = np.linalg.norm(self.coords[i] - self.coords[j])
                for k in range(n_lags):
                    if bin_edges[k] <= dist < bin_edges[k + 1]:
                        n_pairs[k] += 1
                        break

        if lag_tolerance is None:
            lag_tolerance = float(bin_edges[1] - bin_edges[0]) / 2

        self._empirical = EmpiricalVariogram(
            lag_distances=np.asarray(bin_center, dtype=np.float64),
            semivariance=np.asarray(vario, dtype=np.float64),
            lag_tolerance=float(lag_tolerance),
            n_pairs=np.asarray(n_pairs, dtype=np.float64),
            direction=direction,
        )
        return self._empirical

    # ------------------------------------------------------------------
    # Theoretical model fitting
    # ------------------------------------------------------------------

    @classmethod
    def _get_model_map(cls) -> dict:
        """Return model map, building it lazily so gs can be None at import time."""
        if gs is None:
            raise ImportError("gstools is required: pip install gstools")
        return {
            VariogramModel.SPHERICAL: gs.Spherical,
            VariogramModel.EXPONENTIAL: gs.Exponential,
            VariogramModel.GAUSSIAN: gs.Gaussian,
        }

    def fit_model(
        self,
        model_type: VariogramModel = VariogramModel.SPHERICAL,
        nugget: Optional[float] = None,
        sill: Optional[float] = None,
        range_: Optional[float] = None,
    ) -> VariogramParameters:
        """
        Fit a theoretical variogram model to the empirical variogram.

        Parameters
        ----------
        model_type : VariogramModel
            Type of theoretical model.
        nugget, sill, range_ : float, optional
            Initial guesses. If None, auto-estimated from data.

        Returns
        -------
        VariogramParameters
        """
        if self._empirical is None:
            self.compute_empirical()

        emp = self._empirical

        # Auto-guess parameters
        if sill is None:
            sill = np.max(emp.semivariance)
        if range_ is None:
            range_ = emp.lag_distances[np.argmax(emp.semivariance > 0.5 * sill)] if np.any(emp.semivariance > 0.5 * sill) else emp.lag_distances[-1] / 3
        if nugget is None:
            nugget = 0.0

        # Fit using gstools
        dim = self.ndim
        gs_model_cls = self._get_model_map()[model_type]
        model = gs_model_cls(
            dim=dim,
            var=sill - nugget,
            len_scale=range_,
            nugget=nugget,
        )

        # Optimize using least-squares on empirical data
        lag = emp.lag_distances
        sem = emp.semivariance

        def _loss(params):
            n, s, r = params
            if s <= 0 or r <= 0:
                return 1e12
            model_fit = gs_model_cls(dim=dim, var=s - n, len_scale=r, nugget=max(n, 0))
            predicted = model_fit.variogram(lag)
            return np.sum((predicted - sem) ** 2)

        result = minimize(
            _loss,
            x0=[nugget, sill, range_],
            method="Nelder-Mead",
            options={"maxiter": 10000, "xatol": 1e-8, "fatol": 1e-10},
        )
        opt_nugget, opt_sill, opt_range = float(result.x[0]), float(result.x[1]), float(result.x[2])
        opt_nugget = max(opt_nugget, 0.0)
        opt_sill = max(opt_sill, opt_nugget + 1e-6)
        opt_range = max(opt_range, 1e-6)

        # Compute R² and RMSE
        fitted_model = gs_model_cls(dim=dim, var=opt_sill - opt_nugget, len_scale=opt_range, nugget=opt_nugget)
        predicted = fitted_model.variogram(lag)
        ss_res = np.sum((sem - predicted) ** 2)
        ss_tot = np.sum((sem - np.mean(sem)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        rmse = np.sqrt(ss_res / len(sem))

        self._fitted = VariogramParameters(
            model=model_type,
            nugget=opt_nugget,
            sill=opt_sill,
            range_=opt_range,
            r_squared=r_squared,
            rmse=rmse,
        )
        logger.info(
            "Fitted %s variogram: nugget=%.4f, sill=%.4f, range=%.2f, R²=%.4f",
            model_type.value, opt_nugget, opt_sill, opt_range, r_squared,
        )
        return self._fitted

    def cross_validate(
        self,
        model_types: Optional[List[VariogramModel]] = None,
        n_lags: int = 15,
    ) -> Dict[VariogramModel, VariogramParameters]:
        """
        Fit all requested models and rank by R² / RMSE.

        Returns dict of model_type → VariogramParameters, sorted best-first.
        """
        if model_types is None:
            model_types = list(VariogramModel)

        if self._empirical is None:
            self.compute_empirical(n_lags=n_lags)

        # Save original fitted so we can restore the best
        best_r2 = -np.inf
        best_params: Dict[VariogramModel, VariogramParameters] = {}

        for mt in model_types:
            params = self.fit_model(model_type=mt)
            best_params[mt] = params

        # Rank by R² descending
        best_params = dict(sorted(best_params.items(), key=lambda kv: kv[1].r_squared, reverse=True))

        # Set self._fitted to the best
        best_model = next(iter(best_params))
        self._fitted = best_params[best_model]
        logger.info("Best model: %s (R²=%.4f)", best_model.value, self._fitted.r_squared)
        return best_params

    # ------------------------------------------------------------------
    # Anisotropy detection
    # ------------------------------------------------------------------

    def detect_anisotropy(
        self,
        n_directions: int = 8,
        n_lags: int = 10,
        max_lag: Optional[float] = None,
    ) -> AnisotropyResult:
        """
        Detect geometric anisotropy by fitting variograms in multiple directions.

        Parameters
        ----------
        n_directions : int
            Number of azimuth directions to test (evenly spaced 0–180°).
        n_lags : int
            Number of lag bins per direction.

        Returns
        -------
        AnisotropyResult
        """
        if self.ndim < 2:
            raise ValueError("Anisotropy detection requires at least 2D coordinates")

        azimuths = np.linspace(0, 180, n_directions, endpoint=False)
        ranges_per_dir: List[float] = []

        for az in azimuths:
            try:
                emp = self.compute_empirical(
                    n_lags=n_lags,
                    max_lag=max_lag,
                    direction=(az, 0.0),
                    bandwidth=22.5,
                )
                params = self.fit_model(model_type=VariogramModel.SPHERICAL)
                ranges_per_dir.append(params.range_)
            except Exception:
                ranges_per_dir.append(0.0)

        ranges_per_dir = np.array(ranges_per_dir)
        major_idx = np.argmax(ranges_per_dir)
        minor_idx = np.argmin(ranges_per_dir)
        major_azimuth = azimuths[major_idx]
        major_range = ranges_per_dir[major_idx]
        minor_range = ranges_per_dir[minor_idx]

        # Vertical range (if 3D)
        vertical_range = major_range  # default
        if self.ndim == 3:
            try:
                z_values = self.coords[:, 2]
                z_range = (z_values.max() - z_values.min()) / 4
                vertical_range = z_range if z_range > 0 else major_range
            except Exception:
                vertical_range = major_range

        h_ratio = major_range / minor_range if minor_range > 0 else 1.0
        v_ratio = major_range / vertical_range if vertical_range > 0 else 1.0

        result = AnisotropyResult(
            major_range=major_range,
            minor_range=minor_range,
            vertical_range=vertical_range,
            major_azimuth=major_azimuth,
            major_dip=0.0,
            anisotropy_ratio_horizontal=h_ratio,
            anisotropy_ratio_vertical=v_ratio,
        )

        # Update fitted parameters
        if self._fitted is not None:
            self._fitted.anisotropy_ratio = h_ratio
            self._fitted.anisotropy_angle = major_azimuth

        logger.info(
            "Anisotropy: major az=%.1f° range=%.2f, minor range=%.2f, ratio=%.2f",
            major_azimuth, major_range, minor_range, h_ratio,
        )
        return result

    # ------------------------------------------------------------------
    # Get fitted gstools model
    # ------------------------------------------------------------------

    def get_gstools_model(self) -> "gs.Model":
        """Return a gstools model object ready for kriging."""
        if self._fitted is None:
            raise RuntimeError("No model fitted. Call fit_model() or cross_validate() first.")

        gs_cls = self._get_model_map()[self._fitted.model]
        model = gs_cls(
            dim=self.ndim,
            var=self._fitted.sill - self._fitted.nugget,
            len_scale=self._fitted.range_,
            nugget=self._fitted.nugget,
        )
        if self._fitted.anisotropy_ratio != 1.0:
            model.anis = self._fitted.anisotropy_ratio
            if self.ndim >= 2:
                model.angles = np.radians(self._fitted.anisotropy_angle)
        return model

    @property
    def fitted_parameters(self) -> Optional[VariogramParameters]:
        return self._fitted

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------

    def plot_variogram(
        self,
        save_path: Optional[str] = None,
        show: bool = False,
    ) -> plt.Figure:
        """Plot empirical variogram with fitted theoretical model overlay."""
        if self._empirical is None:
            raise RuntimeError("Compute empirical variogram first.")

        emp = self._empirical
        fig, ax = plt.subplots(figsize=(8, 5))

        # Empirical
        ax.scatter(emp.lag_distances, emp.semivariance, c="steelblue", s=50, zorder=5, label="Empirical")
        for i, np_ in enumerate(emp.n_pairs):
            if np_ > 0:
                ax.annotate(
                    str(int(np_)),
                    (emp.lag_distances[i], emp.semivariance[i]),
                    textcoords="offset points", xytext=(0, 8), fontsize=7, ha="center",
                )

        # Theoretical
        if self._fitted is not None:
            model = self.get_gstools_model()
            x_plot = np.linspace(0, emp.lag_distances[-1] * 1.2, 200)
            y_plot = model.variogram(x_plot)
            ax.plot(x_plot, y_plot, "r-", lw=2, label=f"{self._fitted.model.value} (R²={self._fitted.r_squared:.3f})")
            ax.axhline(y=self._fitted.sill, color="gray", ls="--", alpha=0.5, label=f"Sill={self._fitted.sill:.3f}")
            ax.axvline(x=self._fitted.range_, color="green", ls="--", alpha=0.5, label=f"Range={self._fitted.range_:.1f}")

        ax.set_xlabel("Lag Distance")
        ax.set_ylabel("Semivariance")
        ax.set_title("Variogram Analysis")
        ax.legend(loc="lower right")
        ax.grid(True, alpha=0.3)

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
        if show:
            plt.show()
        return fig
