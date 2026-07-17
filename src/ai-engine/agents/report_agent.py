"""
AfriMine AI — Report Agent
Generates comprehensive PDF and text reports using Gemini API and ReportLab.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ReportAgent:
    """
    Agent that generates comprehensive mineral analysis reports.
    Combines data from all other agents into professional PDF documents.
    """

    def __init__(self, gemini_model=None):
        self.name = "Report Agent"
        self.role = "Report Generation Specialist"
        self.gemini = gemini_model

    def generate_comprehensive_report(
        self,
        analysis_results: list[dict],
        geological_context: dict,
        market_data: dict,
        sampling_plan: Optional[dict] = None,
        compliance_status: Optional[dict] = None,
    ) -> dict:
        """
        Generate a comprehensive mineral exploration report.

        Returns:
            {report_text, report_path, summary}
        """
        # Build report sections
        sections = {
            "executive_summary": self._executive_summary(analysis_results, market_data),
            "methodology": self._methodology_section(sampling_plan),
            "geological_context": self._geological_section(geological_context),
            "mineral_analysis": self._analysis_section(analysis_results),
            "grade_assessment": self._grade_section(analysis_results),
            "economic_evaluation": self._economic_section(market_data),
            "compliance": self._compliance_section(compliance_status),
            "recommendations": self._recommendations(analysis_results, geological_context, market_data),
        }

        # Compile full text report
        report_text = self._compile_text_report(sections)

        # Generate PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = f"output/report_{timestamp}.pdf"
        self._generate_pdf(sections, pdf_path)

        # Generate executive summary for Gemini enhancement
        enhanced_summary = None
        if self.gemini:
            enhanced_summary = self._enhance_with_gemini(report_text)

        return {
            "report_text": report_text,
            "report_path": pdf_path,
            "sections": sections,
            "enhanced_summary": enhanced_summary,
            "generated_at": datetime.now().isoformat(),
        }

    def _executive_summary(self, results: list[dict], market: dict) -> str:
        """Generate executive summary section."""
        total = len(results)
        successful = sum(1 for r in results if "error" not in r)
        minerals = list(set(r.get("classification", {}).get("mineral", "unknown") for r in results if "error" not in r))

        lines = [
            "EXECUTIVE SUMMARY",
            "=" * 40,
            f"Total samples analyzed: {total}",
            f"Successful identifications: {successful}",
            f"Minerals identified: {', '.join(minerals)}",
            "",
        ]

        # Value assessment
        if market and "minerals" in market:
            high_value = []
            for m in minerals:
                price = market.get("minerals", {}).get(m, {})
                if isinstance(price, dict) and price.get("price_usd", 0) > 100:
                    high_value.append(m)
            if high_value:
                lines.append(f"High-value minerals detected: {', '.join(high_value)}")

        return "\n".join(lines)

    def _methodology_section(self, sampling: Optional[dict]) -> str:
        lines = ["METHODOLOGY", "=" * 40]
        if sampling:
            lines.extend([
                f"Sampling grid: {sampling.get('grid_type', 'regular')}",
                f"Grid spacing: {sampling.get('spacing_m', 500)}m",
                f"Total sample points: {sampling.get('total_points', 'N/A')}",
                f"Field days: {sampling.get('days', 'N/A')}",
            ])
        else:
            lines.append("Sampling methodology: As per field team protocol")
        lines.extend([
            "",
            "Analysis Pipeline:",
            "1. Image capture with standardized lighting",
            "2. CNN mineral classification (EfficientNet-B2)",
            "3. Visual feature extraction (texture, color, crystal form)",
            "4. Grade estimation (XGBoost with XRF data integration)",
            "5. Geological interpretation and market evaluation",
        ])
        return "\n".join(lines)

    def _geological_section(self, geo: dict) -> str:
        lines = ["GEOLOGICAL CONTEXT", "=" * 40]
        if not geo:
            return "\n".join(lines + ["No geological data available."])

        if "geological_provinces" in geo:
            for prov in geo["geological_provinces"][:3]:
                lines.append(f"\nProvince: {prov.get('province', 'Unknown')}")
                lines.append(f"  {prov.get('description', '')}")
                lines.append(f"  Formation Age: {prov.get('formation_age', 'Unknown')}")
                lines.append(f"  Rock Types: {', '.join(prov.get('rock_types', []))}")

        if "associations" in geo:
            lines.append("\nMineral Associations:")
            for assoc in geo["associations"]:
                lines.append(f"  - {assoc.get('description', '')} — {assoc.get('significance', '')}")

        return "\n".join(lines)

    def _analysis_section(self, results: list[dict]) -> str:
        lines = ["MINERAL ANALYSIS RESULTS", "=" * 40]
        for i, r in enumerate(results):
            if "error" in r:
                lines.append(f"\nSample {i+1}: FAILED — {r['error']}")
                continue
            cls = r.get("classification", {})
            lines.extend([
                f"\nSample {i+1} — {r.get('sample_id', 'N/A')}",
                f"  Mineral: {cls.get('mineral', 'unknown').title()}",
                f"  Confidence: {cls.get('confidence', 0):.1%}",
                f"  Category: {cls.get('category', 'unknown')}",
                f"  Value Score: {cls.get('value_score', 0):.2f}",
                f"  Overall Confidence: {r.get('confidence_level', 'unknown')}",
            ])
            if "top5" in cls:
                lines.append("  Top 5 candidates:")
                for t in cls["top5"]:
                    lines.append(f"    - {t['name']}: {t['confidence']:.1%}")
        return "\n".join(lines)

    def _grade_section(self, results: list[dict]) -> str:
        lines = ["GRADE ASSESSMENT", "=" * 40]
        for i, r in enumerate(results):
            if "error" in r:
                continue
            grade = r.get("grade_estimation", {})
            mineral = r.get("classification", {}).get("mineral", "unknown")
            lines.extend([
                f"\n{mineral.title()} (Sample {i+1}):",
                f"  Grade: {grade.get('grade', 'N/A')} {grade.get('unit', '')}",
                f"  95% CI: {grade.get('confidence_interval_95', ('N/A', 'N/A'))}",
                f"  Confidence: {grade.get('confidence', 'unknown')}",
            ])
            top_feats = grade.get("top_features", [])
            if top_feats:
                lines.append(f"  Key feature: {top_feats[0].get('feature', '')}")
        return "\n".join(lines)

    def _economic_section(self, market: dict) -> str:
        lines = ["ECONOMIC EVALUATION", "=" * 40]
        if not market:
            return "\n".join(lines + ["No market data available."])

        if "viability" in market:
            v = market["viability"]
            lines.extend([
                f"Viability: {v.get('viability', 'unknown')}",
                f"Revenue per tonne: ${v.get('revenue_per_tonne_usd', 0):.2f}",
                f"Profit per tonne: ${v.get('profit_per_tonne_usd', 0):.2f}",
                f"Total estimated profit: ${v.get('total_profit_usd', 0):,.2f}",
                f"Profit margin: {v.get('profit_margin_pct', 0):.1f}%",
            ])
        elif "minerals" in market:
            for mineral, price in market["minerals"].items():
                if isinstance(price, dict) and "error" not in price:
                    lines.append(f"  {mineral.title()}: ${price.get('price_usd', 0)}/{price.get('unit', '')}")
        return "\n".join(lines)

    def _compliance_section(self, compliance: Optional[dict]) -> str:
        lines = ["COMPLIANCE STATUS", "=" * 40]
        if not compliance:
            lines.append("Compliance check not performed.")
            return "\n".join(lines)

        status = compliance.get("overall_status", "unknown")
        lines.append(f"Overall Status: {status.upper()}")
        for item in compliance.get("checks", []):
            icon = "✓" if item.get("status") == "pass" else "✗"
            lines.append(f"  {icon} {item.get('check', '')}: {item.get('status', '')}")
        return "\n".join(lines)

    def _recommendations(self, results: list, geo: dict, market: dict) -> str:
        lines = ["RECOMMENDATIONS", "=" * 40]
        recommendations = []

        # From analysis results
        for r in results:
            if "error" not in r and r.get("recommendation"):
                recommendations.append(r["recommendation"])

        # From market data
        if market and "viability" in market:
            v = market["viability"]
            if v.get("viability") == "economically_viable":
                recommendations.append("Deposit is economically viable — recommend feasibility study")
            elif v.get("viability") == "marginal":
                recommendations.append("Deposit is marginal — further exploration may improve economics")

        if not recommendations:
            recommendations.append("Insufficient data for specific recommendations — expand sampling programme")

        for i, rec in enumerate(recommendations[:10], 1):
            lines.append(f"{i}. {rec}")

        return "\n".join(lines)

    def _compile_text_report(self, sections: dict) -> str:
        header = [
            "=" * 60,
            "AFRIMINE AI — MINERAL ANALYSIS REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            "",
        ]
        body = []
        for section_name, content in sections.items():
            body.append(content)
            body.append("")
            body.append("-" * 40)
            body.append("")
        return "\n".join(header + body)

    def _generate_pdf(self, sections: dict, output_path: str):
        """Generate PDF report using ReportLab."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            styles = getSampleStyleSheet()

            title_style = ParagraphStyle(
                "ReportTitle", parent=styles["Title"],
                fontSize=18, spaceAfter=20, textColor=colors.HexColor("#1a472a")
            )
            heading_style = ParagraphStyle(
                "SectionHeading", parent=styles["Heading2"],
                fontSize=14, spaceBefore=16, spaceAfter=8,
                textColor=colors.HexColor("#2d6a4f")
            )
            body_style = ParagraphStyle(
                "BodyText", parent=styles["Normal"],
                fontSize=10, spaceBefore=4, spaceAfter=4
            )

            story = []
            story.append(Paragraph("AfriMine AI — Mineral Analysis Report", title_style))
            story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", body_style))
            story.append(Spacer(1, 20))

            for section_name, content in sections.items():
                title = section_name.replace("_", " ").title()
                story.append(Paragraph(title, heading_style))
                for line in content.split("\n"):
                    if line.strip():
                        story.append(Paragraph(line.replace("=", "").replace("-", "").strip(), body_style))
                story.append(Spacer(1, 12))

            doc.build(story)
            logger.info(f"PDF report generated: {output_path}")

        except ImportError:
            logger.warning("ReportLab not installed — PDF not generated")
            # Fallback: save as text
            txt_path = output_path.replace(".pdf", ".txt")
            Path(txt_path).parent.mkdir(parents=True, exist_ok=True)
            with open(txt_path, "w") as f:
                f.write(self._compile_text_report(sections))
            logger.info(f"Text report saved: {txt_path}")

    def _enhance_with_gemini(self, report_text: str) -> Optional[str]:
        """Use Gemini to enhance the report with natural language insights."""
        try:
            prompt = (
                "You are a mining geologist reviewing this mineral analysis report from Kenya. "
                "Provide a concise executive briefing (3-5 paragraphs) highlighting:\n"
                "1. Key findings and their significance\n"
                "2. Economic potential\n"
                "3. Recommended next steps\n"
                "4. Risk factors\n\n"
                f"Report:\n{report_text[:4000]}"
            )
            response = self.gemini.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.warning(f"Gemini enhancement failed: {e}")
            return None
