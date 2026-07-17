"""
Grade Estimation Utilities for AfriMine AI
============================================

Log-normal grade distribution handling, top-cutting / capping,
compositing, and domain boundary estimation.

Dependencies: numpy, pandas, scipy
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import norm, lognorm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TopCutResult:
    """Result of top-cutting analysis."""
    original_values: np.ndarray
    capped_values: np.ndarray
    cut_grade: float
    n_capped: int
    original_mean: float
    capped_mean: float
    original_std: float
    capped_std: float
    method: str


@dataclass
class CompositeResult:
    """Result of compositing."""
    composites: pd.DataFrame
    n_input: int
    n_output: int
    composite_length: float


@dataclass
class LogNormalFit:
    """Log-normal distribution fit result."""
    mu: float          # Mean of log(value)
    sigma: float       # Std of log(value)
    mean: float        # Arithmetic mean
    variance: float    # Arithmetic variance
    median: float
    skewness: float
    kurtosis: float
    ad_statistic: float  # Anderson-Darling statistic
    ad_critical: float   # Critical value at 5%
    is_lognormal: bool


@dataclass
class DomainBoundary:
    """Result of domain boundary estimation."""
    domain_id: int
    centroid: np.ndarray
    extent: np.ndarray       # [xmin, xmax, ymin, ymax, (zmin, zmax)]
    n_samples: int
    mean_grade: float
    grade_range: Tuple[float, float]


# ---------------------------------------------------------------------------
# Grade Estimator
# ---------------------------------------------------------------------------

class GradeEstimator:
    """
    Grade processing pipeline for mining applications.

    Parameters
    ----------
    data : pd.DataFrame
        Must contain columns: 'x', 'y', 'grade'.
        Optional: 'z', 'hole_id', 'from', 'to', 'domain'.
    """

    REQUIRED_COLS = {"x", "y", "grade"}

    def __init__(self, data: pd.DataFrame):
        missing = self.REQUIRED_COLS - set(data.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        self.data = data.copy()
        self._validate()

    def _validate(self):
        n_before = len(self.data)
        self.data.dropna(subset=["x", "y", "grade"], inplace=True)
        self.data = self.data[self.data["grade"] >= 0].reset_index(drop=True)
        n_after = len(self.data)
        if n_after < n_before:
            logger.warning("Dropped %d rows with NaN/negative grades", n_before - n_after)

    # ------------------------------------------------------------------
    # Log-normal analysis
    # ------------------------------------------------------------------

    def fit_lognormal(self, values: Optional[np.ndarray] = None) -> LogNormalFit:
        """
        Test whether grades follow a log-normal distribution and fit parameters.

        Uses Anderson-Darling test on log-transformed values.
        """
        if values is None:
            values = self.data["grade"].values

        # Remove zeros for log transform
        pos_values = values[values > 0]
        if len(pos_values) < 10:
            raise ValueError("Need at least 10 positive values for log-normal fitting")

        log_vals = np.log(pos_values)
        mu = np.mean(log_vals)
        sigma = np.std(log_vals, ddof=1)

        # Anderson-Darling test for normality of log-values
        ad_result = stats.anderson(log_vals, dist="norm")
        ad_stat = ad_result.statistic
        # 5% significance level (index 2 is typically 5%)
        ad_crit = ad_result.critical_values[2] if len(ad_result.critical_values) > 2 else 0.787
        is_lognormal = ad_stat < ad_crit

        # Arithmetic moments from log-normal parameters
        mean = np.exp(mu + sigma**2 / 2)
        variance = (np.exp(sigma**2) - 1) * np.exp(2 * mu + sigma**2)
        median = np.exp(mu)
        skewness = (np.exp(sigma**2) + 2) * np.sqrt(np.exp(sigma**2) - 1)
        kurtosis = np.exp(4 * sigma**2) + 2 * np.exp(3 * sigma**2) + 3 * np.exp(2 * sigma**2) - 6

        result = LogNormalFit(
            mu=mu,
            sigma=sigma,
            mean=mean,
            variance=variance,
            median=median,
            skewness=skewness,
            kurtosis=kurtosis,
            ad_statistic=ad_stat,
            ad_critical=ad_crit,
            is_lognormal=is_lognormal,
        )
        logger.info(
            "Log-normal fit: mu=%.4f, sigma=%.4f, mean=%.4f, is_lognormal=%s",
            mu, sigma, mean, is_lognormal,
        )
        return result

    # ------------------------------------------------------------------
    # Top-cutting / Capping
    # ------------------------------------------------------------------

    def top_cut(
        self,
        values: Optional[np.ndarray] = None,
        method: str = "percentile",
        percentile: float = 99.0,
        absolute_cut: Optional[float] = None,
        multiple_of_mean: Optional[float] = None,
        domain_col: Optional[str] = None,
    ) -> TopCutResult:
        """
        Cap extreme high-grade outliers.

        Parameters
        ----------
        values : np.ndarray, optional
            Grade values. If None, uses self.data['grade'].
        method : str
            'percentile' — cap at given percentile
            'absolute' — cap at absolute_cut value
            'mean_multiple' — cap at multiple_of_mean × mean
            'log_normal' — cap at exp(mu + 3*sigma) of log-normal fit
        percentile : float
            Percentile for 'percentile' method (default 99).
        absolute_cut : float
            Absolute grade for 'absolute' method.
        multiple_of_mean : float
            Multiple for 'mean_multiple' method.
        domain_col : str, optional
            Column name for domain-based cutting.

        Returns
        -------
        TopCutResult
        """
        if values is None:
            values = self.data["grade"].values.copy()
        else:
            values = values.copy()

        original_mean = np.mean(values)
        original_std = np.std(values, ddof=1)

        # Determine cut grade
        if method == "percentile":
            cut_grade = np.percentile(values, percentile)
        elif method == "absolute":
            if absolute_cut is None:
                raise ValueError("absolute_cut required for 'absolute' method")
            cut_grade = absolute_cut
        elif method == "mean_multiple":
            if multiple_of_mean is None:
                raise ValueError("multiple_of_mean required for 'mean_multiple' method")
            cut_grade = multiple_of_mean * np.mean(values)
        elif method == "log_normal":
            fit = self.fit_lognormal(values)
            cut_grade = np.exp(fit.mu + 3 * fit.sigma)
        else:
            raise ValueError(f"Unknown method: {method}")

        # Apply cut
        capped = values.copy()
        n_capped = np.sum(capped > cut_grade)
        capped[capped > cut_grade] = cut_grade

        result = TopCutResult(
            original_values=values,
            capped_values=capped,
            cut_grade=cut_grade,
            n_capped=int(n_capped),
            original_mean=original_mean,
            capped_mean=np.mean(capped),
            original_std=original_std,
            capped_std=np.std(capped, ddof=1),
            method=method,
        )
        logger.info(
            "Top-cut (%s): cut=%.4f, n_capped=%d, mean %.4f→%.4f",
            method, cut_grade, n_capped, original_mean, np.mean(capped),
        )
        return result

    def top_cut_by_domain(
        self,
        domain_col: str = "domain",
        method: str = "percentile",
        **kwargs,
    ) -> Dict[int, TopCutResult]:
        """Apply top-cutting independently per domain."""
        if domain_col not in self.data.columns:
            raise ValueError(f"Column '{domain_col}' not found")

        results = {}
        for domain_id, group in self.data.groupby(domain_col):
            results[domain_id] = self.top_cut(
                values=group["grade"].values,
                method=method,
                **kwargs,
            )
        return results

    # ------------------------------------------------------------------
    # Compositing
    # ------------------------------------------------------------------

    def composite(
        self,
        composite_length: float,
        hole_id_col: str = "hole_id",
        from_col: str = "from",
        to_col: str = "to",
        grade_col: str = "grade",
        min_recovery: float = 0.75,
    ) -> CompositeResult:
        """
        Composite drill-hole samples to uniform length intervals.

        Length-weighted averaging for grade.

        Parameters
        ----------
        composite_length : float
            Target composite length (same units as from/to).
        hole_id_col, from_col, to_col, grade_col : str
            Column names.
        min_recovery : float
            Minimum recovery fraction to include a composite.

        Returns
        -------
        CompositeResult
        """
        required = {hole_id_col, from_col, to_col, grade_col}
        missing = required - set(self.data.columns)
        if missing:
            raise ValueError(f"Missing columns for compositing: {missing}")

        df = self.data.sort_values([hole_id_col, from_col]).copy()
        df["_length"] = df[to_col] - df[from_col]
        df = df[df["_length"] > 0].reset_index(drop=True)

        composites = []
        n_input = len(df)

        for hole_id, hole_data in df.groupby(hole_id_col):
            hole_data = hole_data.sort_values(from_col).reset_index(drop=True)
            hole_start = hole_data[from_col].iloc[0]
            hole_end = hole_data[to_col].iloc[-1]

            comp_from = hole_start
            while comp_from < hole_end:
                comp_to = comp_from + composite_length
                # Find samples that overlap with this composite interval
                mask = (hole_data[from_col] < comp_to) & (hole_data[to_col] > comp_from)
                overlapping = hole_data[mask]

                if len(overlapping) == 0:
                    comp_from = comp_to
                    continue

                # Calculate length-weighted grade
                total_length = 0.0
                weighted_grade = 0.0
                for _, row in overlapping.iterrows():
                    overlap_start = max(row[from_col], comp_from)
                    overlap_end = min(row[to_col], comp_to)
                    overlap_len = max(0, overlap_end - overlap_start)
                    total_length += overlap_len
                    weighted_grade += overlap_len * row[grade_col]

                recovery = total_length / composite_length
                if recovery >= min_recovery and total_length > 0:
                    avg_grade = weighted_grade / total_length
                    composites.append({
                        hole_id_col: hole_id,
                        from_col: comp_from,
                        to_col: comp_to,
                        grade_col: avg_grade,
                        "length": total_length,
                        "recovery": recovery,
                    })

                comp_from = comp_to

        comp_df = pd.DataFrame(composites)
        result = CompositeResult(
            composites=comp_df,
            n_input=n_input,
            n_output=len(comp_df),
            composite_length=composite_length,
        )
        logger.info("Compositing: %d samples → %d composites (%.1fm)", n_input, len(comp_df), composite_length)
        return result

    # ------------------------------------------------------------------
    # Domain boundary estimation
    # ------------------------------------------------------------------

    def estimate_domains(
        self,
        grade_col: str = "domain",
        method: str = "grade_threshold",
        thresholds: Optional[List[float]] = None,
        n_clusters: int = 3,
    ) -> List[DomainBoundary]:
        """
        Estimate geological domains based on grade distribution.

        Parameters
        ----------
        grade_col : str
            Column to use for domain definition. If 'domain', uses existing
            domain column. Otherwise uses grade-based classification.
        method : str
            'grade_threshold' — classify by grade thresholds
            'kmeans' — K-means clustering on coordinates + grade
        thresholds : list of float, optional
            Grade thresholds for 'grade_threshold' method.
        n_clusters : int
            Number of clusters for 'kmeans' method.

        Returns
        -------
        List[DomainBoundary]
        """
        df = self.data.copy()
        has_z = "z" in df.columns

        if method == "grade_threshold":
            if grade_col in df.columns and grade_col != "grade":
                # Use existing domain column
                domain_labels = df[grade_col].values
            else:
                # Create domains from grade thresholds
                grades = df["grade"].values
                if thresholds is None:
                    # Auto: use quartile-based thresholds
                    thresholds = [np.percentile(grades, 33), np.percentile(grades, 67)]
                domain_labels = np.digitize(grades, thresholds)

        elif method == "kmeans":
            from sklearn.cluster import KMeans
            features = df[["x", "y", "grade"]].values
            if has_z:
                features = df[["x", "y", "z", "grade"]].values
            # Normalize features
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            domain_labels = kmeans.fit_predict(features_scaled)
        else:
            raise ValueError(f"Unknown method: {method}")

        df["_domain"] = domain_labels
        boundaries = []

        for domain_id in sorted(df["_domain"].unique()):
            subset = df[df["_domain"] == domain_id]
            coords = subset[["x", "y"]].values
            if has_z:
                coords = subset[["x", "y", "z"]].values

            centroid = coords.mean(axis=0)
            if has_z:
                extent = np.array([
                    coords[:, 0].min(), coords[:, 0].max(),
                    coords[:, 1].min(), coords[:, 1].max(),
                    coords[:, 2].min(), coords[:, 2].max(),
                ])
            else:
                extent = np.array([
                    coords[:, 0].min(), coords[:, 0].max(),
                    coords[:, 1].min(), coords[:, 1].max(),
                ])

            boundaries.append(DomainBoundary(
                domain_id=int(domain_id),
                centroid=centroid,
                extent=extent,
                n_samples=len(subset),
                mean_grade=float(subset["grade"].mean()),
                grade_range=(float(subset["grade"].min()), float(subset["grade"].max())),
            ))

        logger.info("Domain estimation: %d domains found", len(boundaries))
        return boundaries

    # ------------------------------------------------------------------
    # Statistical summaries
    # ------------------------------------------------------------------

    def grade_statistics(self, values: Optional[np.ndarray] = None) -> Dict[str, float]:
        """Compute comprehensive grade statistics."""
        if values is None:
            values = self.data["grade"].values

        valid = values[~np.isnan(values)]
        return {
            "count": len(valid),
            "mean": float(np.mean(valid)),
            "median": float(np.median(valid)),
            "std": float(np.std(valid, ddof=1)),
            "min": float(np.min(valid)),
            "max": float(np.max(valid)),
            "p10": float(np.percentile(valid, 10)),
            "p25": float(np.percentile(valid, 25)),
            "p50": float(np.percentile(valid, 50)),
            "p75": float(np.percentile(valid, 75)),
            "p90": float(np.percentile(valid, 90)),
            "skewness": float(stats.skew(valid)),
            "kurtosis": float(stats.kurtosis(valid)),
            "cv": float(np.std(valid, ddof=1) / np.mean(valid)) if np.mean(valid) > 0 else 0.0,
        }

    def decluster_weights(
        self,
        cell_size: Optional[float] = None,
    ) -> np.ndarray:
        """
        Compute cell-declustering weights to correct for sampling bias.

        Samples in densely-sampled areas get lower weight.

        Parameters
        ----------
        cell_size : float, optional
            Cell size. If None, auto-estimated from data spacing.

        Returns
        -------
        np.ndarray, shape (n,)
            Weight per sample (sums to 1).
        """
        coords = self.data[["x", "y"]].values

        if cell_size is None:
            # Auto-estimate: median nearest-neighbor distance × 2
            from scipy.spatial.distance import cdist
            dists = cdist(coords, coords)
            np.fill_diagonal(dists, np.inf)
            nn = dists.min(axis=1)
            cell_size = np.median(nn) * 2

        # Assign cells
        cell_x = np.floor(coords[:, 0] / cell_size).astype(int)
        cell_y = np.floor(coords[:, 1] / cell_size).astype(int)
        cell_ids = list(zip(cell_x, cell_y))

        # Count samples per cell
        from collections import Counter
        counts = Counter(cell_ids)

        # Weight = 1 / count(cell) for each sample
        weights = np.array([1.0 / counts[c] for c in cell_ids])
        weights /= weights.sum()

        logger.info("Decluster weights: cell_size=%.2f, %d cells", cell_size, len(counts))
        return weights

    def declustered_mean(self) -> float:
        """Compute declustered weighted mean grade."""
        weights = self.decluster_weights()
        return float(np.dot(weights, self.data["grade"].values))
