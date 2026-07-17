#!/usr/bin/env python3
"""
AfriMine AI — Satellite Analysis Pipeline
==========================================

Complete mineral detection pipeline for Kenyan mining families.

Usage:
    python main.py                           # Run full pipeline with demo data
    python main.py --region migori           # Analyze specific region
    python main.py --bbox 34.0 -1.3 34.6 -0.8  # Custom bounding box
    python main.py --mode offline            # Offline mode (skip GEE, use cached)
    python main.py --help                    # Show all options

Pipeline stages:
    1. ACQUISITION  — Download Sentinel-2 from Google Earth Engine
    2. PROCESSING   — Band math, alteration index computation
    3. ANALYSIS     — Structural analysis, change detection
    4. SPATIAL      — PostGIS queries, proximity analysis
    5. VISUALIZATION — Maps, dashboards, reports
"""
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np

# Pipeline modules
from utils.helpers import setup_logging, print_banner, date_range, normalize_array
from utils.config import (
    KenyaBounds, SentinelConfig, AlterationConfig,
    StructuralConfig, PostGISConfig, OUTPUT_DIR, CACHE_DIR,
    ALTERATION_COLORMAPS
)

# GEE modules — graceful import (may not be installed)
try:
    from acquisition.gee_client import initialize_ee, verify_connection, EE_AVAILABLE
except ImportError:
    EE_AVAILABLE = False
    def initialize_ee(**kwargs):
        return False
    def verify_connection():
        return False

try:
    from acquisition.downloader import SentinelDownloader, download_region_data
except (ImportError, RuntimeError):
    SentinelDownloader = None
    download_region_data = None

from processing.band_math import BandMathEngine
from processing.alteration import AlterationMapper
from analysis.structural import StructuralAnalyzer
from analysis.change_detection import ChangeDetector
from analysis.spatial_queries import SpatialQueryEngine
from visualization.maps import MapGenerator

logger = logging.getLogger("afrimine.satellite.main")


def generate_demo_data(width: int = 512, height: int = 512) -> dict:
    """
    Generate synthetic Sentinel-2-like data for offline testing.

    Creates realistic-looking spectral data with:
    - Simulated alteration zones
    - Structural features (lineaments)
    - Vegetation patterns
    """
    logger.info("Generating synthetic demo data...")

    np.random.seed(42)

    # Create base terrain
    x = np.linspace(0, 4 * np.pi, width)
    y = np.linspace(0, 4 * np.pi, height)
    xx, yy = np.meshgrid(x, y)

    terrain = (
        0.3 * np.sin(xx * 0.5) * np.cos(yy * 0.3) +
        0.2 * np.sin(xx * 1.2 + yy * 0.8) +
        0.1 * np.random.randn(height, width)
    )

    # Simulate 7 Sentinel-2 bands: B2, B3, B4, B8, B8A, B11, B12
    bands = np.zeros((7, height, width), dtype=np.float32)

    # B2 (Blue): low reflectance, higher in exposed soil
    bands[0] = 0.08 + 0.05 * terrain + 0.02 * np.random.randn(height, width)

    # B3 (Green): vegetation has high green reflectance
    veg_mask = terrain < 0
    bands[1] = 0.06 + 0.04 * terrain + 0.15 * veg_mask + 0.02 * np.random.randn(height, width)

    # B4 (Red): absorbed by vegetation, higher in bare soil/iron oxide
    iron_zone = ((xx > 5) & (xx < 8) & (yy > 3) & (yy < 7)).astype(float)
    bands[2] = 0.07 + 0.03 * terrain + 0.3 * iron_zone + 0.02 * np.random.randn(height, width)

    # B8 (NIR): high in vegetation
    bands[3] = 0.15 + 0.05 * terrain + 0.4 * veg_mask + 0.03 * np.random.randn(height, width)

    # B8A (Narrow NIR)
    bands[4] = 0.18 + 0.04 * terrain + 0.35 * veg_mask + 0.02 * np.random.randn(height, width)

    # B11 (SWIR1): sensitive to clay minerals
    clay_zone = ((xx > 8) & (xx < 12) & (yy > 5) & (yy < 10)).astype(float)
    bands[5] = 0.15 + 0.08 * terrain + 0.25 * clay_zone + 0.03 * np.random.randn(height, width)

    # B12 (SWIR2): sensitive to silica
    silica_zone = ((xx > 3) & (xx < 6) & (yy > 8) & (yy < 12)).astype(float)
    bands[6] = 0.10 + 0.06 * terrain + 0.2 * silica_zone + 0.03 * np.random.randn(height, width)

    # Add structural features (lineaments)
    for _ in range(8):
        x0 = np.random.randint(50, width - 50)
        y0 = np.random.randint(50, height - 50)
        angle = np.random.uniform(0, np.pi)
        length = np.random.randint(80, 200)
        for t in range(-length // 2, length // 2):
            px = int(x0 + t * np.cos(angle))
            py = int(y0 + t * np.sin(angle))
            if 0 <= px < width and 0 <= py < height:
                for b in range(7):
                    bands[b, py, px] += 0.05
                # Widen the lineament
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        nx, ny = px + dx, py + dy
                        if 0 <= nx < width and 0 <= ny < height:
                            for b in range(7):
                                bands[b, ny, nx] += 0.02

    # Clip to realistic reflectance range
    bands = np.clip(bands, 0, 1)

    # Create "before" data for change detection (add some vegetation loss)
    bands_before = bands.copy()
    # Simulate mining area: vegetation removal
    mine_area = ((xx > 6) & (xx < 9) & (yy > 2) & (yy < 5)).astype(float)
    bands_before[3] -= 0.3 * mine_area  # Less NIR (no veg) in "after"
    bands_before[2] += 0.2 * mine_area  # More red (bare soil) in "after"
    bands_before = np.clip(bands_before, 0, 1)

    from rasterio.transform import from_bounds
    bbox = KenyaBounds.MIGORI
    transform = from_bounds(bbox[0], bbox[1], bbox[2], bbox[3], width, height)

    return {
        "data": bands,
        "data_before": bands_before,
        "bands": ["B2", "B3", "B4", "B8", "B8A", "B11", "B12"],
        "transform": transform,
        "crs": "EPSG:4326",
        "bounds": bbox,
        "shape": bands.shape,
    }


def run_pipeline(args):
    """
    Execute the full AfriMine satellite analysis pipeline.
    """
    print_banner()
    setup_logging(args.log_level)

    region_name = args.region
    bbox = args.bbox if args.bbox else getattr(KenyaBounds, region_name.upper(), KenyaBounds.MIGORI)
    start_date, end_date = date_range(args.days_back)

    logger.info(f"Region: {region_name}")
    logger.info(f"Bounding box: {bbox}")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Mode: {args.mode}")

    # ================================================================
    # STAGE 1: DATA ACQUISITION
    # ================================================================
    logger.info("=" * 60)
    logger.info("STAGE 1: SATELLITE DATA ACQUISITION")
    logger.info("=" * 60)

    if args.mode == "offline":
        logger.info("Offline mode: using synthetic demo data")
        imagery = generate_demo_data()
    else:
        if not EE_AVAILABLE or SentinelDownloader is None:
            logger.warning(
                "GEE not available (earthengine-api not installed), "
                "falling back to demo data"
            )
            imagery = generate_demo_data()
        else:
            logger.info("Initializing Google Earth Engine...")
            if not initialize_ee(project_id=args.gee_project):
                logger.warning("GEE init failed, falling back to demo data")
                imagery = generate_demo_data()
            else:
                try:
                    downloader = SentinelDownloader()
                    imagery = downloader.download_composite(
                        bbox=bbox,
                        start_date=start_date,
                        end_date=end_date,
                    )
                except Exception as e:
                    logger.warning(f"GEE download failed: {e}, falling back to demo data")
                    imagery = generate_demo_data()

    logger.info(f"Imagery shape: {imagery['data'].shape}")
    logger.info(f"Bands: {imagery['bands']}")

    # ================================================================
    # STAGE 2: ALTERATION MAPPING
    # ================================================================
    logger.info("=" * 60)
    logger.info("STAGE 2: ALTERATION MAPPING")
    logger.info("=" * 60)

    engine = BandMathEngine(band_order=imagery["bands"])
    mapper = AlterationMapper(band_math=engine)

    # Compute spectral indices
    indices = mapper.compute_indices(imagery["data"])

    # Classify alteration zones
    classification = mapper.classify_alteration_zones(indices)

    # Compute alteration intensity
    intensity = mapper.compute_alteration_intensity(indices)

    # Detect anomalies
    anomaly_mask, threshold = mapper.detect_anomalies(intensity)

    # Save indices as GeoTIFF
    mapper.save_indices_geotiff(
        indices, imagery["transform"], imagery["crs"],
        filename=f"alteration_{region_name}.tif"
    )

    # Generate report
    report = mapper.generate_report(indices, classification, intensity, region_name)
    report_path = OUTPUT_DIR / "alteration" / f"report_{region_name}.txt"
    with open(report_path, "w") as f:
        f.write(report)
    logger.info(f"Report saved: {report_path}")

    # ================================================================
    # STAGE 3: STRUCTURAL ANALYSIS
    # ================================================================
    logger.info("=" * 60)
    logger.info("STAGE 3: STRUCTURAL ANALYSIS")
    logger.info("=" * 60)

    struct_analyzer = StructuralAnalyzer()

    # Detect lineaments from NIR band (good contrast)
    nir_band = imagery["data"][3]  # B8
    struct_result = struct_analyzer.detect_lineaments(nir_band)

    logger.info(f"Lineaments detected: {struct_result.statistics['count']}")
    if struct_result.statistics["count"] > 0:
        logger.info(f"Dominant orientation: {struct_result.statistics['dominant_orientation']:.1f}°")
        logger.info(f"Mean length: {struct_result.statistics['mean_length']:.1f} pixels")

    # Drainage analysis from NDVI (water index)
    if "ndwi" in indices:
        drainage = struct_analyzer.drainage_analysis(indices["ndwi"].normalized)
        logger.info(f"Drainage density: {drainage['drainage_density']:.4f}")

    # ================================================================
    # STAGE 4: CHANGE DETECTION (if before/after data available)
    # ================================================================
    logger.info("=" * 60)
    logger.info("STAGE 4: CHANGE DETECTION")
    logger.info("=" * 60)

    detector = ChangeDetector()

    if "data_before" in imagery:
        # Compute NDVI for both dates
        ndvi_before_engine = BandMathEngine(band_order=imagery["bands"])
        ndvi_after_engine = BandMathEngine(band_order=imagery["bands"])

        ndvi_before = ndvi_before_engine.ndvi(imagery["data_before"]).data
        ndvi_after = ndvi_after_engine.ndvi(imagery["data"]).data

        change_result = detector.comprehensive_change(
            bands_before=imagery["data_before"],
            bands_after=imagery["data"],
            ndvi_before=ndvi_before,
            ndvi_after=ndvi_after,
        )

        # Detect mining expansion
        mining = detector.detect_mining_expansion(change_result)
        logger.info(f"Mining activity detected: {mining['mining_likely']}")
        logger.info(f"Confidence: {mining['confidence']:.2f}")
        logger.info(f"Change clusters: {mining['n_significant_clusters']}")
    else:
        logger.info("No before/after data for change detection")
        change_result = None

    # ================================================================
    # STAGE 5: SPATIAL QUERIES
    # ================================================================
    logger.info("=" * 60)
    logger.info("STAGE 5: SPATIAL QUERIES")
    logger.info("=" * 60)

    spatial = SpatialQueryEngine(use_postgis=args.use_postgis)

    # Insert sample points (demo)
    sample_points = [
        ("MK-001", 34.25, -1.05, "gold"),
        ("MK-002", 34.30, -1.10, "copper"),
        ("MK-003", 34.35, -0.95, "titanium"),
    ]

    for name, lon, lat, mineral in sample_points:
        spatial.insert_sample_point(
            name=name, lon=lon, lat=lat,
            mineral_type=mineral,
            collection_date="2024-06-15",
        )

    # Insert detected lineaments
    for lam in struct_result.lineaments[:50]:  # Top 50
        # Convert pixel to geo coords
        from rasterio.transform import xy
        lon1, lat1 = xy(imagery["transform"], lam.y1, lam.x1)
        lon2, lat2 = xy(imagery["transform"], lam.y2, lam.x2)
        spatial.insert_lineament(lon1, lat1, lon2, lat2, lam.length, lam.orientation)

    # Proximity analysis
    fault_samples = spatial.samples_near_faults(buffer_m=2000)
    logger.info(f"Samples near faults: {len(fault_samples)}")

    # Buffer analysis
    buffer_result = spatial.buffer_analysis(
        point=(34.25, -1.05),
        radii=[500, 1000, 2000, 5000]
    )

    # Export GeoJSON
    spatial.export_geojson("sample_points")

    # ================================================================
    # STAGE 6: VISUALIZATION
    # ================================================================
    logger.info("=" * 60)
    logger.info("STAGE 6: VISUALIZATION")
    logger.info("=" * 60)

    viz = MapGenerator()

    # Alteration heatmaps
    for name, idx in indices.items():
        if idx.normalized is not None:
            viz.plot_alteration_heatmap(
                idx.normalized,
                title=f"{name.replace('_', ' ').title()} — {region_name}",
                cmap=ALTERATION_COLORMAPS.get(name, "viridis"),
                filename=f"heatmap_{name}_{region_name}.png",
            )

    # Alteration composite
    composite = mapper.engine.alteration_composite(indices)
    viz.plot_alteration_composite(composite, filename=f"composite_{region_name}.png")

    # Classification map
    viz.plot_alteration_heatmap(
        classification.astype(float),
        title=f"Alteration Zone Classification — {region_name}",
        cmap="Set1",
        filename=f"classification_{region_name}.png",
        vmin=0, vmax=5,
    )

    # Intensity map
    viz.plot_alteration_heatmap(
        intensity,
        title=f"Alteration Intensity — {region_name}",
        cmap="hot",
        filename=f"intensity_{region_name}.png",
    )

    # Lineament map
    viz.plot_lineaments(
        nir_band, struct_result.lineaments,
        title=f"Structural Lineaments — {region_name}",
        filename=f"lineaments_{region_name}.png",
    )

    # Rose diagram
    viz.plot_rose_diagram(
        struct_result.orientation_histogram,
        struct_result.orientation_bins,
        title=f"Lineament Orientation — {region_name}",
        filename=f"rose_{region_name}.png",
    )

    # Lineament density
    viz.plot_density_map(
        struct_result.density_map,
        title=f"Lineament Density — {region_name}",
        filename=f"density_{region_name}.png",
    )

    # Change detection
    if change_result is not None:
        viz.plot_change_detection(
            change_result.change_magnitude,
            change_result.binary_mask,
            ndvi_change=change_result.ndvi_change,
            title=f"Change Detection — {region_name}",
            filename=f"change_{region_name}.png",
        )

    # Dashboard
    viz.create_dashboard(
        {k: v.normalized for k, v in indices.items() if v.normalized is not None},
        classification,
        intensity,
        lineaments=struct_result.lineaments,
        region_name=region_name,
        filename=f"dashboard_{region_name}.png",
    )

    # ================================================================
    # SUMMARY
    # ================================================================
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)

    output_files = list(OUTPUT_DIR.rglob("*"))
    logger.info(f"Output files: {len(output_files)}")
    for f in sorted(output_files):
        if f.is_file():
            logger.info(f"  {f.relative_to(OUTPUT_DIR)} ({f.stat().st_size / 1024:.1f} KB)")

    print("\n✅ AfriMine satellite analysis pipeline completed successfully!")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print(f"🗺️  Region analyzed: {region_name}")
    print(f"📊 Spectral indices: {len(indices)}")
    print(f"〰️  Lineaments: {struct_result.statistics['count']}")
    if change_result:
        print(f"🔄 Changed area: {change_result.statistics['changed_percent']:.1f}%")

    return {
        "indices": indices,
        "classification": classification,
        "intensity": intensity,
        "struct_result": struct_result,
        "change_result": change_result,
        "output_dir": str(OUTPUT_DIR),
    }


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="AfriMine AI — Satellite Analysis Pipeline for Kenyan Mining",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Regions:
  turkana    — Turkana County (mineral sands)
  kwale      — Kwale County (titanium mining)
  migori     — Migori County (gold mining)
  taita      — Taita Taveta (gemstones)
  homa_bay   — Homa Bay (rare earth elements)

Examples:
  python main.py --region migori --mode offline
  python main.py --region turkana --days-back 60
  python main.py --bbox 34.0 -1.3 34.6 -0.8 --mode gee
  python main.py --use-postgis --region kwale
        """
    )

    parser.add_argument(
        "--region", type=str, default="migori",
        choices=["turkana", "kwale", "migori", "taita", "homa_bay"],
        help="Kenyan mining region to analyze (default: migori)",
    )
    parser.add_argument(
        "--bbox", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help="Custom bounding box (overrides --region)",
    )
    parser.add_argument(
        "--days-back", type=int, default=30,
        help="Number of days to look back for imagery (default: 30)",
    )
    parser.add_argument(
        "--mode", type=str, default="offline",
        choices=["gee", "offline"],
        help="Data source: 'gee' for Google Earth Engine, 'offline' for demo data",
    )
    parser.add_argument(
        "--gee-project", type=str, default=None,
        help="Google Earth Engine project ID",
    )
    parser.add_argument(
        "--use-postgis", action="store_true",
        help="Use PostGIS for spatial queries (requires running PostGIS server)",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        results = run_pipeline(args)
    except KeyboardInterrupt:
        print("\n⚠️ Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"\n❌ Pipeline failed: {e}")
        sys.exit(1)
