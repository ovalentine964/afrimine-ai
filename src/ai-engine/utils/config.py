"""
AfriMine AI — Configuration Management
Loads settings from environment variables and YAML config files.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import yaml


BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class ModelConfig:
    """Classifier model configuration."""
    backbone: str = "efficientnet_b2"
    num_classes: int = 20
    input_size: tuple = (260, 260)
    checkpoint_path: Optional[str] = None
    onnx_path: Optional[str] = None
    tflite_path: Optional[str] = None
    confidence_threshold: float = 0.45
    device: str = "cpu"  # cpu | cuda | mps


@dataclass
class AgentConfig:
    """Multi-agent system configuration."""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    crew_verbose: bool = True
    max_iterations: int = 10


@dataclass
class SatelliteConfig:
    """Satellite processing configuration."""
    sentinel_hub_id: str = ""
    sentinel_hub_secret: str = ""
    default_resolution: int = 10  # metres
    cloud_cover_max: float = 0.2


@dataclass
class GeostatConfig:
    """Geostatistics configuration."""
    variogram_model: str = "spherical"
    kriging_method: str = "ordinary"
    n_lags: int = 12
    max_range_km: float = 50.0


@dataclass
class AfriMineConfig:
    """Root configuration for the entire system."""
    model: ModelConfig = field(default_factory=ModelConfig)
    agents: AgentConfig = field(default_factory=AgentConfig)
    satellite: SatelliteConfig = field(default_factory=SatelliteConfig)
    geostat: GeostatConfig = field(default_factory=GeostatConfig)
    data_dir: Path = BASE_DIR / "data"
    output_dir: Path = BASE_DIR / "output"
    log_level: str = "INFO"


def load_config(config_path: Optional[str] = None) -> AfriMineConfig:
    """Load configuration from YAML file and environment overrides."""
    cfg = AfriMineConfig()

    # Load YAML if present
    if config_path is None:
        config_path = str(BASE_DIR / "config.yaml")

    p = Path(config_path)
    if p.exists():
        with open(p) as f:
            raw = yaml.safe_load(f) or {}

        model_raw = raw.get("model", {})
        cfg.model = ModelConfig(
            backbone=model_raw.get("backbone", cfg.model.backbone),
            num_classes=model_raw.get("num_classes", cfg.model.num_classes),
            input_size=tuple(model_raw.get("input_size", list(cfg.model.input_size))),
            checkpoint_path=model_raw.get("checkpoint_path"),
            onnx_path=model_raw.get("onnx_path"),
            tflite_path=model_raw.get("tflite_path"),
            confidence_threshold=model_raw.get("confidence_threshold", cfg.model.confidence_threshold),
            device=model_raw.get("device", cfg.model.device),
        )

        agent_raw = raw.get("agents", {})
        cfg.agents = AgentConfig(
            gemini_model=agent_raw.get("gemini_model", cfg.agents.gemini_model),
            crew_verbose=agent_raw.get("crew_verbose", cfg.agents.crew_verbose),
            max_iterations=agent_raw.get("max_iterations", cfg.agents.max_iterations),
        )

        sat_raw = raw.get("satellite", {})
        cfg.satellite = SatelliteConfig(
            default_resolution=sat_raw.get("default_resolution", cfg.satellite.default_resolution),
            cloud_cover_max=sat_raw.get("cloud_cover_max", cfg.satellite.cloud_cover_max),
        )

        geo_raw = raw.get("geostat", {})
        cfg.geostat = GeostatConfig(
            variogram_model=geo_raw.get("variogram_model", cfg.geostat.variogram_model),
            kriging_method=geo_raw.get("kriging_method", cfg.geostat.kriging_method),
            n_lags=geo_raw.get("n_lags", cfg.geostat.n_lags),
            max_range_km=geo_raw.get("max_range_km", cfg.geostat.max_range_km),
        )

    # Environment overrides (secrets always from env)
    cfg.agents.gemini_api_key = os.environ.get("GEMINI_API_KEY", cfg.agents.gemini_api_key)
    cfg.satellite.sentinel_hub_id = os.environ.get("SENTINEL_HUB_ID", cfg.satellite.sentinel_hub_id)
    cfg.satellite.sentinel_hub_secret = os.environ.get("SENTINEL_HUB_SECRET", cfg.satellite.sentinel_hub_secret)
    cfg.model.device = os.environ.get("AFRIMINE_DEVICE", cfg.model.device)

    # Ensure directories exist
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    return cfg
