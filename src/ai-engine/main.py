#!/usr/bin/env python3
"""
AfriMine AI — Main Entry Point
Mineral detection and analysis platform for Kenyan mining families.

Usage:
    python main.py                          # Run demo mode
    python main.py analyze <image_path>     # Analyze a single sample
    python main.py pipeline                 # Run full pipeline
    python main.py server                   # Start API server
    python main.py crew                     # Run CrewAI multi-agent workflow
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import load_config, AfriMineConfig
from utils.logger import setup_logger


def cmd_analyze(args, config: AfriMineConfig):
    """Analyze a single mineral sample."""
    from agents.analysis_agent import AnalysisAgent
    from models.classifier import create_classifier

    logger = logging.getLogger("afrimine")
    logger.info(f"Analyzing sample: {args.image}")

    classifier = create_classifier(config.model)
    agent = AnalysisAgent(classifier=classifier)

    xrf_data = None
    if args.xrf:
        with open(args.xrf) as f:
            xrf_data = json.load(f)

    result = agent.analyze_sample(
        image_path=args.image,
        xrf_data=xrf_data,
        location={"lat": args.lat, "lon": args.lon, "sample_id": args.sample_id} if args.lat else None,
    )

    print("\n" + "=" * 60)
    print("AFRIMINE AI — Sample Analysis Result")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))
    return result


def cmd_pipeline(args, config: AfriMineConfig):
    """Run the full analysis pipeline."""
    from pipelines.analysis_pipeline import AnalysisPipeline

    logger = logging.getLogger("afrimine")
    logger.info("Starting full analysis pipeline...")

    pipeline = AnalysisPipeline(config)

    # Load sample images from directory or use demo data
    sample_images = []
    if args.samples_dir:
        samples_path = Path(args.samples_dir)
        for img_path in sorted(samples_path.glob("*.jpg")) + sorted(samples_path.glob("*.png")):
            sample_images.append({"image_path": str(img_path)})
    else:
        # Demo: create synthetic sample data
        logger.info("No samples directory specified — running demo pipeline")
        sample_images = _create_demo_samples()

    area = {
        "lat_min": args.lat_min or -1.0,
        "lat_max": args.lat_max or 0.0,
        "lon_min": args.lon_min or 36.0,
        "lon_max": args.lon_max or 37.0,
        "county": args.county or "Taita Taveta",
        "spacing_m": args.spacing or 500,
    }

    miner_info = {
        "name": "Demo Miner",
        "nationality": "kenyan",
        "county": area["county"],
        "has_licence": False,
        "eia_licence": False,
    }

    results = pipeline.run_full_pipeline(
        area=area,
        sample_images=sample_images,
        miner_info=miner_info,
        licence_type=args.licence_type or "artisanal_mining_permit",
    )

    # Print summary
    print("\n" + "=" * 60)
    print("AFRIMINE AI — Pipeline Results Summary")
    print("=" * 60)
    summary = results.get("analysis", {}).get("summary", {})
    print(f"Total samples: {summary.get('total_samples', 0)}")
    print(f"Dominant mineral: {summary.get('dominant_mineral', 'N/A')}")
    print(f"Average value score: {summary.get('average_value_score', 0)}")
    print(f"Compliance: {results.get('compliance', {}).get('overall_status', 'N/A')}")
    print(f"Report: {results.get('report', {}).get('path', 'N/A')}")

    # Save full results
    output_path = config.output_dir / "pipeline_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results saved to: {output_path}")

    return results


def cmd_crew(args, config: AfriMineConfig):
    """Run the CrewAI multi-agent workflow."""
    from agents.crew import run_crew

    input_data = {
        "county": args.county or "Taita Taveta",
        "lat_min": args.lat_min or -4.0,
        "lat_max": args.lat_max or -3.5,
        "lon_min": args.lon_min or 38.5,
        "lon_max": args.lon_max or 39.0,
        "spacing_m": args.spacing or 500,
        "n_samples": 10,
        "sample_images": _create_demo_samples(),
        "miner_info": {
            "name": "Demo Miner",
            "nationality": "kenyan",
            "county": args.county or "Taita Taveta",
        },
        "licence_type": args.licence_type or "artisanal_mining_permit",
    }

    result = run_crew(
        input_data,
        gemini_api_key=config.agents.gemini_api_key,
        gemini_model=config.agents.gemini_model,
    )

    print("\n" + "=" * 60)
    print("AFRIMINE AI — Crew Result")
    print("=" * 60)
    if "crew_result" in result:
        print(result["crew_result"])
    else:
        print(json.dumps(result, indent=2, default=str))


def cmd_server(args, config: AfriMineConfig):
    """Start the FastAPI server."""
    try:
        import uvicorn
        from api import create_app

        app = create_app(config)
        uvicorn.run(app, host=args.host or "0.0.0.0", port=args.port or 8000)
    except ImportError:
        print("FastAPI/uvicorn not installed. Install with: pip install fastapi uvicorn")
        sys.exit(1)


def cmd_geostat(args, config: AfriMineConfig):
    """Run geostatistical analysis on sample data."""
    from geostatistics.kriging import KrigingInterpolator
    from geostatistics.variograms import VariogramAnalyzer
    import numpy as np

    logger = logging.getLogger("afrimine")

    # Demo data or load from file
    if args.data_file:
        with open(args.data_file) as f:
            data = json.load(f)
        lons = np.array([d["lon"] for d in data])
        lats = np.array([d["lat"] for d in data])
        grades = np.array([d["grade"] for d in data])
    else:
        logger.info("Running demo geostatistics with synthetic data")
        rng = np.random.default_rng(42)
        n = 30
        lons = rng.uniform(36.0, 37.0, n)
        lats = rng.uniform(-1.0, 0.0, n)
        # Simulate gold grades with spatial correlation
        grades = 2.0 + 1.5 * np.sin(lons * 3) * np.cos(lats * 2) + rng.normal(0, 0.5, n)
        grades = np.maximum(grades, 0)

    # Variogram analysis
    var_analyzer = VariogramAnalyzer(n_lags=10)
    experimental = var_analyzer.compute_experimental(lons, lats, grades)
    print("\nVariogram Analysis:")
    print(f"  Model: {experimental['model']['model']}")
    print(f"  Nugget: {experimental['model']['nugget']:.4f}")
    print(f"  Sill: {experimental['model']['sill']:.4f}")
    print(f"  Range: {experimental['model']['range']:.4f}")

    # Kriging interpolation
    kriger = KrigingInterpolator(variogram_model="spherical")
    kriger.fit_ordinary(lons, lats, grades)
    grid = kriger.predict_grid(
        lons.min() - 0.1, lons.max() + 0.1,
        lats.min() - 0.1, lats.max() + 0.1,
        resolution=30,
    )

    print(f"\nKriging Grid: {grid['resolution']}x{grid['resolution']}")
    print(f"  Predicted range: {np.min(grid['predicted']):.2f} — {np.max(grid['predicted']):.2f}")

    # Save
    output = {"variogram": experimental, "grid_summary": {
        "resolution": grid["resolution"],
        "predicted_min": float(np.min(grid["predicted"])),
        "predicted_max": float(np.max(grid["predicted"])),
    }}
    output_path = config.output_dir / "geostat_results.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


def cmd_satellite(args, config: AfriMineConfig):
    """Run satellite image processing."""
    from satellite.sentinel2 import Sentinel2Processor
    import numpy as np

    processor = Sentinel2Processor()

    if args.data_dir:
        processor.load_from_directory(args.data_dir)
    else:
        logger = logging.getLogger("afrimine")
        logger.info("Running demo satellite analysis with synthetic data")
        rng = np.random.default_rng(42)
        h, w = 100, 100
        processor.bands = {
            "B02": rng.uniform(500, 2000, (h, w)).astype(np.float32),  # Blue
            "B03": rng.uniform(600, 2500, (h, w)).astype(np.float32),  # Green
            "B04": rng.uniform(400, 2200, (h, w)).astype(np.float32),  # Red
            "B08": rng.uniform(1000, 4000, (h, w)).astype(np.float32), # NIR
            "B11": rng.uniform(800, 3000, (h, w)).astype(np.float32),  # SWIR1
            "B12": rng.uniform(600, 2500, (h, w)).astype(np.float32),  # SWIR2
        }

    indices = processor.compute_alteration_indices()
    zones = processor.detect_alteration_zones(indices)

    print("\n" + "=" * 60)
    print("AFRIMINE AI — Satellite Analysis Results")
    print("=" * 60)
    for name, stats in zones["statistics"].items():
        print(f"  {name}: anomaly_pixels={stats.get('anomaly_pixels', 0)}, "
              f"anomaly_pct={stats.get('anomaly_pct', 0):.1f}%")
    print(f"\nRecommendation: {zones['recommendation']}")


def _create_demo_samples() -> list[dict]:
    """Create synthetic demo sample data for testing without real images."""
    import numpy as np
    from PIL import Image

    demo_dir = Path(".openclaw/tmp/afrimine_demo")
    demo_dir.mkdir(parents=True, exist_ok=True)

    samples = []
    rng = np.random.default_rng(42)

    demo_data = [
        {"name": "gold_ore", "color": (180, 155, 50), "mineral": "gold"},
        {"name": "pyrite_sample", "color": (180, 175, 60), "mineral": "pyrite"},
        {"name": "quartz_crystal", "color": (220, 220, 230), "mineral": "quartz"},
        {"name": "copper_ore", "color": (40, 140, 80), "mineral": "copper"},
        {"name": "ruby_specimen", "color": (160, 30, 40), "mineral": "ruby"},
    ]

    for i, data in enumerate(demo_data):
        # Create a synthetic mineral image
        img_array = np.zeros((260, 260, 3), dtype=np.uint8)
        base_color = data["color"]

        for c in range(3):
            img_array[:, :, c] = np.clip(
                base_color[c] + rng.normal(0, 20, (260, 260)),
                0, 255
            ).astype(np.uint8)

        # Add texture
        noise = rng.normal(0, 15, (260, 260, 3)).astype(np.int16)
        img_array = np.clip(img_array.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        img_path = demo_dir / f"{data['name']}.png"
        Image.fromarray(img_array).save(str(img_path))

        samples.append({
            "image_path": str(img_path),
            "location": {
                "lat": -3.5 + rng.uniform(-0.5, 0.5),
                "lon": 38.5 + rng.uniform(-0.5, 0.5),
                "sample_id": f"DEMO_{i+1:03d}",
            },
        })

    return samples


def main():
    parser = argparse.ArgumentParser(
        description="AfriMine AI — Mineral Detection Platform for Kenyan Mining Families",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py demo                              Run demo with synthetic data
  python main.py analyze sample.jpg                Analyze a single mineral image
  python main.py pipeline --samples-dir ./images   Run full pipeline on a directory
  python main.py geostat                           Run geostatistics demo
  python main.py satellite                         Run satellite analysis demo
  python main.py crew                              Run CrewAI multi-agent workflow
        """,
    )

    subparsers = parser.add_subparsers(dest="command")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a single sample")
    analyze_parser.add_argument("image", help="Path to mineral image")
    analyze_parser.add_argument("--xrf", help="Path to XRF data JSON file")
    analyze_parser.add_argument("--lat", type=float, help="Sample latitude")
    analyze_parser.add_argument("--lon", type=float, help="Sample longitude")
    analyze_parser.add_argument("--sample-id", default="SAMPLE_001", help="Sample ID")

    # Pipeline command
    pipeline_parser = subparsers.add_parser("pipeline", help="Run full analysis pipeline")
    pipeline_parser.add_argument("--samples-dir", help="Directory containing sample images")
    pipeline_parser.add_argument("--lat-min", type=float, default=-1.0)
    pipeline_parser.add_argument("--lat-max", type=float, default=0.0)
    pipeline_parser.add_argument("--lon-min", type=float, default=36.0)
    pipeline_parser.add_argument("--lon-max", type=float, default=37.0)
    pipeline_parser.add_argument("--county", default="Taita Taveta")
    pipeline_parser.add_argument("--spacing", type=float, default=500, help="Grid spacing in metres")
    pipeline_parser.add_argument("--licence-type", default="artisanal_mining_permit")

    # Crew command
    crew_parser = subparsers.add_parser("crew", help="Run CrewAI multi-agent workflow")
    crew_parser.add_argument("--county", default="Taita Taveta")
    crew_parser.add_argument("--lat-min", type=float, default=-4.0)
    crew_parser.add_argument("--lat-max", type=float, default=-3.5)
    crew_parser.add_argument("--lon-min", type=float, default=38.5)
    crew_parser.add_argument("--lon-max", type=float, default=39.0)
    crew_parser.add_argument("--spacing", type=float, default=500)
    crew_parser.add_argument("--licence-type", default="artisanal_mining_permit")

    # Geostat command
    geostat_parser = subparsers.add_parser("geostat", help="Run geostatistical analysis")
    geostat_parser.add_argument("--data-file", help="JSON file with sample data (lon, lat, grade)")

    # Satellite command
    sat_parser = subparsers.add_parser("satellite", help="Run satellite image analysis")
    sat_parser.add_argument("--data-dir", help="Directory with Sentinel-2 band files")

    # Server command
    server_parser = subparsers.add_parser("server", help="Start API server")
    server_parser.add_argument("--host", default="0.0.0.0")
    server_parser.add_argument("--port", type=int, default=8000)

    # Demo command (default)
    subparsers.add_parser("demo", help="Run demo with synthetic data")

    args = parser.parse_args()

    # Load config
    config = load_config()
    logger = setup_logger(config.log_level)

    if not args.command or args.command == "demo":
        # Run demo mode
        print("=" * 60)
        print("AFRIMINE AI — Mineral Detection Platform")
        print("Demo Mode")
        print("=" * 60)

        # 1. Analyze demo samples
        args_pipeline = argparse.Namespace(
            samples_dir=None, lat_min=-1.0, lat_max=0.0,
            lon_min=36.0, lon_max=37.0, county="Taita Taveta",
            spacing=500, licence_type="artisanal_mining_permit",
        )
        cmd_pipeline(args_pipeline, config)

    elif args.command == "analyze":
        cmd_analyze(args, config)
    elif args.command == "pipeline":
        cmd_pipeline(args, config)
    elif args.command == "crew":
        cmd_crew(args, config)
    elif args.command == "geostat":
        cmd_geostat(args, config)
    elif args.command == "satellite":
        cmd_satellite(args, config)
    elif args.command == "server":
        cmd_server(args, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
