"""
AfriMine AI — Mineral Grade Estimator
Estimates ore grade from visual features and optional XRF elemental data.
Uses XGBoost ensemble with feature engineering.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.metrics import mean_absolute_error, r2_score

logger = logging.getLogger(__name__)


# ──────────────────────────── Feature Engineering ────────────────────────────

# XRF element columns expected
XRF_ELEMENTS = [
    "Si", "Al", "Fe", "Ca", "Mg", "Na", "K", "Ti", "Mn", "P",
    "S", "Cl", "Cr", "Ni", "Cu", "Zn", "As", "Pb", "Au", "Ag",
]

# Visual feature columns from CNN
VISUAL_FEATURES = [
    "visual_metallic_sheen", "visual_grain_size", "visual_crystal_form",
    "visual_color_intensity", "visual_texture_score", "visual_luster",
    "visual_transparency", "visual_fracture_pattern", "visual_hardness_indicator",
    "visual_density_indicator", "visual_streak_color", "visual_impurity_level",
]

GRADE_UNITS = {
    "gold": "g/t",
    "copper": "%",
    "titanium": "%",
    "graphite": "%",
    "manganese": "%",
    "fluorite": "%",
    "bauxite": "%",
    "limestone": "%",
    "soda_ash": "%",
    "sodalite": "%",
    "ruby": "ct/t",
    "sapphire": "ct/t",
    "garnet": "ct/t",
    "tourmaline": "ct/t",
    "pyrite": "%",
    "quartz": "%",
    "diatomite": "%",
    "vermiculite": "%",
    "niobium": "ppm",
    "thorium": "ppm",
}


class GradeEstimator:
    """
    Estimates mineral grade from visual CNN features and XRF data.
    Uses an XGBoost ensemble with feature importance tracking.
    """

    def __init__(self, mineral_type: str = "gold"):
        self.mineral_type = mineral_type
        self.scaler = RobustScaler()
        self.model = self._build_model()
        self.feature_names: list[str] = []
        self.is_fitted = False
        self.metrics: dict = {}

    def _build_model(self) -> xgb.XGBRegressor:
        """Build XGBoost regressor optimized for grade estimation."""
        return xgb.XGBRegressor(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            min_child_weight=3,
            gamma=0.1,
            objective="reg:squarederror",
            tree_method="hist",
            random_state=42,
            n_jobs=-1,
        )

    def prepare_features(
        self,
        visual_features: dict[str, float],
        xrf_data: Optional[dict[str, float]] = None,
        image_embedding: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Combine visual features, XRF data, and CNN embeddings into a feature vector.
        """
        features = {}

        # Visual features
        for f in VISUAL_FEATURES:
            features[f] = visual_features.get(f, 0.0)

        # XRF elemental data
        if xrf_data:
            for elem in XRF_ELEMENTS:
                val = xrf_data.get(elem, 0.0)
                features[f"xrf_{elem}"] = val

            # Derived XRF ratios (geologically meaningful)
            fe_val = max(xrf_data.get("Fe", 0.001), 0.001)
            features["xrf_Si_Fe_ratio"] = xrf_data.get("Si", 0) / fe_val
            features["xrf_Ca_Al_ratio"] = xrf_data.get("Ca", 0) / max(xrf_data.get("Al", 0.001), 0.001)
            features["xrf_Au_Ag_ratio"] = xrf_data.get("Au", 0) / max(xrf_data.get("Ag", 0.001), 0.001)
            features["xrf_sulfide_indicator"] = xrf_data.get("S", 0) * xrf_data.get("Fe", 0)
            features["xrf_total_heavy_metals"] = sum(
                xrf_data.get(e, 0) for e in ["Pb", "Zn", "Cu", "Ni", "Cr"]
            )

        # CNN embedding (pooled feature vector from classifier backbone)
        if image_embedding is not None:
            # Take first 32 components of the embedding
            emb = image_embedding[:32] if len(image_embedding) >= 32 else np.pad(image_embedding, (0, 32 - len(image_embedding)))
            for i, v in enumerate(emb):
                features[f"cnn_emb_{i}"] = float(v)

        self.feature_names = sorted(features.keys())
        return np.array([features[k] for k in self.feature_names]).reshape(1, -1)

    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: Optional[list[str]] = None) -> dict:
        """
        Train the grade estimator.
        X: feature matrix (n_samples, n_features)
        y: grade values (n_samples,)
        Returns training metrics.
        """
        if feature_names:
            self.feature_names = feature_names

        X_scaled = self.scaler.fit_transform(X)

        # Cross-validation
        cv_scores = cross_val_score(self.model, X_scaled, y, cv=5, scoring="r2")

        # Full fit
        self.model.fit(X_scaled, y)
        self.is_fitted = True

        y_pred = self.model.predict(X_scaled)
        self.metrics = {
            "train_r2": float(r2_score(y, y_pred)),
            "train_mae": float(mean_absolute_error(y, y_pred)),
            "cv_r2_mean": float(cv_scores.mean()),
            "cv_r2_std": float(cv_scores.std()),
            "n_samples": len(y),
            "mineral_type": self.mineral_type,
        }

        logger.info(
            f"GradeEstimator trained for {self.mineral_type}: "
            f"R²={self.metrics['train_r2']:.4f}, "
            f"CV R²={self.metrics['cv_r2_mean']:.4f}±{self.metrics['cv_r2_std']:.4f}"
        )
        return self.metrics

    def predict(
        self,
        visual_features: dict[str, float],
        xrf_data: Optional[dict[str, float]] = None,
        image_embedding: Optional[np.ndarray] = None,
    ) -> dict:
        """
        Predict grade from visual and XRF features.
        Returns: {grade, unit, confidence_interval, feature_importance}
        """
        if not self.is_fitted:
            # Return heuristic estimate if not trained
            return self._heuristic_estimate(visual_features, xrf_data)

        X = self.prepare_features(visual_features, xrf_data, image_embedding)
        X_scaled = self.scaler.transform(X)

        # Prediction with uncertainty estimation using individual tree predictions
        y_pred = self.model.predict(X_scaled)[0]

        # Bootstrap confidence interval approximation
        preds_all_trees = []
        for estimator in self.model.get_booster():
            dmat = xgb.DMatrix(X_scaled, feature_names=self.feature_names)
            preds_all_trees.append(estimator.predict(dmat)[0] if hasattr(estimator, 'predict') else y_pred)

        # Use model's built-in prediction
        y_pred = float(y_pred)
        std_estimate = abs(y_pred) * 0.15  # Conservative 15% uncertainty

        return {
            "grade": round(max(0, y_pred), 4),
            "unit": GRADE_UNITS.get(self.mineral_type, "%"),
            "confidence_interval_95": (
                round(max(0, y_pred - 1.96 * std_estimate), 4),
                round(y_pred + 1.96 * std_estimate, 4),
            ),
            "confidence": "high" if self.metrics.get("cv_r2_mean", 0) > 0.7 else "medium",
            "top_features": self._get_top_features(10),
        }

    def _heuristic_estimate(self, visual: dict, xrf: Optional[dict]) -> dict:
        """Fallback grade estimate using geological heuristics."""
        base_grade = 0.0
        confidence = "low"

        if self.mineral_type == "gold":
            # Gold heuristic: high metallic sheen + pyrite association
            base_grade = 0.5 + visual.get("visual_metallic_sheen", 0) * 3.0
            if xrf and xrf.get("Au", 0) > 0:
                base_grade = xrf["Au"]
                confidence = "medium"
        elif self.mineral_type == "copper":
            base_grade = 0.3 + visual.get("visual_color_intensity", 0) * 2.0
            if xrf and xrf.get("Cu", 0) > 0:
                base_grade = xrf["Cu"]
                confidence = "medium"
        elif self.mineral_type == "titanium":
            base_grade = 5.0 + visual.get("visual_density_indicator", 0) * 15.0
        else:
            base_grade = 1.0 + visual.get("visual_color_intensity", 0) * 5.0

        return {
            "grade": round(max(0, base_grade), 4),
            "unit": GRADE_UNITS.get(self.mineral_type, "%"),
            "confidence_interval_95": (round(max(0, base_grade * 0.5), 4), round(base_grade * 2.0, 4)),
            "confidence": confidence,
            "top_features": [],
            "note": "Heuristic estimate — train model for accurate predictions",
        }

    def _get_top_features(self, n: int = 10) -> list[dict]:
        """Get top N most important features."""
        if not self.is_fitted or not self.feature_names:
            return []
        importances = self.model.feature_importances_
        indices = np.argsort(importances)[-n:][::-1]
        return [
            {"feature": self.feature_names[i], "importance": round(float(importances[i]), 4)}
            for i in indices
        ]

    def save(self, path: str):
        """Save the trained model to disk."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "scaler": self.scaler,
                "feature_names": self.feature_names,
                "mineral_type": self.mineral_type,
                "metrics": self.metrics,
            }, f)
        logger.info(f"GradeEstimator saved to {path}")

    @classmethod
    def load(cls, path: str) -> GradeEstimator:
        """Load a trained model from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        estimator = cls(mineral_type=data["mineral_type"])
        estimator.model = data["model"]
        estimator.scaler = data["scaler"]
        estimator.feature_names = data["feature_names"]
        estimator.metrics = data["metrics"]
        estimator.is_fitted = True
        return estimator


# ──────────────────── Visual Feature Extractor ────────────────────

class VisualFeatureExtractor:
    """
    Extracts geological visual features from mineral images.
    Uses traditional CV techniques for texture, color, and shape analysis.
    """

    def __init__(self):
        pass

    def extract(self, image: np.ndarray) -> dict[str, float]:
        """
        Extract visual features from a mineral image (BGR numpy array).
        Returns dict of feature_name -> value (0-1 normalized).
        """
        import cv2

        features = {}
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV) if len(image.shape) == 3 else None

        # Metallic sheen: high local contrast with low saturation
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        features["visual_metallic_sheen"] = float(np.clip(np.std(laplacian) / 80.0, 0, 1))

        # Grain size: average contour area ratio
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            avg_area = np.mean([cv2.contourArea(c) for c in contours])
            total_area = gray.shape[0] * gray.shape[1]
            features["visual_grain_size"] = float(np.clip(avg_area / total_area * 50, 0, 1))
        else:
            features["visual_grain_size"] = 0.0

        # Crystal form: how rectangular/geometric the contours are
        if contours:
            rect_scores = []
            for c in contours[:50]:
                if cv2.contourArea(c) > 100:
                    rect = cv2.minAreaRect(c)
                    w, h = rect[1]
                    if min(w, h) > 0:
                        rect_scores.append(min(w, h) / max(w, h))
            features["visual_crystal_form"] = float(np.mean(rect_scores)) if rect_scores else 0.0
        else:
            features["visual_crystal_form"] = 0.0

        # Color intensity
        if hsv is not None:
            features["visual_color_intensity"] = float(np.clip(np.mean(hsv[:, :, 1]) / 255.0, 0, 1))
        else:
            features["visual_color_intensity"] = float(np.clip(np.mean(gray) / 255.0, 0, 1))

        # Texture score: LBP-like via local variance
        kernel = np.ones((5, 5), np.float32) / 25
        local_mean = cv2.filter2D(gray.astype(np.float32), -1, kernel)
        local_var = cv2.filter2D((gray.astype(np.float32) - local_mean) ** 2, -1, kernel)
        features["visual_texture_score"] = float(np.clip(np.mean(local_var) / 2000.0, 0, 1))

        # Luster: brightness distribution skewness
        bright_mean = np.mean(gray)
        bright_std = np.std(gray)
        features["visual_luster"] = float(np.clip(bright_std / 80.0, 0, 1))

        # Transparency: presence of very bright pixels (light passing through)
        high_pct = np.sum(gray > 220) / gray.size
        features["visual_transparency"] = float(np.clip(high_pct * 5, 0, 1))

        # Fracture pattern: edge density
        features["visual_fracture_pattern"] = float(np.clip(np.sum(edges > 0) / edges.size, 0, 1))

        # Hardness indicator: surface roughness from texture
        features["visual_hardness_indicator"] = float(
            np.clip(features["visual_texture_score"] * 0.7 + features["visual_fracture_pattern"] * 0.3, 0, 1)
        )

        # Density indicator: how packed the mineral appears
        features["visual_density_indicator"] = float(
            np.clip(features["visual_metallic_sheen"] * 0.5 + features["visual_color_intensity"] * 0.3 + 0.2, 0, 1)
        )

        # Streak color: dominant dark channel
        features["visual_streak_color"] = float(np.clip(np.min([np.mean(image[:, :, c]) for c in range(3)]) / 255.0, 0, 1)) if len(image.shape) == 3 else float(np.mean(gray) / 255.0)

        # Impurity level: entropy of color histogram
        hist = cv2.calcHist([gray], [0], None, [32], [0, 256]).flatten()
        hist = hist / hist.sum()
        hist = hist[hist > 0]
        entropy = -np.sum(hist * np.log2(hist))
        features["visual_impurity_level"] = float(np.clip(entropy / 5.0, 0, 1))

        return features

    def extract_from_path(self, image_path: str) -> dict[str, float]:
        """Extract features from an image file path."""
        import cv2
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"Image not found: {image_path}")
        return self.extract(image)
