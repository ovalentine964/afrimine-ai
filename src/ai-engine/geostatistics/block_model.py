"""
3D Block Model for AfriMine AI
================================

Generates a 3D block model, populates it with kriged grades,
and outputs visualization-ready data.

Dependencies: numpy, pandas, matplotlib
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BlockDefinition:
    """Block model grid definition."""
    origin: Tuple[float, float, float]  # (x0, y0, z0)
    block_size: Tuple[float, float, float]  # (dx, dy, dz)
    n_blocks: Tuple[int, int, int]  # (nx, ny, nz)
    rotation: float = 0.0  # degrees, rotation around z-axis


@dataclass
class Block:
    """Single block in the model."""
    i: int
    j: int
    k: int
    centroid: np.ndarray
    grade: float = 0.0
    variance: float = 0.0
    tonnage: float = 0.0
    metal_content: float = 0.0
    density: float = 2.7  # t/m³ default for rock
    domain: int = 0
    classification: str = "unclassified"


@dataclass
class BlockModelStats:
    """Summary statistics for a block model."""
    total_blocks: int
    classified_blocks: int
    total_tonnage: float
    total_metal: float
    average_grade: float
    grade_tonnage_curve: Dict[str, List[float]]


# ---------------------------------------------------------------------------
# Block Model
# ---------------------------------------------------------------------------

class BlockModel:
    """
    3D block model generation and management.

    Parameters
    ----------
    definition : BlockDefinition
        Grid definition (origin, block size, number of blocks).
    """

    def __init__(self, definition: BlockDefinition):
        self.definition = definition
        self.origin = np.array(definition.origin, dtype=np.float64)
        self.block_size = np.array(definition.block_size, dtype=np.float64)
        self.nx, self.ny, self.nz = definition.n_blocks

        # Initialize the block array
        self.n_blocks = self.nx * self.ny * self.nz
        self._blocks: Optional[np.ndarray] = None
        self._grades: Optional[np.ndarray] = None
        self._variances: Optional[np.ndarray] = None
        self._domains: Optional[np.ndarray] = None
        self._classifications: Optional[np.ndarray] = None
        self._densities: Optional[np.ndarray] = None
        self._initialized = False

    def initialize(self, default_density: float = 2.7):
        """Allocate block model arrays."""
        shape = (self.nx, self.ny, self.nz)
        self._grades = np.full(shape, np.nan)
        self._variances = np.full(shape, np.nan)
        self._domains = np.zeros(shape, dtype=int)
        self._classifications = np.full(shape, "unclassified", dtype=object)
        self._densities = np.full(shape, default_density)
        self._initialized = True
        logger.info(
            "Block model initialized: %dx%dx%d = %d blocks",
            self.nx, self.ny, self.nz, self.n_blocks,
        )

    # ------------------------------------------------------------------
    # Coordinate ↔ index conversions
    # ------------------------------------------------------------------

    def centroid(self, i: int, j: int, k: int) -> np.ndarray:
        """Get centroid coordinates of block (i, j, k)."""
        return self.origin + np.array([
            (i + 0.5) * self.block_size[0],
            (j + 0.5) * self.block_size[1],
            (k + 0.5) * self.block_size[2],
        ])

    def all_centroids(self) -> np.ndarray:
        """Return centroids of all blocks, shape (nx*ny*nz, 3)."""
        idx = np.array(np.meshgrid(
            np.arange(self.nx),
            np.arange(self.ny),
            np.arange(self.nz),
            indexing="ij",
        )).reshape(3, -1).T
        centroids = self.origin + (idx + 0.5) * self.block_size
        return centroids

    def coord_to_index(self, x: float, y: float, z: float) -> Tuple[int, int, int]:
        """Convert coordinates to block indices."""
        rel = np.array([x, y, z]) - self.origin
        i = int(rel[0] / self.block_size[0])
        j = int(rel[1] / self.block_size[1])
        k = int(rel[2] / self.block_size[2])
        i = max(0, min(i, self.nx - 1))
        j = max(0, min(j, self.ny - 1))
        k = max(0, min(k, self.nz - 1))
        return i, j, k

    def is_valid(self, i: int, j: int, k: int) -> bool:
        return 0 <= i < self.nx and 0 <= j < self.ny and 0 <= k < self.nz

    # ------------------------------------------------------------------
    # Grade population from kriging
    # ------------------------------------------------------------------

    def populate_from_kriging(
        self,
        centroids: np.ndarray,
        grades: np.ndarray,
        variances: Optional[np.ndarray] = None,
    ):
        """
        Populate block model from kriging results.

        Parameters
        ----------
        centroids : np.ndarray, shape (m, 3)
            Block centroids from kriging.
        grades : np.ndarray, shape (m,)
            Kriged grades.
        variances : np.ndarray, optional
            Kriging variances.
        """
        if not self._initialized:
            self.initialize()

        n_populated = 0
        for idx in range(len(centroids)):
            i, j, k = self.coord_to_index(*centroids[idx])
            self._grades[i, j, k] = grades[idx]
            if variances is not None:
                self._variances[i, j, k] = variances[idx]
            n_populated += 1

        logger.info("Populated %d blocks from kriging results", n_populated)

    def populate_from_dataframe(self, df: pd.DataFrame):
        """
        Populate from a DataFrame with columns: x, y, z, grade, [variance, domain].
        """
        if not self._initialized:
            self.initialize()

        for _, row in df.iterrows():
            i, j, k = self.coord_to_index(row["x"], row["y"], row.get("z", 0))
            self._grades[i, j, k] = row["grade"]
            if "variance" in df.columns:
                self._variances[i, j, k] = row["variance"]
            if "domain" in df.columns:
                self._domains[i, j, k] = int(row["domain"])

    # ------------------------------------------------------------------
    # Domain assignment
    # ------------------------------------------------------------------

    def set_domain(self, i: int, j: int, k: int, domain_id: int):
        if self._initialized:
            self._domains[i, j, k] = domain_id

    def set_domain_mask(self, mask: np.ndarray, domain_id: int):
        """Set domain for all blocks where mask is True."""
        if not self._initialized:
            self.initialize()
        self._domains[mask] = domain_id

    # ------------------------------------------------------------------
    # Tonnage and metal content
    # ------------------------------------------------------------------

    def compute_tonnage(
        self,
        density: Optional[float] = None,
        domain_id: Optional[int] = None,
    ) -> np.ndarray:
        """
        Compute tonnage for each block.

        Tonnage = volume × density
        Volume = dx × dy × dz
        """
        if not self._initialized:
            self.initialize()

        volume = np.prod(self.block_size)
        densities = self._densities if density is None else np.full_like(self._densities, density)

        tonnages = volume * densities

        if domain_id is not None:
            tonnages[self._domains != domain_id] = 0.0

        return tonnages

    def compute_metal_content(self, domain_id: Optional[int] = None) -> np.ndarray:
        """Metal content = tonnage × grade."""
        tonnages = self.compute_tonnage(domain_id=domain_id)
        grades = np.nan_to_num(self._grades, nan=0.0)
        return tonnages * grades

    # ------------------------------------------------------------------
    # Grade-tonnage curve
    # ------------------------------------------------------------------

    def grade_tonnage_curve(
        self,
        cutoffs: Optional[np.ndarray] = None,
        n_cutoffs: int = 20,
        domain_id: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Generate a grade-tonnage curve.

        For each cutoff grade, reports:
        - tonnage above cutoff
        - average grade above cutoff
        - metal content above cutoff
        - percentage of total tonnage

        Returns
        -------
        pd.DataFrame
        """
        grades = self._grades[~np.isnan(self._grades)]
        tonnages = self.compute_tonnage(domain_id=domain_id).ravel()
        metal = self.compute_metal_content(domain_id=domain_id).ravel()

        # Only use blocks with valid grades
        valid = ~np.isnan(self._grades.ravel())
        grades = grades if len(grades) > 0 else np.array([0.0])
        tonnages_valid = tonnages[valid] if np.any(valid) else np.array([0.0])
        metal_valid = metal[valid] if np.any(valid) else np.array([0.0])

        if cutoffs is None:
            cutoffs = np.linspace(0, np.percentile(grades, 95) if len(grades) > 0 else 1.0, n_cutoffs)

        rows = []
        total_tonnage = tonnages_valid.sum()
        for co in cutoffs:
            mask = grades >= co
            t = tonnages_valid[mask].sum()
            m = metal_valid[mask].sum()
            avg_g = m / t if t > 0 else 0.0
            rows.append({
                "cutoff_grade": co,
                "tonnage": t,
                "average_grade": avg_g,
                "metal_content": m,
                "pct_tonnage": t / total_tonnage * 100 if total_tonnage > 0 else 0,
            })

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def summary(self) -> BlockModelStats:
        """Compute summary statistics."""
        valid_grades = self._grades[~np.isnan(self._grades)]
        tonnages = self.compute_tonnage().ravel()
        metal = self.compute_metal_content().ravel()
        valid = ~np.isnan(self._grades.ravel())

        gt_curve = self.grade_tonnage_curve()

        return BlockModelStats(
            total_blocks=self.n_blocks,
            classified_blocks=int(np.sum(valid)),
            total_tonnage=float(tonnages[valid].sum()),
            total_metal=float(metal[valid].sum()),
            average_grade=float(np.nanmean(valid_grades)) if len(valid_grades) > 0 else 0.0,
            grade_tonnage_curve=gt_curve.to_dict(orient="list"),
        )

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def set_classification(self, i: int, j: int, k: int, classification: str):
        """Set resource classification for a block."""
        if self._initialized:
            self._classifications[i, j, k] = classification

    def set_classification_array(self, classifications: np.ndarray):
        """Set classifications from array, same shape as block model."""
        if not self._initialized:
            self.initialize()
        self._classifications = classifications

    # ------------------------------------------------------------------
    # Export / Visualization
    # ------------------------------------------------------------------

    def get_block(self, i: int, j: int, k: int) -> Optional[Block]:
        """Return a Block dataclass instance for position (i, j, k), or None if empty."""
        if not self._initialized:
            return None
        if not self.is_valid(i, j, k):
            return None
        g = self._grades[i, j, k]
        if np.isnan(g):
            return None
        return Block(
            i=i, j=j, k=k,
            centroid=self.centroid(i, j, k),
            grade=float(g),
            variance=float(self._variances[i, j, k]) if not np.isnan(self._variances[i, j, k]) else 0.0,
            density=float(self._densities[i, j, k]),
            domain=int(self._domains[i, j, k]),
            classification=str(self._classifications[i, j, k]),
        )

    def to_dataframe(self) -> pd.DataFrame:
        """Export block model to a flat DataFrame."""
        if not self._initialized:
            self.initialize()

        records = []
        for i in range(self.nx):
            for j in range(self.ny):
                for k in range(self.nz):
                    block = self.get_block(i, j, k)
                    if block is None:
                        continue  # skip empty blocks
                    records.append({
                        "x": block.centroid[0],
                        "y": block.centroid[1],
                        "z": block.centroid[2],
                        "grade": block.grade,
                        "variance": block.variance,
                        "domain": block.domain,
                        "classification": block.classification,
                        "density": block.density,
                        "block_i": block.i,
                        "block_j": block.j,
                        "block_k": block.k,
                    })

        return pd.DataFrame(records)

    def to_csv(self, path: str):
        """Export to CSV."""
        df = self.to_dataframe()
        df.to_csv(path, index=False)
        logger.info("Exported block model to %s (%d blocks)", path, len(df))

    def to_json(self, path: str):
        """Export block model definition + data to JSON."""
        data = {
            "definition": {
                "origin": list(self.origin),
                "block_size": list(self.block_size),
                "n_blocks": [self.nx, self.ny, self.nz],
            },
            "blocks": [],
        }

        if self._initialized:
            for i in range(self.nx):
                for j in range(self.ny):
                    for k in range(self.nz):
                        block = self.get_block(i, j, k)
                        if block is None:
                            continue
                        data["blocks"].append({
                            "i": block.i, "j": block.j, "k": block.k,
                            "centroid": block.centroid.tolist(),
                            "grade": block.grade,
                            "variance": block.variance if block.variance else None,
                            "domain": block.domain,
                            "classification": block.classification,
                        })

        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info("Exported block model JSON to %s", path)

    def to_vtk(self, path: str):
        """
        Export block model to VTK format for 3D visualization
        (ParaView, PyVista, etc.).
        """
        try:
            import pyvista as pv
        except ImportError:
            logger.warning("pyvista not installed; falling back to OBJ export")
            self._to_obj(path)
            return

        if not self._initialized:
            self.initialize()

        # Create a uniform grid
        grid = pv.UniformGrid()
        grid.dimensions = np.array([self.nx + 1, self.ny + 1, self.nz + 1])
        grid.origin = tuple(self.origin)
        grid.spacing = tuple(self.block_size)

        # Add grade as cell data
        grades_flat = self._grades.ravel(order="F")
        grid.cell_data["grade"] = np.nan_to_num(grades_flat, nan=0.0)

        if self._variances is not None:
            var_flat = self._variances.ravel(order="F")
            grid.cell_data["variance"] = np.nan_to_num(var_flat, nan=0.0)

        grid.save(path)
        logger.info("Exported VTK to %s", path)

    def _to_obj(self, path: str):
        """Fallback: export visible blocks as OBJ mesh."""
        if not self._initialized:
            return

        verts = []
        faces = []
        idx = 0

        for i in range(self.nx):
            for j in range(self.ny):
                for k in range(self.nz):
                    if np.isnan(self._grades[i, j, k]):
                        continue
                    c = self.centroid(i, j, k)
                    dx, dy, dz = self.block_size / 2
                    # 8 corners
                    corners = [
                        c + np.array([-dx, -dy, -dz]),
                        c + np.array([dx, -dy, -dz]),
                        c + np.array([dx, dy, -dz]),
                        c + np.array([-dx, dy, -dz]),
                        c + np.array([-dx, -dy, dz]),
                        c + np.array([dx, -dy, dz]),
                        c + np.array([dx, dy, dz]),
                        c + np.array([-dx, dy, dz]),
                    ]
                    base = len(verts) + 1  # OBJ is 1-indexed
                    verts.extend(corners)
                    # 6 faces (quads)
                    faces.extend([
                        [base, base+1, base+2, base+3],
                        [base+4, base+5, base+6, base+7],
                        [base, base+1, base+5, base+4],
                        [base+2, base+3, base+7, base+6],
                        [base, base+3, base+7, base+4],
                        [base+1, base+2, base+6, base+5],
                    ])

        with open(path, "w") as f:
            for v in verts:
                f.write(f"v {v[0]} {v[1]} {v[2]}\n")
            for face in faces:
                f.write(f"f {' '.join(map(str, face))}\n")
        logger.info("Exported OBJ to %s", path)

    # ------------------------------------------------------------------
    # Visualization (matplotlib)
    # ------------------------------------------------------------------

    def plot_slice(
        self,
        k: int = 0,
        save_path: Optional[str] = None,
        show: bool = False,
    ):
        """Plot a horizontal slice (z-level) of the block model."""
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors

        if not self._initialized:
            self.initialize()

        slice_data = self._grades[:, :, k]
        fig, ax = plt.subplots(figsize=(10, 8))

        im = ax.imshow(
            slice_data.T,
            origin="lower",
            extent=[
                self.origin[0], self.origin[0] + self.nx * self.block_size[0],
                self.origin[1], self.origin[1] + self.ny * self.block_size[1],
            ],
            cmap="YlOrRd",
            aspect="equal",
        )
        plt.colorbar(im, ax=ax, label="Grade")
        ax.set_xlabel("Easting (m)")
        ax.set_ylabel("Northing (m)")
        z_val = self.origin[2] + (k + 0.5) * self.block_size[2]
        ax.set_title(f"Block Model Slice at Z = {z_val:.1f}m")

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
        if show:
            plt.show()
        return fig

    def plot_grade_distribution(
        self,
        save_path: Optional[str] = None,
        show: bool = False,
    ):
        """Plot grade histogram of populated blocks."""
        import matplotlib.pyplot as plt

        grades = self._grades[~np.isnan(self._grades)]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(grades, bins=50, color="steelblue", edgecolor="white", alpha=0.8)
        ax.set_xlabel("Grade")
        ax.set_ylabel("Frequency")
        ax.set_title(f"Block Model Grade Distribution (n={len(grades)})")
        ax.axvline(np.mean(grades), color="red", ls="--", label=f"Mean={np.mean(grades):.3f}")
        ax.legend()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
        if show:
            plt.show()
        return fig
