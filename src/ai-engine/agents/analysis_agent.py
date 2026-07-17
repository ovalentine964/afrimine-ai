"""
AfriMine AI — Analysis Agent
Orchestrates mineral classification and grade estimation.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from PIL import Image

from models.classifier import MineralClassifier, create_classifier
from models.grade_estimator import GradeEstimator, VisualFeatureExtractor

logger = logging.getLogger(__name__)


class AnalysisAgent:
    """
    Agent that performs mineral identification and grade estimation.
    Combines CNN classification, visual feature extraction, and XGBoost grade estimation.
    """

    def __init__(self, classifier: Optional[MineralClassifier] = None, gemini_model=None):
        self.name = "Analysis Agent"
        self.role = "Mineral Identification Specialist"
        self.classifier = classifier or create_classifier()
        self.feature_extractor = VisualFeatureExtractor()
        self.gemini = gemini_model
        self.grade_estimators: dict[str, GradeEstimator] = {}

    def analyze_sample(
        self,
        image_path: str,
        xrf_data: Optional[dict] = None,
        location: Optional[dict] = None,
    ) -> dict:
        """
        Complete analysis pipeline for a single mineral sample.

        Steps:
        1. Load and classify mineral image
        2. Extract visual features
        3. Estimate grade
        4. Generate analysis summary

        Returns comprehensive analysis dict.
        """
        logger.info(f"Analyzing sample: {image_path}")

        # Step 1: Mineral classification
        classification = self.classifier.predict(image_path)
        mineral_name = classification["mineral"]
        logger.info(f"Classified as: {mineral_name} ({classification['confidence']:.2%})")

        # Step 2: Visual feature extraction
        import cv2
        image = cv2.imread(image_path)
        visual_features = self.feature_extractor.extract(image) if image is not None else {}

        # Step 3: Grade estimation
        grade_result = self._estimate_grade(mineral_name, visual_features, xrf_data)

        # Step 4: Build comprehensive result
        result = {
            "sample_id": location.get("sample_id", "unknown") if location else "unknown",
            "classification": classification,
            "visual_features": visual_features,
            "grade_estimation": grade_result,
            "location": location or {},
            "xrf_data": xrf_data,
            "confidence_level": self._overall_confidence(classification, grade_result, xrf_data),
            "recommendation": self._generate_recommendation(classification, grade_result),
        }

        return result

    def analyze_batch(
        self,
        samples: list[dict],
    ) -> list[dict]:
        """
        Analyze multiple samples.
        Each sample: {image_path, xrf_data (opt), location (opt)}
        """
        results = []
        for sample in samples:
            try:
                result = self.analyze_sample(
                    image_path=sample["image_path"],
                    xrf_data=sample.get("xrf_data"),
                    location=sample.get("location"),
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to analyze {sample.get('image_path')}: {e}")
                results.append({
                    "sample_id": sample.get("location", {}).get("sample_id", "unknown"),
                    "error": str(e),
                    "status": "failed",
                })

        logger.info(f"Batch analysis complete: {len(results)} samples, {sum(1 for r in results if 'error' not in r)} successful")
        return results

    def _estimate_grade(
        self,
        mineral_name: str,
        visual_features: dict,
        xrf_data: Optional[dict],
    ) -> dict:
        """Estimate grade for a classified mineral."""
        if mineral_name not in self.grade_estimators:
            self.grade_estimators[mineral_name] = GradeEstimator(mineral_type=mineral_name)

        estimator = self.grade_estimators[mineral_name]
        return estimator.predict(
            visual_features=visual_features,
            xrf_data=xrf_data,
        )

    def _overall_confidence(self, classification: dict, grade: dict, xrf: Optional[dict]) -> str:
        """Determine overall analysis confidence level."""
        class_conf = classification.get("confidence", 0)
        grade_conf = grade.get("confidence", "low")

        score = class_conf * 40  # max 40
        if grade_conf == "high":
            score += 30
        elif grade_conf == "medium":
            score += 20
        else:
            score += 10
        if xrf:
            score += 30  # XRF data significantly boosts confidence

        if score >= 70:
            return "high"
        elif score >= 45:
            return "medium"
        return "low"

    def _generate_recommendation(self, classification: dict, grade: dict) -> str:
        """Generate actionable recommendation based on analysis."""
        mineral = classification.get("mineral", "unknown")
        confidence = classification.get("confidence", 0)
        grade_val = grade.get("grade", 0)
        unit = grade.get("unit", "%")

        if confidence < 0.4:
            return f"Low confidence ({confidence:.0%}) — recommend additional sampling and XRF analysis"

        if mineral == "gold":
            if grade_val > 5:
                return f"High-grade gold ({grade_val} {unit}) — recommend immediate detailed exploration"
            elif grade_val > 1:
                return f"Moderate gold grade ({grade_val} {unit}) — recommend expanded sampling programme"
            else:
                return f"Low gold grade ({grade_val} {unit}) — area may not be economically viable"

        if mineral in ("ruby", "sapphire"):
            return f"Precious gemstone detected — recommend gemmological assessment and carat weight estimation"

        return f"Sample classified as {mineral} at {grade_val} {unit} — recommend further geological assessment"

    def get_classified_summary(self, results: list[dict]) -> dict:
        """Generate a summary of a batch analysis."""
        mineral_counts = {}
        total_value_score = 0
        successful = 0

        for r in results:
            if "error" in r:
                continue
            successful += 1
            mineral = r.get("classification", {}).get("mineral", "unknown")
            mineral_counts[mineral] = mineral_counts.get(mineral, 0) + 1
            total_value_score += r.get("classification", {}).get("value_score", 0)

        return {
            "total_samples": len(results),
            "successful": successful,
            "failed": len(results) - successful,
            "mineral_distribution": mineral_counts,
            "average_value_score": round(total_value_score / max(successful, 1), 3),
            "dominant_mineral": max(mineral_counts, key=mineral_counts.get) if mineral_counts else None,
        }
