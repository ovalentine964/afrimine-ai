"""
Kriging Engine for AfriMine AI
================================

Implements Ordinary Kriging, Universal Kriging, Block Kriging,
and Kriging variance (uncertainty estimation).

Uses PyKrige as the backend with gstools variogram models.

Dependencies: pykrige, gstools, numpy, scipy
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from scipy.spatial.distance import cdist

try:
    from pykrige.ok import OrdinaryKriging
    from pykrige.uk import UniversalKriging
except ImportError:
    OrdinaryKriging = None
    UniversalKriging = None

try:
    import gstools as gs
except ImportError:
    gs = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class KrigingMethod(str, Enum):
    ORDINARY = "ordinary"
    UNIVERSAL = "universal"
    BLOCK = "block"


@dataclass
class KrigingResult:
    """Result of a kriging estimation."""
    estimates: np.ndarray          # Estimated grades
    variances: np.ndarray          # Kriging variances
    coordinates: np.ndarray        # Estimation points
    method: KrigingMethod
    block_size: Optional[Tuple[float, float, float]] = None
    n_neighbors: int = 0


@dataclass
class BlockKrigingResult:
    """Block kriging result with per-block statistics."""
    block_centroids: np.ndarray
    block_grades: np.ndarray
    block_variances: np.ndarray
    block_tonnages: Optional[np.ndarray] = None
    block_metal_content: Optional[np.ndarray] = None


# ---------------------------------------------------------------------------
# Kriging Engine
# ---------------------------------------------------------------------------

class KrigingEngine:
    """
    Multi-method kriging engine.

    Parameters
    ----------
    coords : np.ndarray, shape (n, 2 or 3)
        Sample coordinates.
    values : np.ndarray, shape (n,)
        Sample grades.
    variogram_model : str
        PyKrige variogram model name: 'linear', 'power', 'gaussian',
        'spherical', 'exponential', or 'hole-effect'.
    variogram_params : dict, optional
        Variogram parameters (sill, range, nugget).
    """

    def __init__(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        variogram_model: str = "spherical",
        variogram_params: Optional[Dict[str, float]] = None,
    ):
        if OrdinaryKriging is None:
            raise ImportError("pykrige is required: pip install pykrige")

        self.coords = np.asarray(coords, dtype=np.float64)
        self.values = np.asarray(values, dtype=np.float64)
        self.ndim = self.coords.shape[1]
        self.variogram_model = variogram_model
        self.variogram_params = variogram_params or {}
        self._ok = None
        self._uk = None

    # ------------------------------------------------------------------
    # Internal: build PyKrige objects
    # ------------------------------------------------------------------

    def _build_ok(self, **kwargs) -> OrdinaryKriging:
        """Build Ordinary Kriging object."""
        if self.ndim == 2:
            ok = OrdinaryKriging(
                self.coords[:, 0],
                self.coords[:, 1],
                self.values,
                variogram_model=self.variogram_model,
                variogram_parameters=self.variogram_params or None,
                verbose=False,
                enable_plotting=False,
                **kwargs,
            )
        else:
            # PyKrige 3D support
            ok = OrdinaryKriging(
                self.coords[:, 0],
                self.coords[:, 1],
                self.values,
                variogram_model=self.variogram_model,
                variogram_parameters=self.variogram_params or None,
                verbose=False,
                enable_plotting=False,
                nlags=kwargs.get("nlags", 12),
            )
        return ok

    def _build_uk(self, drift_terms: Optional[List[str]] = None, **kwargs) -> UniversalKriging:
        """Build Universal Kriging object with drift terms."""
        if self.ndim != 2:
            raise NotImplementedError("Universal Kriging via PyKrige is 2D only in this implementation")

        # Default drift: linear trend
        if drift_terms is None:
            drift_terms = ["regional_linear"]

        uk = UniversalKriging(
            self.coords[:, 0],
            self.coords[:, 1],
            self.values,
            variogram_model=self.variogram_model,
            variogram_parameters=self.variogram_params or None,
            drift_terms=drift_terms,
            verbose=False,
            enable_plotting=False,
            **kwargs,
        )
        return uk

    # ------------------------------------------------------------------
    # Ordinary Kriging
    # ------------------------------------------------------------------

    def ordinary_kriging(
        self,
        grid_x: np.ndarray,
        grid_y: np.ndarray,
        n_neighbors: int = 12,
        backend: str = "pykrige",
    ) -> KrigingResult:
        """
        Ordinary Kriging on a 2D grid.

        Parameters
        ----------
        grid_x, grid_y : 1-D arrays
            Grid coordinates (meshgrid axes).
        n_neighbors : int
            Number of neighboring samples.

        Returns
        -------
        KrigingResult
        """
        if backend == "pykrige":
            return self._ok_pykrige(grid_x, grid_y, n_neighbors)
        else:
            return self._ok_manual(grid_x, grid_y, n_neighbors)

    def _ok_pykrige(self, grid_x: np.ndarray, grid_y: np.ndarray, n_neighbors: int) -> KrigingResult:
        ok = self._build_ok(nlags=n_neighbors)
        z, ss = ok.execute("grid", grid_x, grid_y)

        # Flatten for result
        gx, gy = np.meshgrid(grid_x, grid_y)
        coords_grid = np.column_stack([gx.ravel(), gy.ravel()])
        estimates = z.ravel()
        variances = ss.ravel()

        # Mask NaN
        valid = ~np.isnan(estimates)
        return KrigingResult(
            estimates=estimates[valid],
            variances=variances[valid],
            coordinates=coords_grid[valid],
            method=KrigingMethod.ORDINARY,
            n_neighbors=n_neighbors,
        )

    def _ok_manual(self, grid_x: np.ndarray, grid_y: np.ndarray, n_neighbors: int) -> KrigingResult:
        """
        Manual Ordinary Kriging implementation using gstools variogram.
        Supports 2D and 3D.
        """
        gx, gy = np.meshgrid(grid_x, grid_y)
        grid_points = np.column_stack([gx.ravel(), gy.ravel()])
        n_grid = grid_points.shape[0]

        estimates = np.zeros(n_grid)
        variances = np.zeros(n_grid)

        # Variogram function
        model_params = self.variogram_params
        nugget = model_params.get("nugget", 0.0)
        sill = model_params.get("sill", np.var(self.values))
        range_ = model_params.get("range", np.ptp(self.coords, axis=0).mean() / 3)

        def _gamma(h):
            """Spherical variogram."""
            if h >= range_:
                return sill
            return nugget + (sill - nugget) * (1.5 * h / range_ - 0.5 * (h / range_) ** 3)

        gamma_vec = np.vectorize(_gamma)

        for i in range(n_grid):
            pt = grid_points[i]
            # Find k nearest neighbors
            dists = np.linalg.norm(self.coords - pt, axis=1)
            idx = np.argsort(dists)[:n_neighbors]
            n = len(idx)

            # Build kriging system
            # Variogram matrix between samples
            G = np.zeros((n + 1, n + 1))
            for a in range(n):
                for b in range(n):
                    h = np.linalg.norm(self.coords[idx[a]] - self.coords[idx[b]])
                    G[a, b] = gamma_vec(h)
                G[a, n] = 1.0
                G[n, a] = 1.0
            G[n, n] = 0.0

            # Right-hand side: variogram between sample and estimation point
            g = np.zeros(n + 1)
            for a in range(n):
                h = np.linalg.norm(self.coords[idx[a]] - pt)
                g[a] = gamma_vec(h)
            g[n] = 1.0

            # Solve
            try:
                weights = np.linalg.solve(G, g)
                est = np.dot(weights[:n], self.values[idx])
                var = np.dot(weights[:n], g[:n]) + weights[n]
                estimates[i] = est
                variances[i] = max(var, 0.0)
            except np.linalg.LinAlgError:
                estimates[i] = np.mean(self.values[idx])
                variances[i] = np.var(self.values[idx])

        valid = ~np.isnan(estimates)
        return KrigingResult(
            estimates=estimates[valid],
            variances=variances[valid],
            coordinates=grid_points[valid],
            method=KrigingMethod.ORDINARY,
            n_neighbors=n_neighbors,
        )

    # ------------------------------------------------------------------
    # Universal Kriging
    # ------------------------------------------------------------------

    def universal_kriging(
        self,
        grid_x: np.ndarray,
        grid_y: np.ndarray,
        drift_terms: Optional[List[str]] = None,
        n_neighbors: int = 12,
    ) -> KrigingResult:
        """
        Universal Kriging (accounts for regional trend).

        Parameters
        ----------
        grid_x, grid_y : 1-D arrays
        drift_terms : list of str, optional
            PyKrige drift terms: 'regional_linear', 'regional_quadratic',
            or specific powers.
        n_neighbors : int

        Returns
        -------
        KrigingResult
        """
        uk = self._build_uk(drift_terms=drift_terms, nlags=n_neighbors)
        z, ss = uk.execute("grid", grid_x, grid_y)

        gx, gy = np.meshgrid(grid_x, grid_y)
        coords_grid = np.column_stack([gx.ravel(), gy.ravel()])
        estimates = z.ravel()
        variances = ss.ravel()

        valid = ~np.isnan(estimates)
        return KrigingResult(
            estimates=estimates[valid],
            variances=variances[valid],
            coordinates=coords_grid[valid],
            method=KrigingMethod.UNIVERSAL,
            n_neighbors=n_neighbors,
        )

    # ------------------------------------------------------------------
    # Block Kriging
    # ------------------------------------------------------------------

    def block_kriging(
        self,
        block_centroids: np.ndarray,
        block_size: Tuple[float, float, float],
        n_sub_points: int = 8,
        n_neighbors: int = 12,
    ) -> BlockKrigingResult:
        """
        Block Kriging: estimate average grade within blocks by
        discretizing each block into sub-points and averaging.

        Parameters
        ----------
        block_centroids : np.ndarray, shape (m, 2 or 3)
            Block center coordinates.
        block_size : tuple (dx, dy, dz)
            Block dimensions.
        n_sub_points : int
            Sub-points per block for discretization (per axis).
        n_neighbors : int

        Returns
        -------
        BlockKrigingResult
        """
        block_centroids = np.asarray(block_centroids, dtype=np.float64)
        n_blocks = block_centroids.shape[0]
        dx, dy, dz = block_size

        block_grades = np.zeros(n_blocks)
        block_variances = np.zeros(n_blocks)

        for b in range(n_blocks):
            centroid = block_centroids[b]
            # Generate sub-points within the block
            if self.ndim == 2:
                sx = np.linspace(centroid[0] - dx / 2, centroid[0] + dx / 2, n_sub_points)
                sy = np.linspace(centroid[1] - dy / 2, centroid[1] + dy / 2, n_sub_points)
                sgx, sgy = np.meshgrid(sx, sy)
                sub_points = np.column_stack([sgx.ravel(), sgy.ravel()])
            else:
                sx = np.linspace(centroid[0] - dx / 2, centroid[0] + dx / 2, n_sub_points)
                sy = np.linspace(centroid[1] - dy / 2, centroid[1] + dy / 2, n_sub_points)
                sz = np.linspace(centroid[2] - dz / 2, centroid[2] + dz / 2, n_sub_points)
                sgx, sgy, sgz = np.meshgrid(sx, sy, sz)
                sub_points = np.column_stack([sgx.ravel(), sgy.ravel(), sgz.ravel()])

            # Krige each sub-point
            sub_est = np.zeros(len(sub_points))
            sub_var = np.zeros(len(sub_points))
            for sp_idx, sp in enumerate(sub_points):
                est, var = self._krige_point(sp, n_neighbors)
                sub_est[sp_idx] = est
                sub_var[sp_idx] = var

            block_grades[b] = np.mean(sub_est)
            # Block variance = mean sub-variance / n_sub (support effect)
            block_variances[b] = np.mean(sub_var) / len(sub_points)

        return BlockKrigingResult(
            block_centroids=block_centroids,
            block_grades=block_grades,
            block_variances=block_variances,
        )

    def _krige_point(self, point: np.ndarray, n_neighbors: int) -> Tuple[float, float]:
        """Krige a single point using manual implementation."""
        dists = np.linalg.norm(self.coords - point, axis=1)
        idx = np.argsort(dists)[:n_neighbors]
        n = len(idx)

        nugget = self.variogram_params.get("nugget", 0.0)
        sill = self.variogram_params.get("sill", np.var(self.values))
        range_ = self.variogram_params.get("range", np.ptp(self.coords, axis=0).mean() / 3)

        def _gamma(h):
            if h >= range_:
                return sill
            return nugget + (sill - nugget) * (1.5 * h / range_ - 0.5 * (h / range_) ** 3)

        G = np.zeros((n + 1, n + 1))
        for a in range(n):
            for b in range(n):
                G[a, b] = _gamma(np.linalg.norm(self.coords[idx[a]] - self.coords[idx[b]]))
            G[a, n] = 1.0
            G[n, a] = 1.0
        G[n, n] = 0.0

        g = np.zeros(n + 1)
        for a in range(n):
            g[a] = _gamma(np.linalg.norm(self.coords[idx[a]] - point))
        g[n] = 1.0

        try:
            w = np.linalg.solve(G, g)
            est = np.dot(w[:n], self.values[idx])
            var = np.dot(w[:n], g[:n]) + w[n]
            return est, max(var, 0.0)
        except np.linalg.LinAlgError:
            return np.mean(self.values[idx]), np.var(self.values[idx])

    # ------------------------------------------------------------------
    # Kriging variance map (uncertainty)
    # ------------------------------------------------------------------

    def kriging_variance_map(
        self,
        grid_x: np.ndarray,
        grid_y: np.ndarray,
        n_neighbors: int = 12,
    ) -> np.ndarray:
        """
        Compute kriging variance across a grid (uncertainty map).

        Returns
        -------
        np.ndarray, shape (len(grid_y), len(grid_x))
        """
        result = self.ordinary_kriging(grid_x, grid_y, n_neighbors)
        # Reshape to grid
        gx, gy = np.meshgrid(grid_x, grid_y)
        var_grid = np.full(gx.shape, np.nan)
        for i, coord in enumerate(result.coordinates):
            xi = np.argmin(np.abs(grid_x - coord[0]))
            yi = np.argmin(np.abs(grid_y - coord[1]))
            var_grid[yi, xi] = result.variances[i]
        return var_grid

    # ------------------------------------------------------------------
    # Point kriging (single or multiple arbitrary points)
    # ------------------------------------------------------------------

    def krige_points(
        self,
        target_points: np.ndarray,
        n_neighbors: int = 12,
        method: KrigingMethod = KrigingMethod.ORDINARY,
    ) -> KrigingResult:
        """
        Krige at arbitrary target points.

        Parameters
        ----------
        target_points : np.ndarray, shape (m, 2 or 3)
        n_neighbors : int
        method : KrigingMethod

        Returns
        -------
        KrigingResult
        """
        target_points = np.asarray(target_points, dtype=np.float64)
        n = target_points.shape[0]
        estimates = np.zeros(n)
        variances = np.zeros(n)

        for i in range(n):
            est, var = self._krige_point(target_points[i], n_neighbors)
            estimates[i] = est
            variances[i] = var

        return KrigingResult(
            estimates=estimates,
            variances=variances,
            coordinates=target_points,
            method=method,
            n_neighbors=n_neighbors,
        )
