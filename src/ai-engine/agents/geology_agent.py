"""
AfriMine AI — Geology Agent
Interprets geological context, correlates mineral findings with regional geology.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# Kenya geological provinces and their mineral associations
KENYA_GEOLOGY = {
    "mozambique_belt": {
        "description": "Neoproterozoic orogenic belt, dominant in SE Kenya",
        "counties": ["Taita Taveta", "Kwale", "Kilifi", "Mombasa", "Machakos", "Kitui"],
        "minerals": ["ruby", "sapphire", "garnet", "tourmaline", "graphite", "titanium", "vermiculite"],
        "rock_types": ["gneiss", "schist", "quartzite", "marble", "granulite"],
        "formation_age": "600-850 Ma",
    },
    "east_african_rift": {
        "description": "Cenozoic rift system with volcanic and sedimentary sequences",
        "counties": ["Nakuru", "Baringo", "Kerio Valley", "Turkana", "Magadi"],
        "minerals": ["fluorite", "soda_ash", "diatomite", "limestone", "pumice"],
        "rock_types": ["basalt", "trachyte", "phonolite", "tuff", "lake sediments"],
        "formation_age": "0-25 Ma",
    },
    "nyanzian_craton": {
        "description": "Archaean granite-greenstone terrain in western Kenya",
        "counties": ["Kisumu", "Homa Bay", "Migori", "Kakamega", "Siaya", "Vihiga"],
        "minerals": ["gold", "pyrite", "copper"],
        "rock_types": ["greenstone", "banded_iron_formation", "granite", "schist"],
        "formation_age": "2700-3000 Ma",
    },
    "coastal_sedimentary": {
        "description": "Mesozoic-Cenozoic coastal basin with heavy mineral sands",
        "counties": ["Kwale", "Kilifi", "Lamu", "Tana River", "Mombasa"],
        "minerals": ["titanium", "niobium", "thorium", "zircon"],
        "rock_types": ["limestone", "sandstone", "shale", "alluvium", "beach sands"],
        "formation_age": "65-250 Ma",
    },
    "turkana_volcanic": {
        "description": "Volcanic province in NW Kenya",
        "counties": ["Turkana", "Marsabit"],
        "minerals": ["fluorite", "pumice", "obsidian", "basalt"],
        "rock_types": ["basalt", "rhyolite", "ignimbrite"],
        "formation_age": "0-35 Ma",
    },
}


class GeologyAgent:
    """
    Agent that provides geological context and interpretation for mineral findings.
    Correlates mineral samples with regional geology, tectonic settings, and formation models.
    """

    def __init__(self, gemini_model=None):
        self.name = "Geology Agent"
        self.role = "Geological Interpreter"
        self.gemini = gemini_model
        self.geology_db = KENYA_GEOLOGY

    def identify_geological_province(self, lat: float, lon: float, county: Optional[str] = None) -> list[dict]:
        """
        Identify which geological province(s) a location falls within.
        Returns list of matching provinces with confidence scores.
        """
        matches = []

        for prov_name, prov in self.geology_db.items():
            score = 0.0

            # County match (strong signal)
            if county and county in prov["counties"]:
                score += 0.6

            # Geographic approximation
            if self._point_in_province(lat, lon, prov_name):
                score += 0.4

            if score > 0:
                matches.append({
                    "province": prov_name,
                    "description": prov["description"],
                    "confidence": min(score, 1.0),
                    "expected_minerals": prov["minerals"],
                    "rock_types": prov["rock_types"],
                    "formation_age": prov["formation_age"],
                })

        matches.sort(key=lambda m: -m["confidence"])
        return matches

    def interpret_mineral_assemblage(self, minerals: list[str], location: dict) -> dict:
        """
        Interpret a set of co-occurring minerals in geological context.
        """
        provinces = self.identify_geological_province(
            location.get("lat", 0), location.get("lon", 0), location.get("county")
        )

        interpretations = []
        for mineral in minerals:
            interps = self._interpret_single_mineral(mineral, provinces)
            interpretations.append(interps)

        # Check for mineral associations
        associations = self._check_associations(minerals)

        return {
            "minerals": minerals,
            "location": location,
            "geological_provinces": provinces[:3],
            "mineral_interpretations": interpretations,
            "associations": associations,
            "geological_model": self._build_geological_model(minerals, provinces),
        }

    def estimate_depth_and_extent(self, mineral: str, province: Optional[str] = None) -> dict:
        """
        Estimate likely depth and lateral extent of mineralization.
        Based on geological knowledge base.
        """
        depth_models = {
            "gold": {"shallow": (0, 30), "moderate": (30, 100), "deep": (100, 500), "typical": "shallow_placer_or_vein"},
            "copper": {"shallow": (0, 50), "moderate": (50, 200), "deep": (200, 1000), "typical": "disseminated"},
            "titanium": {"shallow": (0, 10), "moderate": (10, 30), "deep": (30, 60), "typical": "heavy_mineral_sand"},
            "ruby": {"shallow": (0, 20), "moderate": (20, 80), "deep": (80, 200), "typical": "alluvial_or_in_situ"},
            "graphite": {"shallow": (0, 15), "moderate": (15, 50), "deep": (50, 150), "typical": "schist_hosted"},
            "fluorite": {"shallow": (0, 40), "moderate": (40, 150), "deep": (150, 400), "typical": "vein_or_replacement"},
        }

        model = depth_models.get(mineral, {"shallow": (0, 30), "moderate": (30, 100), "deep": (100, 300), "typical": "unknown"})

        return {
            "mineral": mineral,
            "depth_range_m": model["shallow"],
            "likely_depth": model["typical"],
            "lateral_extent_m": self._estimate_extent(mineral),
            "extraction_method": self._suggest_extraction(mineral, model["typical"]),
        }

    def generate_geological_report(self, analysis_results: list[dict], location: dict) -> str:
        """Generate a geological interpretation report."""
        provinces = self.identify_geological_province(
            location.get("lat", 0), location.get("lon", 0), location.get("county")
        )

        minerals_found = [r.get("classification", {}).get("mineral", "unknown") for r in analysis_results if "error" not in r]
        unique_minerals = list(set(minerals_found))

        report = [
            "# AfriMine AI — Geological Interpretation Report",
            "",
            f"## Location: {location.get('county', 'Unknown')} County, Kenya",
            f"Coordinates: ({location.get('lat', '?')}, {location.get('lon', '?')})",
            "",
            "## Regional Geology",
        ]

        if provinces:
            prov = provinces[0]
            report.extend([
                f"**Primary Province:** {prov['province']}",
                f"- {prov['description']}",
                f"- Formation Age: {prov['formation_age']}",
                f"- Rock Types: {', '.join(prov['rock_types'])}",
                f"- Expected Minerals: {', '.join(prov['expected_minerals'])}",
                "",
            ])

        report.append("## Mineral Findings")
        for mineral in unique_minerals:
            count = minerals_found.count(mineral)
            depth_info = self.estimate_depth_and_extent(mineral)
            report.append(f"- **{mineral}**: {count} sample(s), "
                          f"likely depth: {depth_info['depth_range_m'][0]}-{depth_info['depth_range_m'][1]}m, "
                          f"type: {depth_info['likely_depth']}")

        associations = self._check_associations(unique_minerals)
        if associations:
            report.append("\n## Mineral Associations")
            for assoc in associations:
                report.append(f"- {assoc['description']} — **{assoc['significance']}**")

        return "\n".join(report)

    def _interpret_single_mineral(self, mineral: str, provinces: list[dict]) -> dict:
        """Interpret a single mineral in geological context."""
        for prov in provinces:
            if mineral in prov.get("expected_minerals", []):
                return {
                    "mineral": mineral,
                    "expected_in_province": True,
                    "province": prov["province"],
                    "interpretation": f"{mineral} is consistent with {prov['description']}",
                    "host_rocks": prov.get("rock_types", []),
                }

        return {
            "mineral": mineral,
            "expected_in_province": False,
            "interpretation": f"{mineral} presence may indicate a unique geological setting",
        }

    def _check_associations(self, minerals: list[str]) -> list[dict]:
        """Check for known mineral associations with exploration significance."""
        associations = []
        mineral_set = set(minerals)

        if "gold" in mineral_set and "pyrite" in mineral_set:
            associations.append({
                "minerals": ["gold", "pyrite"],
                "description": "Gold-pyrite association (sulfide-hosted gold)",
                "significance": "High — indicates hydrothermal gold mineralization",
            })

        if "gold" in mineral_set and "quartz" in mineral_set:
            associations.append({
                "minerals": ["gold", "quartz"],
                "description": "Gold in quartz veins",
                "significance": "High — primary gold ore type",
            })

        if "ruby" in mineral_set and "garnet" in mineral_set:
            associations.append({
                "minerals": ["ruby", "garnet"],
                "description": "Ruby-garnet assemblage in metamorphic rocks",
                "significance": "Medium — indicates high-grade metamorphism in Mozambique Belt",
            })

        if "titanium" in mineral_set and "thorium" in mineral_set:
            associations.append({
                "minerals": ["titanium", "thorium"],
                "description": "Titanium-thorium heavy mineral sands",
                "significance": "Medium — coastal placer deposit potential",
            })

        if "copper" in mineral_set and "pyrite" in mineral_set:
            associations.append({
                "minerals": ["copper", "pyrite"],
                "description": "Copper-pyrite sulfide association",
                "significance": "Medium — VMS or porphyry copper potential",
            })

        return associations

    def _build_geological_model(self, minerals: list[str], provinces: list[dict]) -> dict:
        """Build a conceptual geological model."""
        if not provinces:
            return {"type": "unknown", "description": "Insufficient data for geological model"}

        primary = provinces[0]
        return {
            "type": primary["province"],
            "description": primary["description"],
            "mineralization_style": self._infer_mineralization_style(minerals, primary["province"]),
            "exploration_vectors": self._suggest_exploration_vectors(minerals, primary),
        }

    def _infer_mineralization_style(self, minerals: list[str], province: str) -> str:
        styles = {
            "nyanzian_craton": "Archaean lode gold in greenstone belts",
            "mozambique_belt": "Metamorphic gemstone deposits in granulites and gneisses",
            "coastal_sedimentary": "Placer/hard-rock heavy mineral deposits",
            "east_african_rift": "Volcanic-sedimentary industrial mineral deposits",
        }
        return styles.get(province, "Mixed mineralization")

    def _suggest_exploration_vectors(self, minerals: list[str], province: dict) -> list[str]:
        vectors = []
        if "gold" in minerals:
            vectors.extend(["Follow quartz vein structures", "Sample stream sediments downstream", "Map alteration zones (silicification, sericitization)"])
        if any(m in minerals for m in ["ruby", "sapphire", "garnet"]):
            vectors.extend(["Sample alluvial gravels in river beds", "Map marble/calc-silicate horizons"])
        if "titanium" in minerals:
            vectors.extend(["Survey beach and dune sand deposits", "Check ilmenite/rutile/zircon ratios"])
        return vectors

    def _estimate_extent(self, mineral: str) -> tuple[int, int]:
        extents = {
            "gold": (100, 5000), "copper": (200, 10000), "titanium": (500, 50000),
            "ruby": (50, 2000), "graphite": (200, 5000), "fluorite": (100, 3000),
        }
        return extents.get(mineral, (100, 2000))

    def _suggest_extraction(self, mineral: str, depth_type: str) -> str:
        if depth_type in ("heavy_mineral_sand", "alluvial_or_in_situ"):
            return "Open pit / alluvial mining"
        elif depth_type in ("shallow_placer_or_vein",):
            return "Shaft or adit mining"
        return "Underground or open pit depending on geometry"

    def _point_in_province(self, lat: float, lon: float, province: str) -> bool:
        """Approximate bounding box check for geological provinces."""
        bounds = {
            "mozambique_belt": (-5.0, -1.0, 37.0, 41.0),
            "east_african_rift": (-2.0, 3.0, 35.0, 37.5),
            "nyanzian_craton": (-1.5, 1.0, 33.5, 35.5),
            "coastal_sedimentary": (-5.0, -1.0, 39.0, 42.0),
            "turkana_volcanic": (2.0, 5.0, 35.0, 37.0),
        }
        if province not in bounds:
            return False
        lat_min, lat_max, lon_min, lon_max = bounds[province]
        return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max
