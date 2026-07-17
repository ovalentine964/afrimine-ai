"""
Band math operations for Sentinel-2 imagery.

Computes spectral indices used in mineral exploration:
- Iron oxide ratio (B4/B2)
- Clay mineral index ((B11-B12)/(B11+B12))
- Silica index (B11/B12)
- Chlorite index (B8A/B11)
- NDVI ((B8-B4)/(B8+B4))
"""
import logging
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

import numpy as np

from ..utils.helpers import safe_divide, normalize_array

logger = logging.getLogger("afrimine.satellite.band_math")

# Sentinel-2 band index mapping (0-based in the data array)
BAND_MAP = {
    "B1": 0, "B2": 1, "B3": 2, "B4": 3, "B5": 4, "B6": 5, "B7": 6,
    "B8": 7, "B8A": 8, "B9": 9, "B11": 10, "B12": 11,
}


@dataclass
class SpectralIndex:
    """Container for a computed spectral index."""
    name: str
    data: np.ndarray
    formula: str
    description: str
    normalized: Optional[np.ndarray] = None

    def normalize(self, low: float = 0.02, high: float = 0.98):
        """Compute percentile-normalized version."""
        self.normalized = normalize_array(self.data, low, high)
        return self


class BandMathEngine:
    """
    Computes spectral indices from multi-band Sentinel-2 data.

    Usage:
        engine = BandMathEngine(band_order=["B2","B3","B4","B8","B8A","B11","B12"])
        indices = engine.compute_all(data_array)
    """

    # Default band order for AfriMine (7 bands)
    DEFAULT_BANDS = ["B2", "B3", "B4", "B8", "B8A", "B11", "B12"]

    def __init__(self, band_order: list = None):
        self.band_order = band_order or self.DEFAULT_BANDS
        self._band_indices = {name: i for i, name in enumerate(self.band_order)}
        logger.info(f"BandMathEngine initialized with bands: {self.band_order}")

    def _get_band(self, data: np.ndarray, band_name: str) -> np.ndarray:
        """Extract a single band from the data array."""
        if band_name not in self._band_indices:
            raise KeyError(
                f"Band '{band_name}' not in data. Available: {list(self._band_indices.keys())}"
            )
        idx = self._band_indices[band_name]
        if data.ndim == 3:
            return data[idx].astype(np.float32)
        elif data.ndim == 2:
            return data.astype(np.float32)
        raise ValueError(f"Unexpected data shape: {data.shape}")

    def iron_oxide_index(self, data: np.ndarray) -> SpectralIndex:
        """
        Iron Oxide Index: B4/B2 (Red/Blue ratio)
        High values indicate ferric iron-bearing minerals (hematite, goethite).
        These are common alteration halos around gold and copper deposits.
        """
        b4 = self._get_band(data, "B4")
        b2 = self._get_band(data, "B2")
        ratio = safe_divide(b4, b2)

        idx = SpectralIndex(
            name="iron_oxide",
            data=ratio,
            formula="B4 / B2",
            description="Ferric iron oxide ratio — high values = hematite/goethite alteration",
        )
        return idx.normalize()

    def clay_mineral_index(self, data: np.ndarray) -> SpectralIndex:
        """
        Clay Mineral Index: (B11 - B12) / (B11 + B12) (SWIR normalized diff)
        Detects Al-OH and Mg-OH bearing clays (kaolinite, illite, montmorillonite).
        Key indicator of hydrothermal alteration in porphyry and epithermal systems.
        """
        b11 = self._get_band(data, "B11")
        b12 = self._get_band(data, "B12")
        nd = safe_divide(b11 - b12, b11 + b12)

        idx = SpectralIndex(
            name="clay_mineral",
            data=nd,
            formula="(B11 - B12) / (B11 + B12)",
            description="Clay mineral absorption — high values = argillic alteration",
        )
        return idx.normalize()

    def silica_index(self, data: np.ndarray) -> SpectralIndex:
        """
        Silica Index: B11/B12 (SWIR ratio)
        High silica content indicates silicification — common in gold-bearing veins.
        """
        b11 = self._get_band(data, "B11")
        b12 = self._get_band(data, "B12")
        ratio = safe_divide(b11, b12)

        idx = SpectralIndex(
            name="silica",
            data=ratio,
            formula="B11 / B12",
            description="Silica content — high values = silicified zones (gold indicator)",
        )
        return idx.normalize()

    def chlorite_index(self, data: np.ndarray) -> SpectralIndex:
        """
        Chlorite Index: B8A/B11
        Detects chlorite/epidote alteration (propylitic alteration).
        Common in the outer zones of porphyry copper systems.
        """
        b8a = self._get_band(data, "B8A")
        b11 = self._get_band(data, "B11")
        ratio = safe_divide(b8a, b11)

        idx = SpectralIndex(
            name="chlorite",
            data=ratio,
            formula="B8A / B11",
            description="Chlorite/epidote alteration — propylitic halos",
        )
        return idx.normalize()

    def ndvi(self, data: np.ndarray) -> SpectralIndex:
        """
        NDVI: (B8 - B4) / (B8 + B4)
        Normalized Difference Vegetation Index.
        Used to detect vegetation stress from mineral deposits (biogeochemical anomaly).
        Also critical for change detection (deforestation from mining).
        """
        b8 = self._get_band(data, "B8")
        b4 = self._get_band(data, "B4")
        nd = safe_divide(b8 - b4, b8 + b4)

        idx = SpectralIndex(
            name="ndvi",
            data=nd,
            formula="(B8 - B4) / (B8 + B4)",
            description="Vegetation health — low values may indicate mineral stress or mining",
        )
        return idx.normalize()

    def ndwi(self, data: np.ndarray) -> SpectralIndex:
        """
        NDWI: (B3 - B8) / (B3 + B8)
        Normalized Difference Water Index — detects surface water.
        """
        b3 = self._get_band(data, "B3")
        b8 = self._get_band(data, "B8")
        nd = safe_divide(b3 - b8, b3 + b8)

        idx = SpectralIndex(
            name="ndwi",
            data=nd,
            formula="(B3 - B8) / (B3 + B8)",
            description="Water body detection",
        )
        return idx.normalize()

    def compute_all(self, data: np.ndarray) -> Dict[str, SpectralIndex]:
        """
        Compute all spectral indices.

        Args:
            data: Multi-band array (bands, height, width)

        Returns:
            Dict mapping index name to SpectralIndex object
        """
        indices = {}
        compute_funcs = [
            ("iron_oxide", self.iron_oxide_index),
            ("clay_mineral", self.clay_mineral_index),
            ("silica", self.silica_index),
            ("chlorite", self.chlorite_index),
            ("ndvi", self.ndvi),
            ("ndwi", self.ndwi),
        ]

        for name, func in compute_funcs:
            try:
                indices[name] = func(data)
                stats = indices[name].data
                logger.info(
                    f"  {name}: min={np.nanmin(stats):.4f}, "
                    f"max={np.nanmax(stats):.4f}, "
                    f"mean={np.nanmean(stats):.4f}"
                )
            except Exception as e:
                logger.warning(f"Failed to compute {name}: {e}")

        logger.info(f"Computed {len(indices)} spectral indices")
        return indices

    def alteration_composite(self, indices: Dict[str, SpectralIndex]) -> np.ndarray:
        """
        Create RGB composite of key alteration indices.
        R = iron oxide, G = clay mineral, B = silica
        """
        r = indices["iron_oxide"].normalized
        g = indices["clay_mineral"].normalized
        b = indices["silica"].normalized

        composite = np.stack([r, g, b], axis=0)
        return composite
