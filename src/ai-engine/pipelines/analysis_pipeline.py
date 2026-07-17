"""
AfriMine AI — Analysis Pipeline
End-to-end pipeline connecting sampling, analysis, geology, market, and compliance agents.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from agents.sampling_agent import SamplingAgent
from agents.analysis_agent import AnalysisAgent
from agents.geology_agent import GeologyAgent
from agents.market_agent import MarketAgent
from agents.compliance_agent import ComplianceAgent
from agents.report_agent import ReportAgent
from models.classifier import create_classifier, load_classifier
from utils.config import AfriMineConfig

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """
    Orchestrates the full mineral analysis workflow:
    1. Sampling plan generation
    2. Mineral classification and grade estimation
    3. Geological interpretation
    4. Market/economic analysis
    5. Compliance verification
    6. Report generation
    """

    def __init__(self, config: AfriMineConfig):
        self.config = config

        # Initialize classifier
        if config.model.checkpoint_path:
            self.classifier = load_classifier(config.model.checkpoint_path, config.model)
        else:
            self.classifier = create_classifier(config.model)

        # Initialize Gemini model if API key available
        self.gemini = None
        if config.agents.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=config.agents.gemini_api_key)
                self.gemini = genai.GenerativeModel(config.agents.gemini_model)
                logger.info(f"Gemini model initialized: {config.agents.gemini_model}")
            except Exception as e:
                logger.warning(f"Gemini initialization failed: {e}")

        # Initialize agents
        self.sampling_agent = SamplingAgent(gemini_model=self.gemini)
        self.analysis_agent = AnalysisAgent(classifier=self.classifier, gemini_model=self.gemini)
        self.geology_agent = GeologyAgent(gemini_model=self.gemini)
        self.market_agent = MarketAgent(gemini_model=self.gemini)
        self.compliance_agent = ComplianceAgent(gemini_model=self.gemini)
        self.report_agent = ReportAgent(gemini_model=self.gemini)

    def run_full_pipeline(
        self,
        area: dict,
        sample_images: list[dict],
        xrf_data: Optional[dict] = None,
        miner_info: Optional[dict] = None,
        licence_type: str = "exploration_licence",
    ) -> dict:
        """
        Run the complete analysis pipeline.

        Args:
            area: {lat_min, lat_max, lon_min, lon_max, county}
            sample_images: list of {image_path, xrf_data (opt), location (opt)}
            xrf_data: optional XRF data dict
            miner_info: {name, nationality, county}
            licence_type: licence type for compliance check

        Returns:
            Complete pipeline results dict
        """
        logger.info("=" * 60)
        logger.info("AFRIMINE AI — Starting Full Analysis Pipeline")
        logger.info("=" * 60)

        results = {
            "area": area,
            "pipeline_start": __import__("datetime").datetime.now().isoformat(),
        }

        # ── Step 1: Sampling Plan ──
        logger.info("[Step 1/6] Generating sampling plan...")
        sampling_points = self.sampling_agent.generate_sampling_grid(
            lat_min=area.get("lat_min", -1.0),
            lat_max=area.get("lat_max", 0.0),
            lon_min=area.get("lon_min", 36.0),
            lon_max=area.get("lon_max", 37.0),
            spacing_m=area.get("spacing_m", 500),
        )
        route = self.sampling_agent.optimize_route(
            sampling_points,
            start_lat=area.get("lat_min", -1.0),
            start_lon=area.get("lon_min", 36.0),
        )
        sampling_report = self.sampling_agent.generate_report(sampling_points, route)
        results["sampling"] = {
            "points": len(sampling_points),
            "route_days": max(r.get("day", 1) for r in route) if route else 0,
            "report": sampling_report,
        }

        # ── Step 2: Mineral Analysis ──
        logger.info("[Step 2/6] Running mineral analysis...")
        analysis_results = self.analysis_agent.analyze_batch(sample_images)
        analysis_summary = self.analysis_agent.get_classified_summary(analysis_results)
        results["analysis"] = {
            "samples": analysis_results,
            "summary": analysis_summary,
        }

        # ── Step 3: Geological Interpretation ──
        logger.info("[Step 3/6] Interpreting geological context...")
        minerals_found = list(set(
            r.get("classification", {}).get("mineral", "unknown")
            for r in analysis_results if "error" not in r
        ))
        location = {
            "lat": (area.get("lat_min", 0) + area.get("lat_max", 0)) / 2,
            "lon": (area.get("lon_min", 0) + area.get("lon_max", 0)) / 2,
            "county": area.get("county", ""),
        }
        geological = self.geology_agent.interpret_mineral_assemblage(minerals_found, location)
        geo_report = self.geology_agent.generate_geological_report(analysis_results, location)
        results["geology"] = {
            "context": geological,
            "report": geo_report,
        }

        # ── Step 4: Market Analysis ──
        logger.info("[Step 4/6] Running market analysis...")
        market_summary = self.market_agent.get_market_summary(minerals_found)
        # Calculate viability for dominant mineral
        if analysis_summary.get("dominant_mineral"):
            dominant = analysis_summary["dominant_mineral"]
            avg_grade = self._average_grade(analysis_results, dominant)
            grade_unit = self._get_grade_unit(analysis_results, dominant)
            viability = self.market_agent.calculate_economic_viability(
                dominant, avg_grade, grade_unit, 1000
            )
            market_summary["viability"] = viability
        market_report = self.market_agent.generate_market_report(analysis_results)
        results["market"] = {
            "summary": market_summary,
            "report": market_report,
        }

        # ── Step 5: Compliance Check ──
        logger.info("[Step 5/6] Checking compliance...")
        if miner_info:
            compliance = self.compliance_agent.check_compliance(
                licence_type=licence_type,
                miner_info=miner_info,
                operation_details={
                    "mineral": analysis_summary.get("dominant_mineral", "unknown"),
                    "has_licence": miner_info.get("has_licence", False),
                    "licence_expiry": miner_info.get("licence_expiry", ""),
                    "eia_licence": miner_info.get("eia_licence", False),
                    "emp_submitted": miner_info.get("emp_submitted", False),
                    "safety_plan": miner_info.get("safety_plan", False),
                    "worker_training": miner_info.get("worker_training", False),
                    "ppe_available": miner_info.get("ppe_available", False),
                    "royalties_current": miner_info.get("royalties_current", False),
                    "community_development_agreement": miner_info.get("cda", False),
                    "designated_area": miner_info.get("designated_area", False),
                },
            )
        else:
            compliance = {"overall_status": "not_checked", "checks": []}
        results["compliance"] = compliance

        # ── Step 6: Report Generation ──
        logger.info("[Step 6/6] Generating report...")
        report = self.report_agent.generate_comprehensive_report(
            analysis_results=analysis_results,
            geological_context=geological,
            market_data=market_summary,
            sampling_plan={"total_points": len(sampling_points), "days": results["sampling"]["route_days"]},
            compliance_status=compliance,
        )
        results["report"] = {
            "text": report["report_text"],
            "path": report.get("report_path"),
            "enhanced_summary": report.get("enhanced_summary"),
        }

        results["pipeline_end"] = __import__("datetime").datetime.now().isoformat()
        results["status"] = "completed"

        logger.info("=" * 60)
        logger.info("AFRIMINE AI — Pipeline Complete")
        logger.info(f"Samples: {analysis_summary.get('total_samples', 0)}")
        logger.info(f"Minerals: {', '.join(minerals_found)}")
        logger.info(f"Report: {report.get('report_path', 'N/A')}")
        logger.info("=" * 60)

        return results

    def run_single_sample(self, image_path: str, xrf_data: Optional[dict] = None, location: Optional[dict] = None) -> dict:
        """Quick analysis of a single sample."""
        analysis = self.analysis_agent.analyze_sample(image_path, xrf_data, location)
        mineral = analysis.get("classification", {}).get("mineral", "unknown")

        # Geological context
        geo = {}
        if location:
            geo = self.geology_agent.interpret_mineral_assemblage([mineral], location)

        # Market price
        price = self.market_agent.get_price(mineral)

        # Grade viability
        grade_info = analysis.get("grade_estimation", {})
        viability = self.market_agent.calculate_economic_viability(
            mineral, grade_info.get("grade", 0), grade_info.get("unit", "%"), 100
        )

        return {
            "analysis": analysis,
            "geological_context": geo,
            "market_price": price,
            "viability": viability,
        }

    @staticmethod
    def _average_grade(results: list[dict], mineral: str) -> float:
        grades = [
            r.get("grade_estimation", {}).get("grade", 0)
            for r in results
            if "error" not in r and r.get("classification", {}).get("mineral") == mineral
        ]
        return sum(grades) / max(len(grades), 1)

    @staticmethod
    def _get_grade_unit(results: list[dict], mineral: str) -> str:
        for r in results:
            if "error" not in r and r.get("classification", {}).get("mineral") == mineral:
                return r.get("grade_estimation", {}).get("unit", "%")
        return "%"
