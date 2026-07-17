"""
Resource Classification for AfriMine AI
=========================================

Implements JORC / SAMREC classification rules for mineral resource reporting.
Assigns Measured / Indicated / Inferred categories and confidence scores.

Reference: JORC Code (2012), SAMREC Code (2016)

Dependencies: numpy, pandas
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants / Enums
# ---------------------------------------------------------------------------

class ResourceCategory(str, Enum):
    MEASURED = "measured"
    INDICATED = "indicated"
    INFERRED = "inferred"
    UNCLASSIFIED = "unclassified"


@dataclass
class ClassificationCriteria:
    """
    Thresholds for JORC/SAMREC classification.

    These are guidelines — actual classification depends on competent person judgment.
    """
    # Maximum distance to nearest sample (meters)
    max_distance_measured: float = 25.0
    max_distance_indicated: float = 50.0
    max_distance_inferred: float = 100.0

    # Maximum kriging variance (relative to sill)
    max_variance_measured: float = 0.25
    max_variance_indicated: float = 0.50
    max_variance_inferred: float = 0.75

    # Minimum number of informing samples within search radius
    min_samples_measured: int = 6
    min_samples_indicated: int = 3
    min_samples_inferred: int = 1

    # Maximum coefficient of variation of informing samples
    max_cv_measured: float = 0.5
    max_cv_indicated: float = 1.0
    max_cv_inferred: float = 2.0

    # Geological confidence (0-1)
    min_geological_confidence_measured: float = 0.8
    min_geological_confidence_indicated: float = 0.5
    min_geological_confidence_inferred: float = 0.2


@dataclass
class BlockClassification:
    """Classification result for a single block."""
    category: ResourceCategory
    confidence_score: float  # 0.0 to 1.0
    distance_to_nearest: float
    n_informing_samples: float
    kriging_variance: float
    cv_informing: float
    geological_confidence: float
    reasons: List[str]


@dataclass
class ClassificationSummary:
    """Summary of resource classification."""
    total_blocks: int
    measured_blocks: int
    indicated_blocks: int
    inferred_blocks: int
    unclassified_blocks: int
    measured_tonnage: float
    indicated_tonnage: float
    inferred_tonnage: float
    measured_grade: float
    indicated_grade: float
    inferred_grade: float
    measured_metal: float
    indicated_metal: float
    inferred_metal: float


# ---------------------------------------------------------------------------
# Resource Classifier
# ---------------------------------------------------------------------------

class ResourceClassifier:
    """
    JORC/SAMREC resource classification engine.

    Assigns Measured / Indicated / Inferred categories to block model cells
    based on multiple criteria including spatial proximity, kriging variance,
    sample density, and geological confidence.

    Parameters
    ----------
    criteria : ClassificationCriteria, optional
        Classification thresholds. Uses JORC defaults if not provided.
    variogram_range : float, optional
        Variogram range for spatial context.
    sill : float, optional
        Variogram sill for variance normalization.
    """

    def __init__(
        self,
        criteria: Optional[ClassificationCriteria] = None,
        variogram_range: Optional[float] = None,
        sill: Optional[float] = None,
    ):
        self.criteria = criteria or ClassificationCriteria()
        self.variogram_range = variogram_range
        self.sill = sill

    # ------------------------------------------------------------------
    # Single block classification
    # ------------------------------------------------------------------

    def classify_block(
        self,
        distance_to_nearest: float,
        n_informing_samples: int,
        kriging_variance: float,
        cv_informing: float = 0.0,
        geological_confidence: float = 1.0,
    ) -> BlockClassification:
        """
        Classify a single block based on JORC criteria.

        Parameters
        ----------
        distance_to_nearest : float
            Distance to nearest informing sample (meters).
        n_informing_samples : int
            Number of samples used in estimation.
        kriging_variance : float
            Kriging variance at this block.
        cv_informing : float
            Coefficient of variation of informing samples.
        geological_confidence : float
            Geological confidence factor (0–1), domain-dependent.

        Returns
        -------
        BlockClassification
        """
        c = self.criteria
        reasons = []
        scores = []

        # 1. Distance score
        if distance_to_nearest <= c.max_distance_measured:
            dist_score = 1.0
        elif distance_to_nearest <= c.max_distance_indicated:
            dist_score = 0.66
        elif distance_to_nearest <= c.max_distance_inferred:
            dist_score = 0.33
        else:
            dist_score = 0.0
        scores.append(dist_score)

        # 2. Variance score (normalized)
        norm_var = kriging_variance / self.sill if self.sill and self.sill > 0 else kriging_variance
        if norm_var <= c.max_variance_measured:
            var_score = 1.0
        elif norm_var <= c.max_variance_indicated:
            var_score = 0.66
        elif norm_var <= c.max_variance_inferred:
            var_score = 0.33
        else:
            var_score = 0.0
        scores.append(var_score)

        # 3. Sample density score
        if n_informing_samples >= c.min_samples_measured:
            samp_score = 1.0
        elif n_informing_samples >= c.min_samples_indicated:
            samp_score = 0.66
        elif n_informing_samples >= c.min_samples_inferred:
            samp_score = 0.33
        else:
            samp_score = 0.0
        scores.append(samp_score)

        # 4. CV score
        if cv_informing <= c.max_cv_measured:
            cv_score = 1.0
        elif cv_informing <= c.max_cv_indicated:
            cv_score = 0.66
        elif cv_informing <= c.max_cv_inferred:
            cv_score = 0.33
        else:
            cv_score = 0.0
        scores.append(cv_score)

        # 5. Geological confidence
        geo_score = min(max(geological_confidence, 0.0), 1.0)
        scores.append(geo_score)

        # Weighted confidence score
        weights = [0.25, 0.20, 0.20, 0.15, 0.20]
        confidence = sum(s * w for s, w in zip(scores, weights))

        # Category assignment (conservative: ALL criteria must be met for higher category)
        # Measured: all criteria met
        if (
            distance_to_nearest <= c.max_distance_measured
            and norm_var <= c.max_variance_measured
            and n_informing_samples >= c.min_samples_measured
            and cv_informing <= c.max_cv_measured
            and geological_confidence >= c.min_geological_confidence_measured
        ):
            category = ResourceCategory.MEASURED
            reasons.append("All measured criteria satisfied")

        # Indicated: all indicated criteria met
        elif (
            distance_to_nearest <= c.max_distance_indicated
            and norm_var <= c.max_variance_indicated
            and n_informing_samples >= c.min_samples_indicated
            and cv_informing <= c.max_cv_indicated
            and geological_confidence >= c.min_geological_confidence_indicated
        ):
            category = ResourceCategory.INDICATED
            reasons.append("Indicated criteria satisfied (not all measured)")
            if distance_to_nearest > c.max_distance_measured:
                reasons.append(f"Distance {distance_to_nearest:.1f}m exceeds measured limit")
            if norm_var > c.max_variance_measured:
                reasons.append(f"Variance {norm_var:.3f} exceeds measured limit")

        # Inferred: all inferred criteria met
        elif (
            distance_to_nearest <= c.max_distance_inferred
            and norm_var <= c.max_variance_inferred
            and n_informing_samples >= c.min_samples_inferred
            and cv_informing <= c.max_cv_inferred
            and geological_confidence >= c.min_geological_confidence_inferred
        ):
            category = ResourceCategory.INFERRED
            reasons.append("Inferred criteria satisfied")

        else:
            category = ResourceCategory.UNCLASSIFIED
            reasons.append("Does not meet minimum inferred criteria")
            if distance_to_nearest > c.max_distance_inferred:
                reasons.append(f"Distance {distance_to_nearest:.1f}m exceeds inferred limit")
            if n_informing_samples < c.min_samples_inferred:
                reasons.append(f"Only {n_informing_samples} informing samples (min {c.min_samples_inferred})")

        return BlockClassification(
            category=category,
            confidence_score=confidence,
            distance_to_nearest=distance_to_nearest,
            n_informing_samples=n_informing_samples,
            kriging_variance=kriging_variance,
            cv_informing=cv_informing,
            geological_confidence=geological_confidence,
            reasons=reasons,
        )

    # ------------------------------------------------------------------
    # Batch classification of block model
    # ------------------------------------------------------------------

    def classify_block_model(
        self,
        block_centroids: np.ndarray,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        kriging_variances: np.ndarray,
        geological_confidences: Optional[np.ndarray] = None,
        search_radius: Optional[float] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Classify all blocks in a block model.

        Parameters
        ----------
        block_centroids : np.ndarray, shape (m, 3)
            Block model centroids.
        sample_coords : np.ndarray, shape (n, 3)
            Sample locations.
        sample_values : np.ndarray, shape (n,)
            Sample grades.
        kriging_variances : np.ndarray, shape (m,)
            Kriging variance per block.
        geological_confidences : np.ndarray, shape (m,), optional
            Geological confidence per block (default 1.0).
        search_radius : float, optional
            Search radius for sample counting.

        Returns
        -------
        categories : np.ndarray of str, shape (m,)
        confidence_scores : np.ndarray, shape (m,)
        """
        from scipy.spatial.distance import cdist

        n_blocks = len(block_centroids)
        if geological_confidences is None:
            geological_confidences = np.ones(n_blocks)

        if search_radius is None:
            search_radius = self.criteria.max_distance_inferred

        # Distance matrix: blocks × samples
        dist_matrix = cdist(block_centroids, sample_coords)

        categories = np.empty(n_blocks, dtype=object)
        confidence_scores = np.zeros(n_blocks)

        for b in range(n_blocks):
            dists = dist_matrix[b]
            nearest = dists.min()
            within_radius = dists <= search_radius
            n_informing = int(within_radius.sum())
            informing_values = sample_values[within_radius]

            cv = (
                np.std(informing_values, ddof=1) / np.mean(informing_values)
                if n_informing > 1 and np.mean(informing_values) > 0
                else 0.0
            )

            result = self.classify_block(
                distance_to_nearest=nearest,
                n_informing_samples=n_informing,
                kriging_variance=kriging_variances[b],
                cv_informing=cv,
                geological_confidence=geological_confidences[b],
            )
            categories[b] = result.category.value
            confidence_scores[b] = result.confidence_score

        logger.info(
            "Classification complete: measured=%d, indicated=%d, inferred=%d, unclassified=%d",
            np.sum(categories == "measured"),
            np.sum(categories == "indicated"),
            np.sum(categories == "inferred"),
            np.sum(categories == "unclassified"),
        )
        return categories, confidence_scores

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summarize(
        self,
        categories: np.ndarray,
        block_tonnages: np.ndarray,
        block_grades: np.ndarray,
        block_metal: Optional[np.ndarray] = None,
    ) -> ClassificationSummary:
        """
        Generate a JORC-style classification summary.

        Parameters
        ----------
        categories : np.ndarray of str
        block_tonnages, block_grades, block_metal : np.ndarray

        Returns
        -------
        ClassificationSummary
        """
        if block_metal is None:
            block_metal = block_tonnages * block_grades

        def _cat_stats(cat: str):
            mask = categories == cat
            t = block_tonnages[mask].sum()
            m = block_metal[mask].sum()
            g = m / t if t > 0 else 0.0
            return int(mask.sum()), t, g, m

        m_blocks, m_tonnage, m_grade, m_metal = _cat_stats("measured")
        i_blocks, i_tonnage, i_grade, i_metal = _cat_stats("indicated")
        f_blocks, f_tonnage, f_grade, f_metal = _cat_stats("inferred")
        u_blocks = int(np.sum(categories == "unclassified"))

        return ClassificationSummary(
            total_blocks=len(categories),
            measured_blocks=m_blocks,
            indicated_blocks=i_blocks,
            inferred_blocks=f_blocks,
            unclassified_blocks=u_blocks,
            measured_tonnage=m_tonnage,
            indicated_tonnage=i_tonnage,
            inferred_tonnage=f_tonnage,
            measured_grade=m_grade,
            indicated_grade=i_grade,
            inferred_grade=f_grade,
            measured_metal=m_metal,
            indicated_metal=i_metal,
            inferred_metal=f_metal,
        )

    def summary_to_dataframe(self, summary: ClassificationSummary) -> pd.DataFrame:
        """Convert summary to a JORC-style table."""
        rows = [
            {
                "Category": "Measured",
                "Blocks": summary.measured_blocks,
                "Tonnage (t)": summary.measured_tonnage,
                "Grade": summary.measured_grade,
                "Metal Content": summary.measured_metal,
            },
            {
                "Category": "Indicated",
                "Blocks": summary.indicated_blocks,
                "Tonnage (t)": summary.indicated_tonnage,
                "Grade": summary.indicated_grade,
                "Metal Content": summary.indicated_metal,
            },
            {
                "Category": "Inferred",
                "Blocks": summary.inferred_blocks,
                "Tonnage (t)": summary.inferred_tonnage,
                "Grade": summary.inferred_grade,
                "Metal Content": summary.inferred_metal,
            },
            {
                "Category": "Unclassified",
                "Blocks": summary.unclassified_blocks,
                "Tonnage (t)": 0,
                "Grade": 0,
                "Metal Content": 0,
            },
        ]
        df = pd.DataFrame(rows)
        # Add totals
        totals = pd.DataFrame([{
            "Category": "TOTAL",
            "Blocks": summary.total_blocks,
            "Tonnage (t)": df["Tonnage (t)"].sum(),
            "Grade": "",
            "Metal Content": df["Metal Content"].sum(),
        }])
        return pd.concat([df, totals], ignore_index=True)

    # ------------------------------------------------------------------
    # Confidence map for visualization
    # ------------------------------------------------------------------

    def confidence_map(
        self,
        block_centroids: np.ndarray,
        confidence_scores: np.ndarray,
        grid_shape: Tuple[int, int],
    ) -> np.ndarray:
        """
        Reshape confidence scores to a 2D grid for visualization.

        Parameters
        ----------
        block_centroids : np.ndarray, shape (m, 2 or 3)
        confidence_scores : np.ndarray, shape (m,)
        grid_shape : (nx, ny)

        Returns
        -------
        np.ndarray, shape (ny, nx)
        """
        nx, ny = grid_shape
        conf_grid = np.full((ny, nx), np.nan)

        # Map centroids to grid indices
        x_unique = np.unique(block_centroids[:, 0])
        y_unique = np.unique(block_centroids[:, 1])

        for idx in range(len(block_centroids)):
            xi = np.argmin(np.abs(x_unique - block_centroids[idx, 0]))
            yi = np.argmin(np.abs(y_unique - block_centroids[idx, 1]))
            if 0 <= xi < nx and 0 <= yi < ny:
                conf_grid[yi, xi] = confidence_scores[idx]

        return conf_grid
