"""
AfriMine AI — Sampling Agent
Plans optimal field sampling routes for mineral exploration.
Considers geology, accessibility, prior findings, and grid coverage.
"""

from __future__ import annotations

import math
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class SamplingAgent:
    """
    Agent responsible for planning field sampling campaigns.
    Generates sampling grids, prioritizes locations, and optimizes routes.
    """

    def __init__(self, gemini_model=None):
        self.name = "Sampling Agent"
        self.role = "Field Sampling Planner"
        self.gemini = gemini_model

    def generate_sampling_grid(
        self,
        lat_min: float, lat_max: float,
        lon_min: float, lon_max: float,
        spacing_m: float = 500.0,
        grid_type: str = "regular",
    ) -> list[dict]:
        """
        Generate a sampling grid over the area of interest.

        Args:
            lat_min, lat_max: Latitude bounds
            lon_min, lon_max: Longitude bounds
            spacing_m: Grid spacing in metres
            grid_type: 'regular', 'random', or 'biased'

        Returns:
            List of {lat, lon, sample_id, priority}
        """
        # Convert metres to approximate degrees
        lat_step = spacing_m / 111_320.0
        lon_step = spacing_m / (111_320.0 * math.cos(math.radians((lat_min + lat_max) / 2)))

        points = []
        sample_id = 1

        if grid_type == "regular":
            lat = lat_min
            while lat <= lat_max:
                lon = lon_min
                while lon <= lon_max:
                    points.append({
                        "lat": round(lat, 6),
                        "lon": round(lon, 6),
                        "sample_id": f"S{sample_id:04d}",
                        "priority": self._calculate_priority(lat, lon, lat_min, lat_max, lon_min, lon_max),
                    })
                    sample_id += 1
                    lon += lon_step
                lat += lat_step

        elif grid_type == "random":
            n_points = int(((lat_max - lat_min) / lat_step) * ((lon_max - lon_min) / lon_step))
            rng = np.random.default_rng(42)
            for i in range(n_points):
                lat = rng.uniform(lat_min, lat_max)
                lon = rng.uniform(lon_min, lon_max)
                points.append({
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "sample_id": f"S{i+1:04d}",
                    "priority": "medium",
                })

        elif grid_type == "biased":
            # Bias toward centre and known geological features
            rng = np.random.default_rng(42)
            center_lat = (lat_min + lat_max) / 2
            center_lon = (lon_min + lon_max) / 2
            n_points = int(((lat_max - lat_min) / lat_step) * ((lon_max - lon_min) / lon_step) * 1.5)
            for i in range(n_points):
                # Gaussian distribution centred on AOI centre
                lat = rng.normal(center_lat, (lat_max - lat_min) / 4)
                lon = rng.normal(center_lon, (lon_max - lon_min) / 4)
                lat = np.clip(lat, lat_min, lat_max)
                lon = np.clip(lon, lon_min, lon_max)
                dist = math.sqrt((lat - center_lat) ** 2 + (lon - center_lon) ** 2)
                priority = "high" if dist < (lat_max - lat_min) / 6 else "medium"
                points.append({
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "sample_id": f"S{i+1:04d}",
                    "priority": priority,
                })

        logger.info(f"Generated {len(points)} sampling points ({grid_type} grid, {spacing_m}m spacing)")
        return points

    def optimize_route(
        self,
        points: list[dict],
        start_lat: float,
        start_lon: float,
        max_daily_samples: int = 20,
    ) -> list[dict]:
        """
        Optimize field route using nearest-neighbour heuristic with priority weighting.
        Returns ordered list of points with day assignments.
        """
        if not points:
            return []

        # Sort by priority weight
        priority_weights = {"high": 3, "medium": 2, "low": 1}
        unvisited = sorted(points, key=lambda p: -priority_weights.get(p.get("priority", "medium"), 2))

        route = []
        current_lat, current_lon = start_lat, start_lon
        day = 1
        samples_today = 0

        while unvisited:
            if samples_today >= max_daily_samples:
                day += 1
                samples_today = 0

            # Find nearest unvisited point
            best_idx = None
            best_dist = float("inf")
            for i, pt in enumerate(unvisited):
                d = math.sqrt(
                    (pt["lat"] - current_lat) ** 2 + (pt["lon"] - current_lon) ** 2
                )
                # Apply priority boost
                p_weight = priority_weights.get(pt.get("priority", "medium"), 2)
                effective_dist = d / p_weight
                if effective_dist < best_dist:
                    best_dist = effective_dist
                    best_idx = i

            next_point = unvisited.pop(best_idx)
            next_point["day"] = day
            next_point["order"] = len(route) + 1
            next_point["distance_from_prev_km"] = round(best_dist * 111.32, 2)
            route.append(next_point)
            current_lat = next_point["lat"]
            current_lon = next_point["lon"]
            samples_today += 1

        logger.info(f"Route optimized: {len(route)} points over {day} days")
        return route

    def assess_terrain_difficulty(self, lat: float, lon: float) -> dict:
        """Estimate terrain difficulty for a sampling point."""
        # Simplified terrain assessment based on Kenya's geography
        # In production, this would query DEM/elevation data
        difficulty = "moderate"
        notes = []

        # Rift Valley region
        if -1.0 < lat < 1.0 and 35.0 < lon < 37.0:
            difficulty = "hard"
            notes.append("Great Rift Valley — steep terrain possible")

        # Coastal region
        if -4.5 < lat < -2.0 and 39.0 < lon < 41.0:
            difficulty = "easy"
            notes.append("Coastal lowlands — flat terrain")

        # Central highlands
        if -1.5 < lat < 0.5 and 36.5 < lon < 37.5:
            difficulty = "moderate"
            notes.append("Central highlands — moderate elevation")

        return {
            "lat": lat,
            "lon": lon,
            "difficulty": difficulty,
            "notes": notes,
            "recommended_vehicle": "4x4" if difficulty == "hard" else "any",
        }

    def generate_report(self, points: list[dict], route: list[dict]) -> str:
        """Generate a human-readable sampling plan report."""
        report_lines = [
            "# AfriMine AI — Sampling Plan Report",
            "",
            f"## Grid Summary",
            f"- Total sample points: {len(points)}",
            f"- High priority: {sum(1 for p in points if p.get('priority') == 'high')}",
            f"- Medium priority: {sum(1 for p in points if p.get('priority') == 'medium')}",
            f"- Low priority: {sum(1 for p in points if p.get('priority') == 'low')}",
            "",
            f"## Route Summary",
            f"- Estimated days: {max(r.get('day', 1) for r in route) if route else 0}",
            f"- Total distance: {sum(r.get('distance_from_prev_km', 0) for r in route):.1f} km",
            "",
            "## Daily Schedule",
        ]

        if route:
            current_day = 0
            for pt in route:
                if pt.get("day", 1) != current_day:
                    current_day = pt["day"]
                    report_lines.append(f"\n### Day {current_day}")
                report_lines.append(
                    f"  {pt['order']}. {pt['sample_id']} — ({pt['lat']}, {pt['lon']}) "
                    f"[{pt.get('priority', 'medium')}] — {pt.get('distance_from_prev_km', 0):.1f}km"
                )

        return "\n".join(report_lines)

    @staticmethod
    def _calculate_priority(lat, lon, lat_min, lat_max, lon_min, lon_max) -> str:
        """Calculate sample priority based on position in AOI."""
        center_lat = (lat_min + lat_max) / 2
        center_lon = (lon_min + lon_max) / 2
        dist = math.sqrt((lat - center_lat) ** 2 + (lon - center_lon) ** 2)
        max_dist = math.sqrt((lat_max - lat_min) ** 2 + (lon_max - lon_min) ** 2) / 2
        if dist < max_dist * 0.3:
            return "high"
        elif dist < max_dist * 0.7:
            return "medium"
        return "low"
