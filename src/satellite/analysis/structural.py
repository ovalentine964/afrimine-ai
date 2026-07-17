"""
Structural Analysis Module

Detects lineaments (faults, fractures, joints) from satellite imagery
using Canny edge detection and Hough transform.

Lineaments are critical in mineral exploration as faults and fractures
serve as conduits for hydrothermal fluids that deposit minerals.
"""
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

import numpy as np
import cv2
from scipy import ndimage

from ..utils.config import StructuralConfig, OUTPUT_DIR
from ..utils.helpers import normalize_array

logger = logging.getLogger("afrimine.satellite.structural")


@dataclass
class Lineament:
    """Detected lineament (fault/fracture)."""
    x1: int
    y1: int
    x2: int
    y2: int
    length: float
    orientation: float  # degrees, 0-180
    density_score: float = 0.0

    @property
    def midpoint(self) -> Tuple[int, int]:
        return (self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2


@dataclass
class StructuralResult:
    """Results from structural analysis."""
    lineaments: List[Lineament]
    edge_image: np.ndarray
    density_map: np.ndarray
    orientation_histogram: np.ndarray
    orientation_bins: np.ndarray
    statistics: Dict = field(default_factory=dict)


class StructuralAnalyzer:
    """
    Structural analysis of satellite imagery for mineral exploration.

    Methods:
    - Canny edge detection for lineament identification
    - Hough transform for line extraction
    - Lineament density mapping
    - Orientation (rose diagram) analysis
    - Drainage pattern analysis
    """

    def __init__(self, config: StructuralConfig = None):
        self.config = config or StructuralConfig()
        self.output_dir = OUTPUT_DIR / "structural"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def detect_edges(self, image: np.ndarray,
                     preprocess: bool = True) -> np.ndarray:
        """
        Apply Canny edge detection to detect lineaments.

        Args:
            image: 2D array (grayscale or single band)
            preprocess: Apply Gaussian blur and contrast enhancement

        Returns:
            Binary edge image
        """
        if image.ndim == 3:
            # Use PCA first component or mean of bands
            image = np.mean(image, axis=0)

        # Normalize to 8-bit
        img = normalize_array(image)
        img = (img * 255).astype(np.uint8)

        if preprocess:
            # Gaussian blur to reduce noise
            img = cv2.GaussianBlur(img, (5, 5), 1.0)
            # CLAHE for contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img = clahe.apply(img)

        edges = cv2.Canny(
            img,
            self.config.CANNY_LOW,
            self.config.CANNY_HIGH,
            apertureSize=3,
            L2gradient=True,
        )

        logger.info(f"Edge detection: {np.sum(edges > 0)} edge pixels")
        return edges

    def detect_lineaments(self, image: np.ndarray) -> StructuralResult:
        """
        Full lineament detection pipeline: edge detection + Hough transform.

        Args:
            image: Input image (2D or 3D)

        Returns:
            StructuralResult with lineaments and analysis
        """
        edges = self.detect_edges(image)

        # Probabilistic Hough Transform
        lines = cv2.HoughLinesP(
            edges,
            rho=self.config.HOUGH_RHO,
            theta=self.config.HOUGH_THETA,
            threshold=self.config.HOUGH_THRESHOLD,
            minLineLength=self.config.HOUGH_MIN_LINE_LENGTH,
            maxLineGap=self.config.HOUGH_MAX_LINE_GAP,
        )

        lineaments = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                orientation = np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180

                if length >= self.config.MIN_LINEAMENT_LENGTH:
                    lineaments.append(Lineament(
                        x1=x1, y1=y1, x2=x2, y2=y2,
                        length=length,
                        orientation=orientation,
                    ))

        logger.info(f"Detected {len(lineaments)} lineaments")

        # Compute density map
        density_map = self.compute_density_map(lineaments, image.shape[-2:])

        # Orientation histogram
        hist, bins = self.orientation_histogram(lineaments)

        # Statistics
        stats = self._compute_statistics(lineaments)

        return StructuralResult(
            lineaments=lineaments,
            edge_image=edges,
            density_map=density_map,
            orientation_histogram=hist,
            orientation_bins=bins,
            statistics=stats,
        )

    def compute_density_map(self, lineaments: List[Lineament],
                            shape: Tuple[int, int],
                            kernel_size: int = 25) -> np.ndarray:
        """
        Compute lineament density map using kernel density estimation.

        High density zones (intersection of multiple faults) are
        prime targets for mineral exploration.
        """
        # Create binary lineament map
        line_map = np.zeros(shape, dtype=np.float32)
        for lam in lineaments:
            cv2.line(line_map, (lam.x1, lam.y1), (lam.x2, lam.y2), 1.0, 1)

        # Gaussian kernel density
        density = ndimage.uniform_filter(line_map, size=kernel_size)
        density = normalize_array(density)

        logger.info(
            f"Density map: max={density.max():.3f}, "
            f"mean={density.mean():.4f}"
        )
        return density

    def orientation_histogram(self, lineaments: List[Lineament],
                              n_bins: int = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute orientation histogram (rose diagram data).

        Args:
            lineaments: List of detected lineaments
            n_bins: Number of orientation bins

        Returns:
            Tuple of (histogram_counts, bin_edges) in degrees
        """
        n_bins = n_bins or self.config.DIRECTION_BINS
        orientations = [lam.orientation for lam in lineaments]
        lengths = [lam.length for lam in lineaments]

        if not orientations:
            return np.zeros(n_bins), np.linspace(0, 180, n_bins + 1)

        # Weight by lineament length
        hist, bins = np.histogram(
            orientations,
            bins=n_bins,
            range=(0, 180),
            weights=lengths,
        )

        # Normalize
        if hist.max() > 0:
            hist = hist / hist.max()

        return hist, bins

    def drainage_analysis(self, ndwi: np.ndarray,
                          threshold: float = 0.3) -> Dict:
        """
        Analyze drainage patterns from water index.

        Drainage patterns reveal underlying geology:
        - Dendritic: uniform lithology
        - Rectangular: joint-controlled
        - Trellis: alternating resistant/soft layers
        - Radial: volcanic/domal structures

        Args:
            ndwi: Normalized Difference Water Index array
            threshold: Water detection threshold

        Returns:
            Dict with drainage statistics
        """
        # Threshold to get water pixels
        water_mask = ndwi > threshold

        # Skeletonize to get drainage lines
        try:
            from skimage.morphology import skeletonize
            skeleton = skeletonize(water_mask).astype(np.uint8)
        except ImportError:
            logger.warning(
                "scikit-image not available for skeletonize, "
                "using erosion-based approximation"
            )
            # Fallback: thin the water mask with erosion
            kernel = np.ones((3, 3), dtype=np.uint8)
            skeleton = water_mask.astype(np.uint8)
            for _ in range(3):
                eroded = ndimage.binary_erosion(skeleton, structure=kernel).astype(np.uint8)
                if np.sum(eroded) == 0:
                    break
                skeleton = eroded

        # Count junctions (intersections)
        kernel = np.array([[1, 1, 1], [1, 10, 1], [1, 1, 1]], dtype=np.uint8)
        convolved = ndimage.convolve(skeleton, kernel)
        junctions = int(np.sum(convolved >= 13))  # >2 neighbors + center

        # Estimate drainage density
        total_pixels = ndwi.size
        drainage_pixels = int(np.sum(skeleton))
        density = drainage_pixels / total_pixels if total_pixels > 0 else 0

        # Estimate flow directions (gradient-based)
        gy, gx = np.gradient(ndwi.astype(np.float64))
        flow_angle = np.degrees(np.arctan2(gy, gx)) % 360

        # Dominant flow direction in water areas
        if np.sum(water_mask) > 0:
            dominant_flow = np.median(flow_angle[water_mask])
        else:
            dominant_flow = 0

        result = {
            "drainage_density": float(density),
            "total_drainage_pixels": drainage_pixels,
            "junction_count": junctions,
            "dominant_flow_direction": float(dominant_flow),
            "water_area_fraction": float(np.sum(water_mask) / total_pixels),
            "skeleton": skeleton,
        }

        logger.info(
            f"Drainage analysis: density={density:.4f}, "
            f"junctions={junctions}, flow_dir={dominant_flow:.1f}°"
        )
        return result

    def proximity_to_faults(self, points: np.ndarray,
                            lineaments: List[Lineament],
                            max_distance: float = 500) -> np.ndarray:
        """
        Calculate distance from sample points to nearest fault.

        Args:
            points: Nx2 array of (x, y) coordinates
            lineaments: Detected lineaments
            max_distance: Maximum search distance in pixels

        Returns:
            Array of distances to nearest fault
        """
        # Create distance transform from fault lines
        shape = (np.max(points[:, 1]) + 100, np.max(points[:, 0]) + 100)
        fault_map = np.zeros(shape, dtype=np.uint8)

        for lam in lineaments:
            cv2.line(fault_map, (lam.x1, lam.y1), (lam.x2, lam.y2), 255, 2)

        # Distance transform
        dist = ndimage.distance_transform_edt(255 - fault_map)

        # Sample distances at point locations
        distances = np.array([
            dist[int(p[1]), int(p[0])]
            for p in points
        ])

        logger.info(
            f"Fault proximity: min={distances.min():.1f}, "
            f"max={distances.max():.1f}, mean={distances.mean():.1f} px"
        )
        return distances

    def _compute_statistics(self, lineaments: List[Lineament]) -> Dict:
        """Compute summary statistics for detected lineaments."""
        if not lineaments:
            return {
                "count": 0, "total_length": 0, "mean_length": 0,
                "max_length": 0, "dominant_orientation": 0,
            }

        lengths = [l.length for l in lineaments]
        orientations = [l.orientation for l in lineaments]

        # Find dominant orientation (weighted by length)
        hist, bins = self.orientation_histogram(lineaments)
        dominant_idx = np.argmax(hist)
        dominant_orient = (bins[dominant_idx] + bins[dominant_idx + 1]) / 2

        return {
            "count": len(lineaments),
            "total_length": sum(lengths),
            "mean_length": np.mean(lengths),
            "max_length": max(lengths),
            "std_length": np.std(lengths),
            "dominant_orientation": dominant_orient,
            "mean_orientation": np.mean(orientations),
        }
