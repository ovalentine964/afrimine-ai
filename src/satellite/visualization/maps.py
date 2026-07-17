"""
Map Visualization Module

Generates publication-quality maps for:
- Alteration heatmaps
- Lineament overlay maps
- Change detection maps
- RGB composites
- Rose diagrams
"""
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import FancyArrowPatch
from mpl_toolkits.axes_grid1 import make_axes_locatable

from ..utils.config import OUTPUT_DIR, ALTERATION_COLORMAPS
from ..utils.helpers import normalize_array

logger = logging.getLogger("afrimine.satellite.visualization")


class MapGenerator:
    """
    Generates maps and figures for satellite analysis results.

    Outputs:
    - Alteration heatmaps (per index)
    - RGB alteration composite
    - Lineament overlay on imagery
    - Rose diagram (orientation)
    - Change detection maps
    - Multi-panel comparison figures
    """

    def __init__(self, output_dir: Path = None, dpi: int = 150):
        self.output_dir = output_dir or (OUTPUT_DIR / "maps")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dpi = dpi

        # Style
        plt.rcParams.update({
            "figure.facecolor": "white",
            "axes.facecolor": "#f8f8f8",
            "axes.grid": True,
            "grid.alpha": 0.3,
            "font.size": 10,
        })

    def plot_alteration_heatmap(self, data: np.ndarray,
                                title: str = "Alteration Index",
                                cmap: str = "YlOrRd",
                                filename: str = None,
                                vmin: float = None,
                                vmax: float = None,
                                overlay_points: np.ndarray = None) -> str:
        """
        Plot a single alteration index as a heatmap.

        Args:
            data: 2D array of index values
            title: Map title
            cmap: Matplotlib colormap name
            filename: Output filename
            vmin, vmax: Color scale limits
            overlay_points: Nx2 array of (x, y) points to overlay

        Returns:
            Path to saved figure
        """
        fig, ax = plt.subplots(figsize=(12, 10))

        im = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="bilinear")

        # Colorbar
        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="3%", pad=0.1)
        plt.colorbar(im, cax=cax, label="Index Value")

        if overlay_points is not None and len(overlay_points) > 0:
            ax.scatter(overlay_points[:, 0], overlay_points[:, 1],
                       c="cyan", s=20, edgecolors="black", linewidths=0.5,
                       label="Samples", zorder=5)
            ax.legend(loc="upper right")

        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_xlabel("Pixel Column")
        ax.set_ylabel("Pixel Row")

        filename = filename or f"{title.lower().replace(' ', '_')}.png"
        path = self.output_dir / filename
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)

        logger.info(f"Saved heatmap: {path}")
        return str(path)

    def plot_alteration_composite(self, composite: np.ndarray,
                                  title: str = "Alteration Composite (R=Fe, G=Clay, B=SiO₂)",
                                  filename: str = "alteration_composite.png") -> str:
        """
        Plot RGB composite of alteration indices.

        Args:
            composite: (3, H, W) array with R=iron, G=clay, B=silica
            title: Figure title
            filename: Output filename
        """
        fig, ax = plt.subplots(figsize=(12, 10))

        # Transpose to (H, W, 3) for matplotlib
        rgb = np.transpose(composite, (1, 2, 0))
        rgb = np.clip(rgb, 0, 1)

        ax.imshow(rgb)
        ax.set_title(title, fontsize=14, fontweight="bold")

        # Legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="red", label="Iron Oxide (Gossan)"),
            Patch(facecolor="green", label="Clay Minerals"),
            Patch(facecolor="blue", label="Silica"),
        ]
        ax.legend(handles=legend_elements, loc="upper right", fontsize=9)

        path = self.output_dir / filename
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)

        logger.info(f"Saved composite: {path}")
        return str(path)

    def plot_lineaments(self, image: np.ndarray, lineaments: list,
                        title: str = "Structural Lineaments",
                        filename: str = "lineaments.png") -> str:
        """
        Plot detected lineaments overlaid on imagery.
        """
        fig, ax = plt.subplots(figsize=(12, 10))

        # Background image
        if image.ndim == 3:
            bg = normalize_array(np.mean(image, axis=0))
        else:
            bg = normalize_array(image)
        ax.imshow(bg, cmap="gray", interpolation="bilinear")

        # Draw lineaments
        for lam in lineaments:
            color_val = lam.orientation / 180.0
            color = plt.cm.hsv(color_val)
            ax.plot(
                [lam.x1, lam.x2], [lam.y1, lam.y2],
                color=color, linewidth=1.5, alpha=0.8
            )

        ax.set_title(f"{title} ({len(lineaments)} detected)", fontsize=14, fontweight="bold")
        ax.set_xlabel("Pixel Column")
        ax.set_ylabel("Pixel Row")

        path = self.output_dir / filename
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)

        logger.info(f"Saved lineament map: {path}")
        return str(path)

    def plot_rose_diagram(self, histogram: np.ndarray, bins: np.ndarray,
                          title: str = "Lineament Orientation (Rose Diagram)",
                          filename: str = "rose_diagram.png") -> str:
        """
        Plot rose diagram (polar histogram) of lineament orientations.
        """
        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"projection": "polar"})

        # Convert to radians, use bin centers
        bin_centers = (bins[:-1] + bins[1:]) / 2
        theta = np.radians(bin_centers)

        # Width of each bar
        width = np.radians(bins[1] - bins[0])

        # Plot (mirror for 0-360 representation)
        bars = ax.bar(theta, histogram, width=width, bottom=0,
                      alpha=0.7, color="steelblue", edgecolor="navy", linewidth=0.5)
        ax.bar(theta + np.pi, histogram, width=width, bottom=0,
               alpha=0.7, color="steelblue", edgecolor="navy", linewidth=0.5)

        ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)

        path = self.output_dir / filename
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)

        logger.info(f"Saved rose diagram: {path}")
        return str(path)

    def plot_change_detection(self, change_magnitude: np.ndarray,
                              change_mask: np.ndarray,
                              ndvi_change: np.ndarray = None,
                              title: str = "Change Detection",
                              filename: str = "change_detection.png") -> str:
        """
        Multi-panel change detection figure.
        """
        n_panels = 3 if ndvi_change is not None else 2
        fig, axes = plt.subplots(1, n_panels, figsize=(6 * n_panels, 6))

        # Panel 1: Change magnitude
        im1 = axes[0].imshow(change_magnitude, cmap="hot", interpolation="bilinear")
        axes[0].set_title("Change Magnitude")
        plt.colorbar(im1, ax=axes[0], fraction=0.046)

        # Panel 2: Binary change mask
        axes[1].imshow(change_mask, cmap="Reds", interpolation="nearest")
        axes[1].set_title(f"Change Mask ({100*np.mean(change_mask):.1f}% changed)")

        # Panel 3: NDVI change
        if ndvi_change is not None:
            vmin, vmax = -0.5, 0.5
            im3 = axes[2].imshow(ndvi_change, cmap="RdYlGn",
                                 vmin=vmin, vmax=vmax, interpolation="bilinear")
            axes[2].set_title("NDVI Change (green=gain, red=loss)")
            plt.colorbar(im3, ax=axes[2], fraction=0.046)

        for ax in axes:
            ax.set_xlabel("Pixel Column")
            ax.set_ylabel("Pixel Row")

        fig.suptitle(title, fontsize=14, fontweight="bold")
        fig.tight_layout()

        path = self.output_dir / filename
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)

        logger.info(f"Saved change detection: {path}")
        return str(path)

    def plot_density_map(self, density: np.ndarray,
                         title: str = "Lineament Density",
                         filename: str = "lineament_density.png") -> str:
        """Plot lineament density map."""
        return self.plot_alteration_heatmap(
            density, title=title, cmap="inferno",
            filename=filename,
        )

    def plot_rgb_composite(self, bands: np.ndarray,
                           band_indices: Tuple[int, int, int] = (2, 1, 0),
                           title: str = "True Color Composite",
                           filename: str = "rgb_composite.png") -> str:
        """
        Plot RGB composite from multi-band data.

        Args:
            bands: (n_bands, H, W) array
            band_indices: (R, G, B) band indices
            title: Figure title
            filename: Output filename
        """
        rgb = np.stack([
            normalize_array(bands[band_indices[0]]),
            normalize_array(bands[band_indices[1]]),
            normalize_array(bands[band_indices[2]]),
        ], axis=-1)

        fig, ax = plt.subplots(figsize=(12, 10))
        ax.imshow(rgb)
        ax.set_title(title, fontsize=14, fontweight="bold")

        path = self.output_dir / filename
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)

        logger.info(f"Saved RGB composite: {path}")
        return str(path)

    def create_dashboard(self, indices: Dict[str, np.ndarray],
                         classification: np.ndarray,
                         intensity: np.ndarray,
                         lineaments: list = None,
                         region_name: str = "Region",
                         filename: str = "dashboard.png") -> str:
        """
        Create multi-panel dashboard with all key results.
        """
        n_indices = min(len(indices), 6)
        n_cols = 3
        n_rows = 2 + (1 if lineaments else 0)  # indices + classification + intensity

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 5 * n_rows))
        axes = axes.flatten()

        # Plot individual indices
        for i, (name, data) in enumerate(indices.items()):
            if i >= n_cols * 2:
                break
            cmap = ALTERATION_COLORMAPS.get(name, "viridis")
            im = axes[i].imshow(data, cmap=cmap, interpolation="bilinear")
            axes[i].set_title(name.replace("_", " ").title(), fontsize=11)
            plt.colorbar(im, ax=axes[i], fraction=0.046)

        # Classification
        zone_colors = mcolors.ListedColormap([
            "#cccccc", "#ff0000", "#ff8c00", "#ffff00", "#00aa00", "#0000ff"
        ])
        im_class = axes[n_indices].imshow(classification, cmap=zone_colors,
                                          vmin=0, vmax=5, interpolation="nearest")
        axes[n_indices].set_title("Alteration Zones", fontsize=11)

        # Intensity
        im_int = axes[n_indices + 1].imshow(intensity, cmap="hot",
                                             interpolation="bilinear")
        axes[n_indices + 1].set_title("Alteration Intensity", fontsize=11)
        plt.colorbar(im_int, ax=axes[n_indices + 1], fraction=0.046)

        # Remove empty axes
        for i in range(n_indices + 2, len(axes)):
            axes[i].set_visible(False)

        fig.suptitle(f"AfriMine Analysis Dashboard — {region_name}",
                     fontsize=16, fontweight="bold")
        fig.tight_layout()

        path = self.output_dir / filename
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)

        logger.info(f"Saved dashboard: {path}")
        return str(path)
