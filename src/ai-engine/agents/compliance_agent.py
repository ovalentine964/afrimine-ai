"""
AfriMine AI — Compliance Agent
Kenya Mining Act and regulatory compliance checks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# Kenya Mining Act 2016 key requirements
KENYA_MINING_REQUIREMENTS = {
    "mining_licence": {
        "description": "Mining Licence under the Mining Act 2016",
        "authority": "Mining Rights Board / Cabinet Secretary",
        "validity_years": 25,
        "renewable": True,
        "conditions": [
            "Environmental Impact Assessment (EIA) licence",
            "Community Development Agreement (CDA)",
            "Annual work programme submitted",
            "Royalty payments current",
        ],
    },
    "exploration_licence": {
        "description": "Exploration Licence under the Mining Act 2016",
        "authority": "Mining Rights Board",
        "validity_years": 3,
        "renewable": True,
        "conditions": [
            "Minimum expenditure commitments met",
            "Annual reports submitted",
            "Environmental mitigation plan in place",
        ],
    },
    "artisanal_mining_permit": {
        "description": "Artisanal Mining Permit for small-scale miners",
        "authority": "County Government / Mining Rights Board",
        "validity_years": 5,
        "renewable": True,
        "conditions": [
            "Kenyan citizen",
            "Mining in designated artisanal mining area",
            "Environmental compliance",
            "Safety measures in place",
        ],
    },
    "royalty_rates": {
        "gold": 0.05,       # 5% of gross value
        "copper": 0.05,
        "titanium": 0.05,
        "ruby": 0.05,
        "sapphire": 0.05,
        "graphite": 0.03,
        "fluorite": 0.03,
        "limestone": 0.03,
        "soda_ash": 0.03,
        "default": 0.05,
    },
    "environmental_requirements": [
        "Environmental Impact Assessment (EIA) by NEMA",
        "Environmental Management Plan (EMP)",
        "Water use permit from WRMA",
        "Air quality monitoring",
        "Waste management plan",
        "Rehabilitation and restoration plan",
        "Community health and safety plan",
    ],
    "safety_requirements": [
        "Mine Health and Safety Act compliance",
        "Regular safety inspections",
        "Worker safety training",
        "Emergency response plan",
        "Personal protective equipment",
        "Mine ventilation (underground)",
        "Ground stability monitoring",
    ],
}


class ComplianceAgent:
    """
    Agent that checks mining regulatory compliance under Kenya's Mining Act 2016.
    """

    def __init__(self, gemini_model=None):
        self.name = "Compliance Agent"
        self.role = "Regulatory Compliance Specialist"
        self.gemini = gemini_model
        self.requirements = KENYA_MINING_REQUIREMENTS

    def check_compliance(
        self,
        licence_type: str,
        miner_info: dict,
        operation_details: dict,
    ) -> dict:
        """
        Run a comprehensive compliance check.

        Args:
            licence_type: 'mining_licence', 'exploration_licence', 'artisanal_mining_permit'
            miner_info: {name, nationality, county, ...}
            operation_details: {mineral, scale, environmental_clearance, ...}
        """
        checks = []

        # 1. Licence validity
        licence_check = self._check_licence(licence_type, miner_info, operation_details)
        checks.append(licence_check)

        # 2. Environmental compliance
        env_check = self._check_environmental(operation_details)
        checks.append(env_check)

        # 3. Safety compliance
        safety_check = self._check_safety(operation_details)
        checks.append(safety_check)

        # 4. Royalty obligations
        royalty_check = self._check_royalties(operation_details)
        checks.append(royalty_check)

        # 5. Community obligations
        community_check = self._check_community(operation_details)
        checks.append(community_check)

        # 6. Artisanal mining specific
        if licence_type == "artisanal_mining_permit":
            artisanal_check = self._check_artisanal(miner_info)
            checks.append(artisanal_check)

        # Overall status
        failed = sum(1 for c in checks if c["status"] == "fail")
        warned = sum(1 for c in checks if c["status"] == "warning")
        if failed > 0:
            overall = "non_compliant"
        elif warned > 0:
            overall = "partial_compliance"
        else:
            overall = "compliant"

        return {
            "overall_status": overall,
            "licence_type": licence_type,
            "checks": checks,
            "failed_count": failed,
            "warning_count": warned,
            "action_items": self._generate_action_items(checks),
            "next_review_date": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
            "generated_at": datetime.now().isoformat(),
        }

    def calculate_royalties(self, mineral: str, gross_value_usd: float) -> dict:
        """Calculate royalty obligation under Kenya Mining Act."""
        rate = self.requirements["royalty_rates"].get(
            mineral.lower(),
            self.requirements["royalty_rates"]["default"]
        )
        royalty_usd = gross_value_usd * rate
        royalty_kes = royalty_usd * 155.0  # approximate USD/KES

        return {
            "mineral": mineral,
            "gross_value_usd": gross_value_usd,
            "royalty_rate": rate,
            "royalty_usd": round(royalty_usd, 2),
            "royalty_kes": round(royalty_kes, 2),
            "payment_frequency": "Quarterly",
            "authority": "Kenya Revenue Authority (KRA)",
            "reference": "Mining Act 2016, Section 146",
        }

    def get_permit_requirements(self, licence_type: str) -> dict:
        """Get detailed permit requirements for a licence type."""
        permit = self.requirements.get(licence_type, {})
        return {
            "licence_type": licence_type,
            "description": permit.get("description", "Unknown"),
            "authority": permit.get("authority", "Unknown"),
            "validity_years": permit.get("validity_years", 0),
            "renewable": permit.get("renewable", False),
            "conditions": permit.get("conditions", []),
            "application_documents": self._required_documents(licence_type),
            "estimated_timeline": self._processing_timeline(licence_type),
            "fees": self._permit_fees(licence_type),
        }

    def generate_compliance_report(self, compliance_result: dict) -> str:
        """Generate a human-readable compliance report."""
        lines = [
            "# AfriMine AI — Compliance Report",
            "",
            f"## Overall Status: {compliance_result['overall_status'].upper()}",
            f"Licence Type: {compliance_result['licence_type']}",
            f"Next Review: {compliance_result.get('next_review_date', 'N/A')}",
            "",
            "## Compliance Checks",
        ]

        for check in compliance_result.get("checks", []):
            icon = "✓" if check["status"] == "pass" else ("⚠" if check["status"] == "warning" else "✗")
            lines.append(f"\n{icon} **{check['check']}**: {check['status'].upper()}")
            if check.get("details"):
                lines.append(f"  {check['details']}")
            if check.get("requirements"):
                for req in check["requirements"]:
                    met = "✓" if req.get("met") else "✗"
                    lines.append(f"  {met} {req['item']}")

        action_items = compliance_result.get("action_items", [])
        if action_items:
            lines.append("\n## Action Items")
            for i, item in enumerate(action_items, 1):
                lines.append(f"{i}. [{item['priority'].upper()}] {item['action']}")

        return "\n".join(lines)

    def _check_licence(self, licence_type: str, miner: dict, ops: dict) -> dict:
        """Check licence status."""
        has_licence = ops.get("has_licence", False)
        licence_valid = ops.get("licence_expiry", "") > datetime.now().strftime("%Y-%m-%d")

        requirements = []
        if licence_type == "artisanal_mining_permit":
            requirements.append({
                "item": "Kenyan citizenship",
                "met": miner.get("nationality", "").lower() == "kenyan",
            })

        if not has_licence:
            return {
                "check": "Licence Status",
                "status": "fail",
                "details": f"No valid {licence_type} found",
                "requirements": requirements,
            }
        elif not licence_valid:
            return {
                "check": "Licence Status",
                "status": "fail",
                "details": "Licence has expired",
                "requirements": requirements,
            }
        return {
            "check": "Licence Status",
            "status": "pass",
            "details": f"Valid {licence_type} on file",
            "requirements": requirements,
        }

    def _check_environmental(self, ops: dict) -> dict:
        """Check environmental compliance."""
        eia = ops.get("eia_licence", False)
        emp = ops.get("emp_submitted", False)

        status = "pass" if (eia and emp) else "fail"
        requirements = [
            {"item": "EIA Licence from NEMA", "met": eia},
            {"item": "Environmental Management Plan", "met": emp},
        ]

        return {
            "check": "Environmental Compliance",
            "status": status,
            "details": "EIA and EMP status verified",
            "requirements": requirements,
        }

    def _check_safety(self, ops: dict) -> dict:
        """Check safety compliance."""
        safety_plan = ops.get("safety_plan", False)
        training = ops.get("worker_training", False)
        ppe = ops.get("ppe_available", False)

        met_count = sum([safety_plan, training, ppe])
        if met_count == 3:
            status = "pass"
        elif met_count >= 1:
            status = "warning"
        else:
            status = "fail"

        return {
            "check": "Health & Safety",
            "status": status,
            "details": f"{met_count}/3 safety requirements met",
            "requirements": [
                {"item": "Mine safety plan", "met": safety_plan},
                {"item": "Worker safety training", "met": training},
                {"item": "PPE availability", "met": ppe},
            ],
        }

    def _check_royalties(self, ops: dict) -> dict:
        """Check royalty payment status."""
        current = ops.get("royalties_current", False)
        return {
            "check": "Royalty Payments",
            "status": "pass" if current else "warning",
            "details": "Royalty payment status verified" if current else "Royalty payment status unclear",
            "requirements": [
                {"item": "Quarterly royalty returns filed", "met": current},
            ],
        }

    def _check_community(self, ops: dict) -> dict:
        """Check community development obligations."""
        cda = ops.get("community_development_agreement", False)
        return {
            "check": "Community Development",
            "status": "pass" if cda else "warning",
            "details": "CDA in place" if cda else "Community Development Agreement not confirmed",
            "requirements": [
                {"item": "Community Development Agreement (CDA)", "met": cda},
            ],
        }

    def _check_artisanal(self, miner: dict) -> dict:
        """Artisanal mining specific checks."""
        citizen = miner.get("nationality", "").lower() == "kenyan"
        designated = miner.get("designated_area", False)

        return {
            "check": "Artisanal Mining Requirements",
            "status": "pass" if (citizen and designated) else "fail",
            "details": "Artisanal mining eligibility",
            "requirements": [
                {"item": "Kenyan citizen", "met": citizen},
                {"item": "Operating in designated artisanal area", "met": designated},
            ],
        }

    def _generate_action_items(self, checks: list[dict]) -> list[dict]:
        """Generate prioritized action items from failed/warning checks."""
        items = []
        for check in checks:
            if check["status"] == "fail":
                items.append({
                    "priority": "critical",
                    "action": f"Address {check['check']}: {check.get('details', '')}",
                    "check": check["check"],
                })
            elif check["status"] == "warning":
                items.append({
                    "priority": "medium",
                    "action": f"Review {check['check']}: {check.get('details', '')}",
                    "check": check["check"],
                })

            for req in check.get("requirements", []):
                if not req.get("met"):
                    items.append({
                        "priority": "high" if check["status"] == "fail" else "medium",
                        "action": f"Obtain/complete: {req['item']}",
                        "check": check["check"],
                    })

        return items

    def _required_documents(self, licence_type: str) -> list[str]:
        base = ["National ID / Passport", "KRA PIN Certificate", "Proof of mining site"]
        if licence_type == "mining_licence":
            base.extend(["EIA Licence", "Mining scheme", "Financial capability proof", "Technical competence evidence"])
        elif licence_type == "exploration_licence":
            base.extend(["Exploration work programme", "Financial capability proof"])
        elif licence_type == "artisanal_mining_permit":
            base.extend(["County government endorsement", "Location map"])
        return base

    def _processing_timeline(self, licence_type: str) -> str:
        timelines = {
            "mining_licence": "6-12 months",
            "exploration_licence": "3-6 months",
            "artisanal_mining_permit": "1-3 months",
        }
        return timelines.get(licence_type, "Unknown")

    def _permit_fees(self, licence_type: str) -> dict:
        fees = {
            "mining_licence": {"application_kes": 50000, "annual_kes": 100000},
            "exploration_licence": {"application_kes": 20000, "annual_kes": 50000},
            "artisanal_mining_permit": {"application_kes": 5000, "annual_kes": 10000},
        }
        return fees.get(licence_type, {"application_kes": 0, "annual_kes": 0})
