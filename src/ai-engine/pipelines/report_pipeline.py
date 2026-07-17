"""
AfriMine AI — Report Pipeline
Handles report generation with multiple output formats.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ReportPipeline:
    """
    Dedicated pipeline for generating, formatting, and distributing reports.
    Supports PDF, text, JSON, and CSV output formats.
    """

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def generate_all_formats(self, pipeline_results: dict) -> dict[str, str]:
        """Generate reports in all supported formats."""
        paths = {}

        # Text report
        paths["text"] = self._save_text(pipeline_results)

        # JSON report
        paths["json"] = self._save_json(pipeline_results)

        # CSV summary
        paths["csv"] = self._save_csv_summary(pipeline_results)

        # PDF (via report agent)
        report_data = pipeline_results.get("report", {})
        if report_data.get("path"):
            paths["pdf"] = report_data["path"]

        logger.info(f"Reports generated: {list(paths.keys())}")
        return paths

    def _save_text(self, results: dict) -> str:
        """Save full text report."""
        path = self.output_dir / f"afrimine_report_{self.timestamp}.txt"
        text = results.get("report", {}).get("text", "No report text available")
        with open(path, "w") as f:
            f.write(text)
        return str(path)

    def _save_json(self, results: dict) -> str:
        """Save structured JSON report."""
        path = self.output_dir / f"afrimine_report_{self.timestamp}.json"

        # Make results JSON-serializable
        serializable = self._make_serializable(results)
        with open(path, "w") as f:
            json.dump(serializable, f, indent=2, default=str)
        return str(path)

    def _save_csv_summary(self, results: dict) -> str:
        """Save sample analysis summary as CSV."""
        path = self.output_dir / f"afrimine_summary_{self.timestamp}.csv"

        samples = results.get("analysis", {}).get("samples", [])
        if not samples:
            return str(path)

        lines = [
            "sample_id,mineral,confidence,grade,grade_unit,value_score,confidence_level"
        ]
        for s in samples:
            if "error" in s:
                continue
            cls = s.get("classification", {})
            grade = s.get("grade_estimation", {})
            lines.append(
                f"{s.get('sample_id', 'N/A')},"
                f"{cls.get('mineral', 'unknown')},"
                f"{cls.get('confidence', 0):.4f},"
                f"{grade.get('grade', 0)},"
                f"{grade.get('unit', '')},"
                f"{cls.get('value_score', 0)},"
                f"{s.get('confidence_level', 'unknown')}"
            )

        with open(path, "w") as f:
            f.write("\n".join(lines))
        return str(path)

    def _make_serializable(self, obj):
        """Recursively convert objects to JSON-serializable types."""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(v) for v in obj]
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        elif hasattr(obj, '__dict__'):
            return self._make_serializable(obj.__dict__)
        else:
            return str(obj)
