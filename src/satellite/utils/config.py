"""
AfriMine Satellite Pipeline Configuration
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Tuple, Optional

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "cache"
OUTPUT_DIR = PROJECT_ROOT / "output"
DATA_DIR = PROJECT_ROOT / "data"

for d in [CACHE_DIR, OUTPUT_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@dataclass
class KenyaBounds:
    """Default bounding boxes for Kenyan mining regions."""
    # Turkana County - major mining area
    TURKANA: Tuple[float, float, float, float] = (34.0, 2.5, 36.0, 5.0)
    # Kwale County - titanium mining
    KWALE: Tuple[float, float, float, float] = (39.3, -4.2, 39.8, -3.8)
    # Migori County - gold mining
    MIGORI: Tuple[float, float, float, float] = (34.0, -1.3, 34.6, -0.8)
    # Taita Taveta - gemstones
    TAITA: Tuple[float, float, float, float] = (37.5, -3.8, 38.2, -3.0)
    # Homa Bay - rare earth
    HOMA_BAY: Tuple[float, float, float, float] = (34.0, -0.8, 34.8, -0.2)
    # Entire Kenya
    KENYA: Tuple[float, float, float, float] = (33.9, -4.7, 41.9, 5.0)


@dataclass
class SentinelConfig:
    """Sentinel-2 acquisition parameters."""
    COLLECTION: str = "COPERNICUS/S2_SR_HARMONIZED"
    MAX_CLOUD_COVER: float = 10.0
    BANDS: list = field(default_factory=lambda: [
        "B2", "B3", "B4", "B8", "B8A", "B11", "B12"
    ])
    # All bands for full analysis
    ALL_BANDS: list = field(default_factory=lambda: [
        "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8",
        "B8A", "B9", "B11", "B12"
    ])
    SCALE: int = 10  # meters per pixel
    CRS: str = "EPSG:4326"


@dataclass
class AlterationConfig:
    """Alteration index parameters."""
    # Iron oxide: B4/B2 (red/blue ratio)
    IRON_OXIDE_BANDS: Tuple[str, str] = ("B4", "B2")
    # Clay minerals: (B11-B12)/(B11+B12) (SWIR ratio)
    CLAY_BANDS: Tuple[str, str, str, str] = ("B11", "B12", "B11", "B12")
    # Silica: B11/B12
    SILICA_BANDS: Tuple[str, str] = ("B11", "B12")
    # Chlorite: B8A/B11
    CHLORITE_BANDS: Tuple[str, str] = ("B8A", "B11")
    # NDVI: (B8-B4)/(B8+B4)
    NDVI_BANDS: Tuple[str, str, str, str] = ("B8", "B4", "B8", "B4")


@dataclass
class StructuralConfig:
    """Structural analysis parameters."""
    CANNY_LOW: int = 50
    CANNY_HIGH: int = 150
    HOUGH_RHO: int = 1
    HOUGH_THETA: float = 3.14159 / 180  # 1 degree
    HOUGH_THRESHOLD: int = 80
    HOUGH_MIN_LINE_LENGTH: int = 50
    HOUGH_MAX_LINE_GAP: int = 10
    MIN_LINEAMENT_LENGTH: int = 100  # pixels
    DIRECTION_BINS: int = 36  # 10-degree bins


@dataclass
class PostGISConfig:
    """PostGIS database connection."""
    HOST: str = os.getenv("POSTGIS_HOST", "localhost")
    PORT: int = int(os.getenv("POSTGIS_PORT", "5432"))
    DATABASE: str = os.getenv("POSTGIS_DB", "afrimine")
    USER: str = os.getenv("POSTGIS_USER", "afrimine")
    PASSWORD: str = os.getenv("POSTGIS_PASS", "afrimine_pass")

    @property
    def connection_string(self) -> str:
        return (
            f"postgresql://{self.USER}:{self.PASSWORD}"
            f"@{self.HOST}:{self.PORT}/{self.DATABASE}"
        )


# Sentinel-2 band wavelengths (micrometers) for reference
SENTINEL2_WAVELENGTHS = {
    "B1": 0.443,  # Coastal aerosol
    "B2": 0.490,  # Blue
    "B3": 0.560,  # Green
    "B4": 0.665,  # Red
    "B5": 0.705,  # Red Edge 1
    "B6": 0.740,  # Red Edge 2
    "B7": 0.783,  # Red Edge 3
    "B8": 0.842,  # NIR
    "B8A": 0.865,  # Narrow NIR
    "B9": 0.945,  # Water vapour
    "B11": 1.610,  # SWIR 1
    "B12": 2.190,  # SWIR 2
}

# Colormap definitions for alteration maps
ALTERATION_COLORMAPS = {
    "iron_oxide": "YlOrRd",
    "clay": "YlGnBu",
    "silica": "RdPu",
    "chlorite": "Greens",
    "ndvi": "RdYlGn",
    "alteration_combined": "hot",
}
