# AfriMine AI — GIS & Remote Sensing Engineering Reference

> A practical reference for engineers building spatial analysis features on the AfriMine mining intelligence platform.

---

## A. SATELLITE IMAGERY

### A1. Sentinel-2 Bands (13 Bands)

Sentinel-2 is the primary free multispectral satellite for mineral exploration. It carries the MSI (Multi-Spectral Instrument) with 13 bands at varying spatial resolutions.

| Band | Name | Central λ (nm) | Resolution | Measures |
|------|------|----------------|------------|----------|
| B1 | Coastal aerosol | 443 | 60 m | Atmospheric correction, coastal water |
| B2 | Blue | 490 | 10 m | Water bodies, deep vegetation |
| B3 | Green | 560 | 10 m | Vegetation vigor (green peak) |
| B4 | Red | 665 | 10 m | Chlorophyll absorption, iron oxides |
| B5 | Red Edge 1 | 705 | 20 m | Vegetation stress detection |
| B6 | Red Edge 2 | 740 | 20 m | Vegetation canopy structure |
| B7 | Red Edge 3 | 783 | 20 m | Chlorophyll content |
| B8 | NIR | 842 | 10 m | Biomass, vegetation structure |
| B8A | Narrow NIR | 865 | 20 m | Water vapor, chlorite detection |
| B9 | Water vapor | 940 | 60 m | Atmospheric water vapor |
| B10 | SWIR - Cirrus | 1375 | 60 m | Cirrus cloud detection |
| B11 | SWIR 1 | 1610 | 20 m | Clay minerals, soil moisture |
| B12 | SWIR 2 | 2190 | 20 m | Clay/carbonate minerals, dry vegetation |

**How it translates to code:**
```python
import rasterio

def load_sentinel2_bands(s2_dir: str) -> dict[str, rasterio.DatasetReader]:
    """Load all Sentinel-2 bands from a directory."""
    band_map = {
        "B1": "B01", "B2": "B02", "B3": "B03", "B4": "B04",
        "B5": "B05", "B6": "B06", "B7": "B07", "B8": "B08",
        "B8A": "8A", "B9": "B09", "B10": "B10", "B11": "B11", "B12": "B12",
    }
    bands = {}
    for name, fname in band_map.items():
        path = f"{s2_dir}/{fname}.jp2"  # or .tif after conversion
        bands[name] = rasterio.open(path)
    return bands

def stack_bands(band_paths: list[str], out_path: str):
    """Stack multiple bands into a single multi-band GeoTIFF."""
    src_files = [rasterio.open(p) for p in band_paths]
    profile = src_files[0].profile.copy()
    profile.update(count=len(src_files))
    with rasterio.open(out_path, "w", **profile) as dst:
        for i, src in enumerate(src_files, 1):
            dst.write(src.read(1), i)
            src.close()
```

**Where in AfriMine:** Raw satellite data ingestion pipeline. Every spectral analysis downstream depends on correctly loaded bands with proper metadata (CRS, transform, nodata).

---

### A2. Band Ratios for Mineral Detection

Band ratios exploit the diagnostic absorption/reflection features of minerals at specific wavelengths. A ratio normalizes illumination differences and highlights specific mineral signatures.

| Ratio | Formula | Detects | Why It Works |
|-------|---------|---------|--------------|
| Iron Oxide | B4 / B2 | Hematite, goethite, gossan | Iron oxides absorb blue (B2) and reflect red (B4) |
| Clay | B11 / B12 | Kaolinite, illite, montmorillonite | Clay has OH⁻ absorption near 2200 nm (B12), reflects at 1610 nm (B11) |
| Chlorite/Muscovite | B8A / B11 | Chlorite, epidote, muscovite | These minerals absorb in SWIR (B11) relative to NIR (B8A) |
| Ferrous Iron | B4 / B3 | Ferrous vs ferric iron | Ferrous iron absorbs green more than red |
| Gossan Index | (B4 * B11) / (B3 * B12) | Oxidized surface (gossan) | Combined iron + clay signature of weathered sulfides |

**How it translates to code:**
```python
import numpy as np
import rasterio

def mineral_ratio(band_num_path: str, band_den_path: str, out_path: str):
    """Compute a band ratio and save as GeoTIFF."""
    with rasterio.open(band_num_path) as num_src, \
         rasterio.open(band_den_path) as den_src:
        num = num_src.read(1).astype(np.float32)
        den = den_src.read(1).astype(np.float32)
        
        # Avoid division by zero
        ratio = np.where(den > 0, num / den, 0)
        
        profile = num_src.profile.copy()
        profile.update(dtype="float32", nodata=0)
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(ratio, 1)

def iron_oxide_ratio(s2_dir: str, out_path: str):
    """B4/B2 — Iron oxide index."""
    mineral_ratio(f"{s2_dir}/B04.tif", f"{s2_dir}/B02.tif", out_path)

def clay_ratio(s2_dir: str, out_path: str):
    """B11/B12 — Clay mineral index."""
    mineral_ratio(f"{s2_dir}/B11.tif", f"{s2_dir}/B12.tif", out_path)

def chlorite_ratio(s2_dir: str, out_path: str):
    """B8A/B11 — Chlorite/muscovite index."""
    mineral_ratio(f"{s2_dir}/8A.tif", f"{s2_dir}/B11.tif", out_path)

# Composite alteration map — stack ratios for ML input
def build_alteration_stack(s2_dir: str, out_path: str):
    """Stack all mineral ratios into a single multi-band raster."""
    import tempfile, os
    ratios = {
        "iron_oxide": (f"{s2_dir}/B04.tif", f"{s2_dir}/B02.tif"),
        "clay": (f"{s2_dir}/B11.tif", f"{s2_dir}/B12.tif"),
        "chlorite": (f"{s2_dir}/8A.tif", f"{s2_dir}/B11.tif"),
    }
    paths = []
    for name, (num, den) in ratios.items():
        p = f"{s2_dir}/ratio_{name}.tif"
        mineral_ratio(num, den, p)
        paths.append(p)
    stack_bands(paths, out_path)
```

**Where in AfriMine:** Prospectivity mapping — these ratios are primary features fed into ML models to predict mineral occurrence probability. Also used directly in alteration mapping dashboards.

---

### A3. NDVI — Vegetation Stress as Subsurface Indicator

NDVI (Normalized Difference Vegetation Index) measures vegetation health. In mineral exploration, anomalous vegetation stress can indicate:
- **Subsurface sulfide oxidation** → acidic groundwater → stressed roots
- **Metal toxicity** (Cu, Zn, Ni uptake by plants)
- **Altered soil chemistry** from hydrothermal systems

Formula: `NDVI = (NIR - Red) / (NIR + Red) = (B8 - B4) / (B8 + B4)`

Values: -1 to +1. Healthy vegetation ≈ 0.6–0.9. Stressed vegetation ≈ 0.2–0.4. Bare soil/water < 0.2.

**How it translates to code:**
```python
def compute_ndvi(s2_dir: str, out_path: str):
    """Compute NDVI from Sentinel-2 B8 (NIR) and B4 (Red)."""
    with rasterio.open(f"{s2_dir}/B08.tif") as nir_src, \
         rasterio.open(f"{s2_dir}/B04.tif") as red_src:
        nir = nir_src.read(1).astype(np.float32)
        red = red_src.read(1).astype(np.float32)
        
        ndvi = np.where((nir + red) > 0, (nir - red) / (nir + red), 0)
        
        profile = nir_src.profile.copy()
        profile.update(dtype="float32", nodata=-9999)
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(ndvi, 1)
    return out_path

def detect_stress_anomalies(ndvi_path: str, threshold: float = 0.3, out_path: str = None):
    """Identify pixels with NDVI below threshold (potential stress)."""
    with rasterio.open(ndvi_path) as src:
        ndvi = src.read(1)
        mask = (ndvi > 0) & (ndvi < threshold)  # stressed but vegetated
        
        if out_path:
            profile = src.profile.copy()
            profile.update(dtype="uint8", count=1, nodata=255)
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(mask.astype(np.uint8), 1)
    return mask
```

**Where in AfriMine:** Vegetation stress layer in the prospectivity model. Especially relevant in tropical African mining regions (DRC copper belt, West African gold) where surface expressions are subtle beneath canopy cover.

---

### A4. Alteration Mapping

Hydrothermal alteration creates diagnostic mineral assemblages around ore deposits:
- **Argillic** (clay-rich): kaolinite, illite → detected by B11/B12 ratio
- **Propylitic** (chlorite-epidote): → detected by B8A/B11 ratio
- **Silicification** (quartz-rich): high reflectance in SWIR
- **Iron oxide/hematite**: → detected by B4/B2 ratio

Alteration halos are concentric zones around deposits: silicic core → argillic → propylitic → unaltered. Detecting these patterns from space is a primary exploration tool.

**How it translates to code:**
```python
from sklearn.cluster import KMeans
import numpy as np

def classify_alteration(ratio_stack_path: str, n_classes: int = 5) -> np.ndarray:
    """Unsupervised classification of alteration zones from stacked ratios.
    
    Input: Multi-band GeoTIFF of mineral ratios (iron, clay, chlorite, etc.)
    Output: Classification map with alteration zone labels.
    """
    with rasterio.open(ratio_stack_path) as src:
        bands = src.read()  # shape: (n_bands, height, width)
        profile = src.profile.copy()
        mask = np.all(bands > 0, axis=0)  # valid pixels
    
    # Reshape to (n_pixels, n_bands)
    n_bands, h, w = bands.shape
    pixels = bands[:, mask].T  # (n_valid, n_bands)
    
    # KMeans clustering for alteration zones
    kmeans = KMeans(n_clusters=n_classes, random_state=42, n_init=10)
    labels = kmeans.fit_predict(pixels)
    
    # Map back to raster
    result = np.full((h, w), profile.get("nodata", 255), dtype=np.uint8)
    result[mask] = labels
    
    profile.update(dtype="uint8", count=1, nodata=255)
    return result, profile, kmeans.cluster_centers_

def threshold_alteration(iron_ratio: np.ndarray, clay_ratio: np.ndarray,
                         iron_thresh: float = 1.2, clay_thresh: float = 1.1) -> dict:
    """Simple threshold-based alteration mapping."""
    return {
        "iron_alteration": iron_ratio > iron_thresh,
        "clay_alteration": clay_ratio > clay_thresh,
        "combined": (iron_ratio > iron_thresh) & (clay_ratio > clay_thresh),
    }
```

**Where in AfriMine:** Core feature engineering for prospectivity models. Alteration maps are overlaid on geological maps to identify drill targets. The unsupervised approach is used for greenfield exploration; supervised classification when training data from known deposits exists.

---

## B. SPATIAL DATA

### B1. Data Formats

| Format | Type | Use Case | Strengths |
|--------|------|----------|-----------|
| **GeoTIFF** | Raster | Satellite imagery, DEMs, ratio maps | Metadata-embedded, cloud-optimized (COG), multi-band |
| **Shapefile** | Vector | Boundaries, drill holes, sample points | Legacy standard, universal support |
| **GeoJSON** | Vector | Web APIs, frontend mapping | Human-readable, native to web/JS, lightweight |
| **COG** | Raster | Cloud-native satellite data | HTTP range-request access, tiled, overview pyramids |
| **GeoPackage** | Vector/Raster | Modern replacement for Shapefile | Single file, supports rasters + vectors, no 2GB limit |

**How it translates to code:**
```python
import geopandas as gpd
import rasterio
from rasterio.io import MemoryFile
import json

# --- Reading/writing vectors ---
def load_geojson(path: str) -> gpd.GeoDataFrame:
    """Load GeoJSON into a GeoDataFrame."""
    gdf = gpd.read_file(path)
    return gdf

def save_geojson(gdf: gpd.GeoDataFrame, path: str):
    """Save GeoDataFrame as GeoJSON."""
    gdf.to_file(path, driver="GeoJSON")

def load_shapefile(path: str) -> gpd.GeoDataFrame:
    """Load Shapefile."""
    return gpd.read_file(path)

# --- Reading/writing rasters ---
def read_geotiff(path: str) -> tuple[np.ndarray, dict]:
    """Read a GeoTIFF and return (data, metadata)."""
    with rasterio.open(path) as src:
        data = src.read()
        meta = src.profile
    return data, meta

def write_geotiff(data: np.ndarray, profile: dict, out_path: str):
    """Write array to GeoTIFF."""
    with rasterio.open(out_path, "w", **profile) as dst:
        if data.ndim == 2:
            dst.write(data, 1)
        else:
            for i in range(data.shape[0]):
                dst.write(data[i], i + 1)

# --- Format conversion ---
def geotiff_to_cog(input_path: str, output_path: str):
    """Convert GeoTIFF to Cloud-Optimized GeoTIFF."""
    from rio_cogeo.cogeo import cog_translate
    cog_translate(input_path, output_path, cog_profile="deflate")
```

**Where in AfriMine:** All data ingestion. GeoTIFF/COG for raster layers (satellite, geophysics, DEMs). GeoJSON for the web API (prospect boundaries, sample locations, drill targets). Shapefile for legacy data from mining companies.

---

### B2. Coordinate Reference Systems (CRS)

| CRS | Type | Use Case |
|-----|------|----------|
| **WGS84 (EPSG:4326)** | Geographic (lat/lon) | Global standard, GPS, web maps, data exchange |
| **UTM zones** | Projected (meters) | Distance/area calculations, local analysis |
| Africa spans UTM zones 28N–37S | — | Choose the zone covering your AOI |

**Key rule:** Always store in WGS84, transform to UTM for measurements. Never mix CRS in spatial operations.

**How it translates to code:**
```python
import pyproj
from pyproj import Transformer
import geopandas as gpd

def get_utm_zone(longitude: float) -> int:
    """Return UTM zone number for a given longitude."""
    return int((longitude + 180) / 6) + 1

def get_utm_epsg(lon: float, lat: float) -> int:
    """Get EPSG code for the UTM zone at a given point."""
    zone = get_utm_zone(lon)
    hemisphere = "north" if lat >= 0 else "south"
    epsg_base = 32600 if hemisphere == "north" else 32700
    return epsg_base + zone

def reproject_gdf(gdf: gpd.GeoDataFrame, target_epsg: int) -> gpd.GeoDataFrame:
    """Reproject a GeoDataFrame to target CRS."""
    return gdf.to_crs(epsg=target_epsg)

def auto_utm_for_gdf(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Automatically reproject to the appropriate UTM zone."""
    centroid = gdf.geometry.unary_union.centroid
    epsg = get_utm_epsg(centroid.x, centroid.y)
    return gdf.to_crs(epsg=epsg)

def transform_point(lon: float, lat: float, from_epsg: int, to_epsg: int) -> tuple:
    """Transform a point between CRS."""
    transformer = Transformer.from_crs(from_epsg, to_epsg, always_xy=True)
    return transformer.transform(lon, lat)
```

**Where in AfriMine:** CRS transforms happen at every data boundary. Web API serves WGS84 GeoJSON. Spatial analysis (buffering, area, distance) runs in UTM. Storage uses WGS84. The `auto_utm_for_gdf` function is critical for African mining sites spanning multiple UTM zones.

---

### B3. Spatial Indexing (R-tree)

R-trees are tree data structures that group nearby objects using bounding boxes. They make spatial queries (nearest neighbor, intersection, within) fast — O(log n) instead of O(n).

**How it translates to code:**
```python
from rtree import index
import geopandas as gpd
from shapely.geometry import Point

class SpatialIndex:
    """R-tree spatial index for mining features."""
    
    def __init__(self):
        self.idx = index.Index()
        self.features = {}  # id -> feature data
    
    def insert(self, feature_id: int, geometry, data: dict = None):
        """Insert a feature with its bounding box."""
        self.idx.insert(feature_id, geometry.bounds)
        self.features[feature_id] = {"geometry": geometry, "data": data or {}}
    
    def query_bbox(self, minx: float, miny: float, maxx: float, maxy: float) -> list:
        """Find all features within a bounding box."""
        return [self.features[fid] for fid in self.idx.intersection((minx, miny, maxx, maxy))]
    
    def query_nearest(self, point: Point, k: int = 5) -> list:
        """Find k nearest features to a point."""
        ids = list(self.idx.nearest(point.bounds, k))
        return [(fid, self.features[fid]) for fid in ids if fid in self.features]
    
    @classmethod
    def from_geodataframe(cls, gdf: gpd.GeoDataFrame) -> "SpatialIndex":
        """Build index from a GeoDataFrame."""
        si = cls()
        for i, row in gdf.iterrows():
            si.insert(i, row.geometry, row.drop("geometry").to_dict())
        return si

# Quick nearest-neighbor with geopandas (uses spatial index internally)
def nearest_mine(gdf_mines: gpd.GeoDataFrame, point: Point) -> dict:
    """Find the nearest mine to a given point."""
    gdf_mines["distance"] = gdf_mines.geometry.distance(point)
    nearest = gdf_mines.loc[gdf_mines["distance"].idxmin()]
    return nearest.to_dict()
```

**Where in AfriMine:** Fast proximity queries — "find all known deposits within 10km of this prospect," "what's the nearest drill hole?" Used in the backend API for real-time spatial queries on large datasets (100k+ mining features across Africa).

---

### B4. PostGIS Spatial SQL

PostGIS extends PostgreSQL with spatial types and functions. It's the backbone for storing and querying geospatial data server-side.

**Key operations:**
```sql
-- Enable PostGIS (run once per database)
CREATE EXTENSION IF NOT EXISTS postgis;

-- Create a spatially-indexed table
CREATE TABLE mining_sites (
    id SERIAL PRIMARY KEY,
    name TEXT,
    commodity TEXT,
    geom GEOMETRY(Point, 4326)  -- WGS84
);
CREATE INDEX idx_mining_sites_geom ON mining_sites USING GIST (geom);

-- Insert with ST_SetSRID
INSERT INTO mining_sites (name, commodity, geom)
VALUES ('Kibali Gold', 'Au', ST_SetSRID(ST_MakePoint(30.2, 3.1), 4326));

-- Find all sites within 50km of a point
SELECT name, commodity,
       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(30.0, 3.0), 4326)::geography) / 1000 AS distance_km
FROM mining_sites
WHERE ST_DWithin(
    geom::geography,
    ST_SetSRID(ST_MakePoint(30.0, 3.0), 4326)::geography,
    50000  -- 50km in meters
)
ORDER BY distance_km;

-- Spatial join: mines inside geological provinces
SELECT m.name, g.province_name
FROM mining_sites m
JOIN geological_provinces g ON ST_Within(m.geom, g.geom);

-- Buffer and intersection: find all prospects overlapping alteration zones
SELECT p.name, p.grade
FROM prospects p
JOIN alteration_zones a ON ST_Intersects(p.geom, a.geom)
WHERE a.alteration_type = 'argillic';

-- Aggregate: count mines per province
SELECT g.province_name, COUNT(*) as mine_count
FROM mining_sites m
JOIN geological_provinces g ON ST_Within(m.geom, g.geom)
GROUP BY g.province_name
ORDER BY mine_count DESC;

-- Raster-vector intersection: extract raster values at point locations
-- (requires raster extension)
CREATE EXTENSION IF NOT EXISTS postgis_raster;

SELECT m.name, ST_Value(r.rast, 1, m.geom) AS ndvi_value
FROM mining_sites m
JOIN ndvi_raster r ON ST_Intersects(m.geom, r.rast);
```

**Python ↔ PostGIS:**
```python
from sqlalchemy import create_engine, text
import geopandas as gpd

def get_engine(db_url: str):
    return create_engine(db_url)

def query_spatial(db_url: str, sql: str) -> gpd.GeoDataFrame:
    """Execute a spatial SQL query and return GeoDataFrame."""
    engine = get_engine(db_url)
    return gpd.read_postgis(sql, engine, geom_col="geom")

def insert_geodataframe(gdf: gpd.GeoDataFrame, table: str, db_url: str):
    """Insert a GeoDataFrame into a PostGIS table."""
    engine = get_engine(db_url)
    gdf.to_postgis(table, engine, if_exists="append", index=False)

# Example: find prospects near known deposits
def prospects_near_deposits(db_url: str, max_km: float = 25):
    sql = f"""
        SELECT p.*, d.name AS nearest_deposit, d.commodity,
               ST_Distance(p.geom::geography, d.geom::geography) / 1000 AS dist_km
        FROM prospects p
        CROSS JOIN LATERAL (
            SELECT name, commodity, geom
            FROM mining_sites
            ORDER BY p.geom::geography <-> geom::geography
            LIMIT 1
        ) d
        WHERE ST_DWithin(p.geom::geography, d.geom::geography, {max_km * 1000})
    """
    return query_spatial(db_url, sql)
```

**Where in AfriMine:** Primary data store. All spatial data (prospects, deposits, geological maps, concession boundaries, drill holes) lives in PostGIS. The REST API builds spatial queries on the fly. The `<->` operator (KNN) is critical for proximity features.

---

## C. REMOTE SENSING

### C1. Image Classification

**Supervised:** Train on labeled pixels (e.g., "this pixel = alteration," "this = vegetation"). Needs ground truth from field surveys or known deposits.

**Unsupervised:** Cluster pixels by spectral similarity without labels. Good for exploration when ground truth is scarce.

**How it translates to code:**
```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans, MiniBatchKMeans
import numpy as np
import rasterio

def supervised_classify(raster_path: str, training_points: gpd.GeoDataFrame,
                        label_col: str, out_path: str):
    """Supervised classification using Random Forest.
    
    training_points: GeoDataFrame with geometry + label column.
    """
    with rasterio.open(raster_path) as src:
        data = src.read()  # (n_bands, h, w)
        profile = src.profile.copy()
        transform = src.transform
    
    n_bands, h, w = data.shape
    
    # Extract pixel values at training points
    X_train, y_train = [], []
    for _, row in training_points.iterrows():
        col, row_idx = ~transform * (row.geometry.x, row.geometry.y)
        col, row_idx = int(col), int(row_idx)
        if 0 <= col < w and 0 <= row_idx < h:
            pixel_vals = data[:, row_idx, col]
            if not np.any(np.isnan(pixel_vals)):
                X_train.append(pixel_vals)
                y_train.append(row[label_col])
    
    X_train = np.array(X_train)
    
    # Train classifier
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    
    # Classify all pixels
    flat = data.reshape(n_bands, -1).T  # (n_pixels, n_bands)
    valid_mask = ~np.any(np.isnan(flat), axis=1)
    predictions = np.full(flat.shape[0], 255, dtype=np.uint8)
    predictions[valid_mask] = clf.predict(flat[valid_mask])
    result = predictions.reshape(h, w)
    
    profile.update(dtype="uint8", count=1, nodata=255)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(result, 1)
    
    return clf, result

def unsupervised_classify(raster_path: str, n_classes: int = 5, out_path: str = None):
    """Unsupervised classification using KMeans."""
    with rasterio.open(raster_path) as src:
        data = src.read()
        profile = src.profile.copy()
    
    n_bands, h, w = data.shape
    flat = data.reshape(n_bands, -1).T
    valid_mask = ~np.any(np.isnan(flat), axis=1) & np.all(flat != 0, axis=1)
    
    # Use MiniBatch for large rasters
    km = MiniBatchKMeans(n_clusters=n_classes, random_state=42, batch_size=10000)
    labels = np.full(flat.shape[0], 255, dtype=np.uint8)
    labels[valid_mask] = km.fit_predict(flat[valid_mask])
    result = labels.reshape(h, w)
    
    if out_path:
        profile.update(dtype="uint8", count=1, nodata=255)
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(result, 1)
    
    return km, result
```

**Where in AfriMine:** Land cover classification for masking (exclude vegetation/water before mineral mapping). Alteration zone classification. The unsupervised path is the default for new exploration areas; supervised is used when AfriMine has accumulated labeled training data from field campaigns.

---

### C2. Spectral Unmixing

A single pixel (e.g., 20m for Sentinel-11/12) may contain multiple materials. Spectral unmixing estimates the **fraction** of each mineral per pixel. This is more informative than hard classification.

**Linear Mixing Model:** `Pixel Spectrum = Σ (fraction_i × spectrum_i) + noise`

**How it translates to code:**
```python
import numpy as np
from sklearn.linear_model import NonNegativeLeastSquares

def spectral_unmixing(pixel_spectrum: np.ndarray, endmembers: np.ndarray) -> np.ndarray:
    """Unmix a single pixel into endmember fractions.
    
    Args:
        pixel_spectrum: (n_bands,) measured spectrum
        endmembers: (n_endmembers, n_bands) known mineral spectra
    
    Returns:
        fractions: (n_endmembers,) fraction of each endmember
    """
    # Constrained: fractions >= 0, sum <= 1
    nnls = NonNegativeLeastSquares()
    nnls.fit(endmembers.T, pixel_spectrum)
    fractions = nnls.coef_
    # Normalize to sum <= 1
    if fractions.sum() > 1:
        fractions /= fractions.sum()
    return fractions

def unmix_raster(raster_path: str, endmembers: np.ndarray, out_path: str):
    """Unmix an entire raster. Output: one band per endmember fraction."""
    with rasterio.open(raster_path) as src:
        data = src.read().astype(np.float32)  # (n_bands, h, w)
        profile = src.profile.copy()
    
    n_bands, h, w = data.shape
    n_endmembers = endmembers.shape[0]
    fractions = np.zeros((n_endmembers, h, w), dtype=np.float32)
    
    for i in range(h):
        for j in range(w):
            pixel = data[:, i, j]
            if not np.any(np.isnan(pixel)) and np.all(pixel > 0):
                fractions[:, i, j] = spectral_unmixing(pixel, endmembers)
    
    profile.update(dtype="float32", count=n_endmembers)
    with rasterio.open(out_path, "w", **profile) as dst:
        for b in range(n_endmembers):
            dst.write(fractions[b], b + 1)
    return fractions

# Endmember spectra (simplified — in practice, extract from USGS spectral library)
# These are approximate reflectance values for Sentinel-2 bands [B2,B3,B4,B5,B6,B7,B8,B8A,B11,B12]
ENDMEMBERS = {
    "kaolinite":  [0.05, 0.08, 0.12, 0.15, 0.18, 0.20, 0.22, 0.23, 0.18, 0.08],
    "hematite":   [0.03, 0.04, 0.15, 0.18, 0.12, 0.10, 0.10, 0.10, 0.12, 0.10],
    "vegetation": [0.04, 0.08, 0.05, 0.12, 0.25, 0.30, 0.35, 0.33, 0.15, 0.08],
    "soil":       [0.10, 0.12, 0.15, 0.18, 0.22, 0.25, 0.28, 0.27, 0.30, 0.25],
}
```

**Where in AfriMine:** Quantitative mineral mapping. Instead of "this area has clay," you get "this pixel is 40% kaolinite, 30% vegetation, 20% soil, 10% hematite." This feeds directly into prospectivity scoring.

---

### C3. Change Detection

Comparing satellite images from different dates to detect changes: new mining activity, vegetation loss, land disturbance, water contamination.

**How it translates to code:**
```python
import numpy as np
import rasterio

def change_detection_raster(path_before: str, path_after: str, out_path: str,
                            method: str = "difference"):
    """Detect changes between two rasters (same area, different dates).
    
    Methods:
        'difference': after - before (simple)
        'ratio': after / before
        'ndvi_change': NDVI difference
    """
    with rasterio.open(path_before) as b_src, \
         rasterio.open(path_after) as a_src:
        before = b_src.read(1).astype(np.float32)
        after = a_src.read(1).astype(np.float32)
        profile = b_src.profile.copy()
    
    if method == "difference":
        change = after - before
    elif method == "ratio":
        change = np.where(before > 0, after / before, 0)
    elif method == "ndvi_change":
        # Expects multi-band input: bands = [Red, NIR]
        before_ndvi = (before[1] - before[0]) / (before[1] + before[0] + 1e-10)
        after_ndvi = (after[1] - after[0]) / (after[1] + after[0] + 1e-10)
        change = after_ndvi - before_ndvi
    
    profile.update(dtype="float32")
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(change, 1)
    return change

def detect_new_activity(path_before: str, path_after: str,
                        ndvi_drop_threshold: float = -0.15) -> np.ndarray:
    """Detect areas with significant NDVI drop (potential new mining/excavation)."""
    # ... compute NDVI for both dates ...
    # Pixels where NDVI dropped significantly = potential disturbance
    pass
```

**Where in AfriMine:** Monitoring active mining concessions for unauthorized activity. Tracking rehabilitation progress. Detecting new artisanal mining sites. Time-series dashboards showing vegetation recovery or degradation.

---

### C4. Atmospheric Correction

Raw satellite radiance includes atmospheric effects (scattering, absorption). Correcting to surface reflectance is essential for comparing images across dates and for mineral mapping.

**Methods:**
- **Simplified Model (DOS1):** Dark object subtraction — assumes darkest pixel = atmospheric path radiance
- **6S / SMAC:** Physics-based radiative transfer models
- **Sen2Cor:** ESA's official Sentinel-2 L2A processor (most common for S2)

**How it translates to code:**
```python
# Option 1: Use sen2cor (command line, recommended for S2)
# Install: wget https://step.esa.int/main/snap-supported-plugins/sen2cor/
# Run: L2A_Process <S2_L1C_product>

# Option 2: Simple DOS1 correction in Python
def dos1_correction(radiance: np.ndarray, dark_percentile: float = 1.0) -> np.ndarray:
    """Dark Object Subtraction (DOS1) atmospheric correction.
    
    Subtracts the darkest pixel value (assumed = path radiance) from the image.
    """
    dark_value = np.percentile(radiance[radiance > 0], dark_percentile)
    corrected = radiance - dark_value
    corrected = np.clip(corrected, 0, None)
    return corrected

def apply_to_raster(raster_path: str, out_path: str):
    """Apply DOS1 to a GeoTIFF."""
    with rasterio.open(raster_path) as src:
        data = src.read(1).astype(np.float32)
        profile = src.profile.copy()
        
        corrected = dos1_correction(data)
        
        profile.update(dtype="float32")
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(corrected, 1)
```

**Where in AfriMine:** Data preprocessing pipeline. L2A (atmospherically corrected) Sentinel-2 data is preferred. DOS1 is a fallback for older L1C data. Proper correction is critical for quantitative mineral mapping — uncorrected data produces unreliable ratios.

---

## D. GEOSPATIAL ML

### D1. Spatial Autocorrelation (Moran's I)

**What it is:** Moran's I measures whether nearby locations have similar values (positive autocorrelation) or dissimilar values (negative). It quantifies the "spatial clustering" of a variable.

- I ≈ +1: clustered (similar values near each other)
- I ≈ 0: random
- I ≈ -1: dispersed

**Why it matters for ML:** If your data has spatial autocorrelation, random train/test splits give overly optimistic accuracy. You need spatial cross-validation.

**How it translates to code:**
```python
from libpysal.weights import Queen, KNN
from esda.moran import Moran
import numpy as np

def compute_morans_i(gdf, value_col: str, weight_type: str = "knn", k: int = 8) -> dict:
    """Compute Moran's I for a spatial variable.
    
    Args:
        gdf: GeoDataFrame with geometry and value column
        value_col: column to test for spatial autocorrelation
        weight_type: 'knn' (k-nearest) or 'queen' (contiguity)
        k: number of neighbors for KNN
    """
    if weight_type == "knn":
        w = KNN.from_dataframe(gdf, k=k)
    else:
        w = Queen.from_dataframe(gdf)
    
    w.transform = "r"  # row-standardize
    
    y = gdf[value_col].values
    mi = Moran(y, w)
    
    return {
        "I": mi.I,
        "p_value": mi.p_sim,
        "z_score": mi.z_sim,
        "significant": mi.p_sim < 0.05,
        "interpretation": "clustered" if mi.I > 0 and mi.p_sim < 0.05
                          else "dispersed" if mi.I < 0 and mi.p_sim < 0.05
                          else "random"
    }

# Example usage
# result = compute_morans_i(prospects_gdf, "gold_grade")
# print(f"Moran's I = {result['I']:.3f}, p = {result['p_value']:.3f}")
# → Moran's I = 0.45, p = 0.001 → "clustered"
```

**Where in AfriMine:** Pre-ML diagnostic. Before building grade prediction models, check if grades are spatially autocorrelated. If yes (they almost always are in mining data), use spatial cross-validation. Also used to validate prospectivity maps — if high-probability areas are randomly scattered, the model may be wrong.

---

### D2. Variograms

A variogram plots how the variance between two points changes with distance. It reveals:
- **Nugget:** variance at zero distance (measurement error / micro-variability)
- **Sill:** maximum variance (total spatial variance)
- **Range:** distance at which spatial correlation disappears

**Why it matters:** Variograms are the foundation of kriging and tell you the spatial scale of geological processes.

**How it translates to code:**
```python
import numpy as np
from skgstat import Variogram

def fit_variogram(coords: np.ndarray, values: np.ndarray,
                  model: str = "spherical", n_lags: int = 15) -> dict:
    """Fit an experimental variogram and return parameters.
    
    Args:
        coords: (n, 2) array of x, y coordinates (in projected CRS!)
        values: (n,) array of measured values (e.g., grade)
        model: 'spherical', 'exponential', 'gaussian'
        n_lags: number of distance bins
    """
    V = Variogram(coords, values, model=model, n_lags=n_lags)
    
    return {
        "nugget": V.parameters[0],
        "sill": V.parameters[1],
        "range": V.parameters[2],
        "model": model,
        "variogram_object": V,
    }

def plot_variogram(V, out_path: str = "variogram.png"):
    """Plot experimental variogram with fitted model."""
    import matplotlib.pyplot as plt
    fig = V.plot()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()

# Example
# coords = drill_holes_gdf[["easting", "northing"]].values  # must be in meters (UTM)
# values = drill_holes_gdf["gold_grade"].values
# vparams = fit_variogram(coords, values, model="spherical")
# print(f"Range: {vparams['range']:.0f}m, Sill: {vparams['sill']:.3f}, Nugget: {vparams['nugget']:.3f}")
```

**Where in AfriMine:** Grade estimation / resource modeling. Variograms characterize the spatial continuity of mineralization at each deposit. They parameterize kriging for block model construction. The range tells geologists how far apart drill holes can be while still capturing grade trends.

---

### D3. Spatial Cross-Validation

Standard k-fold CV assumes i.i.d. data. Spatial data violates this — nearby points are correlated, so random folds leak spatial information. Spatial CV uses geographic blocking to prevent data leakage.

**Methods:**
- **Spatial Blocking:** Split by geographic blocks (grid cells)
- **Buffered Leave-One-Out:** Exclude a buffer around each test point
- **Cluster-based:** Use spatial clusters as folds

**How it translates to code:**
```python
from sklearn.model_selection import cross_val_score
from sklearn.ensemble import RandomForestRegressor
import numpy as np

def spatial_blocked_cv(gdf, features: list[str], target: str,
                       n_splits: int = 5, block_size: float = 10000):
    """Spatial cross-validation using geographic blocks.
    
    Args:
        gdf: GeoDataFrame (must be in projected CRS, e.g., UTM)
        features: feature column names
        target: target column name
        n_splits: number of folds
        block_size: block size in map units (meters)
    """
    from sklearn.model_selection import KFold
    
    coords = np.array([[g.centroid.x, g.centroid.y] for g in gdf.geometry])
    
    # Assign points to grid blocks
    block_x = (coords[:, 0] / block_size).astype(int)
    block_y = (coords[:, 1] / block_size).astype(int)
    block_ids = block_x * 10000 + block_y  # unique block ID
    unique_blocks = np.unique(block_ids)
    
    # K-fold on blocks (not points!)
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    
    X = gdf[features].values
    y = gdf[target].values
    
    scores = []
    for train_blocks, test_blocks in kf.split(unique_blocks):
        train_mask = np.isin(block_ids, unique_blocks[train_blocks])
        test_mask = np.isin(block_ids, unique_blocks[test_blocks])
        
        X_train, X_test = X[train_mask], X[test_mask]
        y_train, y_test = y[train_mask], y[test_mask]
        
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)
        score = model.score(X_test, y_test)
        scores.append(score)
    
    return {
        "scores": scores,
        "mean": np.mean(scores),
        "std": np.std(scores),
        "non_spatial_comparison": cross_val_score(
            RandomForestRegressor(n_estimators=100, random_state=42),
            X, y, cv=n_splits
        ).mean()
    }

# Typical output: spatial CV R² = 0.45 vs non-spatial R² = 0.78
# → non-spatial overestimates by 0.33 due to spatial leakage
```

**Where in AfriMine:** Every ML model evaluation. This is non-negotiable for prospectivity models. Non-spatial CV gives inflated accuracy that doesn't generalize to new areas. Spatial CV shows true predictive power.

---

### D4. Kriging (Spatial Interpolation)

Kriging uses the variogram to optimally interpolate values at unmeasured locations. It provides both an estimate and an uncertainty (kriging variance).

**Types:**
- **Ordinary Kriging:** Assumes constant unknown mean (most common)
- **Universal Kriging:** Models a spatial trend + residual kriging
- **Indicator Kriging:** Interpolates binary variables (above/below cutoff)

**How it translates to code:**
```python
from pykrige.ok import OrdinaryKriging
import numpy as np

def kriging_interpolation(coords: np.ndarray, values: np.ndarray,
                          grid_x: np.ndarray, grid_y: np.ndarray,
                          variogram_model: str = "spherical") -> dict:
    """Ordinary Kriging interpolation on a regular grid.
    
    Args:
        coords: (n, 2) x,y coordinates in projected CRS
        values: (n,) measured values
        grid_x, grid_y: 1D arrays defining the output grid
        variogram_model: 'linear', 'power', 'gaussian', 'spherical', 'exponential'
    
    Returns:
        dict with 'estimate' and 'variance' grids
    """
    ok = OrdinaryKriging(
        coords[:, 0], coords[:, 1], values,
        variogram_model=variogram_model,
        verbose=True, enable_plotting=False,
    )
    
    z, ss = ok.execute("grid", grid_x, grid_y)
    
    return {
        "estimate": z,       # interpolated values
        "variance": ss,      # kriging variance (uncertainty)
        "grid_x": grid_x,
        "grid_y": grid_y,
    }

def kriging_from_geodataframe(gdf, value_col: str, resolution: float = 50):
    """Kriging interpolation from a GeoDataFrame of sample points."""
    # Must be in projected CRS
    coords = np.array([[g.x, g.y] for g in gdf.geometry])
    values = gdf[value_col].values
    
    # Create regular grid
    x_min, y_min = coords.min(axis=0) - resolution
    x_max, y_max = coords.max(axis=0) + resolution
    grid_x = np.arange(x_min, x_max, resolution)
    grid_y = np.arange(y_min, y_max, resolution)
    
    return kriging_interpolation(coords, values, grid_x, grid_y)

# Example: interpolate gold grades from drill holes
# result = kriging_from_geodataframe(drill_holes, "au_ppm", resolution=25)
# Save estimate as GeoTIFF
```

**Where in AfriMine:** Resource estimation — interpolating grade between drill holes to build block models. Uncertainty maps (kriging variance) identify areas needing more drilling. Also used for geophysical data interpolation (magnetic, radiometric).

---

## E. FREE TOOLS & APIs

### E1. Google Earth Engine (GEE)

A cloud platform with petabytes of satellite imagery and geospatial datasets. No download required — computation runs on Google's servers.

**Key capabilities for AfriMine:**
- Access Sentinel-2, Landsat, MODIS archives
- Built-in spectral indices, classification, time-series analysis
- Scale: process entire continents without local compute
- Python API (`earthengine-api`)

**How it translates to code:**
```python
import ee

# Initialize (requires authentication: `earthengine authenticate`)
ee.Initialize()

# Load Sentinel-2 surface reflectance collection
def get_s2_collection(aoi_coords: list, start_date: str, end_date: str,
                      cloud_cover_max: float = 20) -> ee.ImageCollection:
    """Get cloud-masked Sentinel-2 composite for an area of interest.
    
    Args:
        aoi_coords: [[lon,lat], [lon,lat], ...] polygon coordinates
        start_date, end_date: date range (YYYY-MM-DD)
        cloud_cover_max: max cloud cover percentage
    """
    aoi = ee.Geometry.Polygon(aoi_coords)
    
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_cover_max))
    )
    
    # Cloud masking function
    def mask_clouds(image):
        qa = image.select("QA60")
        cloud_mask = qa.bitwiseAnd(1 << 10).eq(0)  # cloud bit
        cirrus_mask = qa.bitwiseAnd(1 << 11).eq(0)  # cirrus bit
        return image.updateMask(cloud_mask.And(cirrus_mask))
    
    collection = collection.map(mask_clouds)
    
    # Create median composite
    composite = collection.median().clip(aoi)
    return composite

def compute_mineral_indices(image: ee.Image) -> ee.Image:
    """Compute mineral ratio bands on a GEE image."""
    iron = image.select("B4").divide(image.select("B2")).rename("iron_ratio")
    clay = image.select("B11").divide(image.select("B12")).rename("clay_ratio")
    chlorite = image.select("B8A").divide(image.select("B11")).rename("chlorite_ratio")
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    
    return image.addBands([iron, clay, chlorite, ndvi])

def export_to_geotiff(image: ee.Image, region: ee.Geometry, filename: str,
                      scale: int = 20, crs: str = "EPSG:4326"):
    """Export a GEE image to Google Drive as GeoTIFF."""
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=filename,
        folder="AfriMine",
        region=region,
        scale=scale,
        crs=crs,
        maxPixels=1e13,
    )
    task.start()
    return task

# Example workflow: mineral mapping for a prospect
# aoi = [[29.5, 2.5], [30.5, 2.5], [30.5, 3.5], [29.5, 3.5]]
# composite = get_s2_collection(aoi, "2023-01-01", "2023-12-31")
# enriched = compute_mineral_indices(composite)
# export_to_geotiff(enriched, ee.Geometry.Polygon(aoi), "kibali_mineral_ratios")
```

**Where in AfriMine:** Continental-scale prospectivity screening. Process all of West Africa or the DRC copper belt in one script. Generate mineral ratio composites without downloading terabytes of data. Also used for time-series analysis (NDVI trends over mining concessions).

---

### E2. QGIS (Programmatic Operations)

QGIS has a Python API (PyQGIS) for automating geoprocessing workflows.

**How it translates to code:**
```python
# QGIS Python console or standalone script
import sys
sys.path.append("/usr/share/qgis/python")  # adjust for your install

from qgis.core import (
    QgsApplication, QgsVectorLayer, QgsRasterLayer,
    QgsProcessingFeedback, QgsProject
)

def init_qgis():
    """Initialize QGIS application (standalone mode)."""
    qgs = QgsApplication([], False)
    qgs.initQgis()
    return qgs

def run_processing_algorithm(algorithm: str, params: dict) -> dict:
    """Run a QGIS processing algorithm."""
    import processing
    feedback = QgsProcessingFeedback()
    result = processing.run(algorithm, params, feedback=feedback)
    return result

# Example: clip raster by polygon
def clip_raster(raster_path: str, mask_path: str, out_path: str):
    result = run_processing_algorithm("gdal:cliprasterbymasklayer", {
        "INPUT": raster_path,
        "MASK": mask_path,
        "OUTPUT": out_path,
    })
    return result

# Example: vector intersection
def intersect_layers(layer_a_path: str, layer_b_path: str, out_path: str):
    result = run_processing_algorithm("native:intersection", {
        "INPUT": layer_a_path,
        "OVERLAY": layer_b_path,
        "OUTPUT": out_path,
    })
    return result
```

**Where in AfriMine:** Rapid prototyping of spatial workflows. Batch processing legacy Shapefiles. QGIS modeler exports can be converted to Python scripts for the pipeline. Also used by geologists for interactive analysis — AfriMine can export layers for QGIS review.

---

### E3. GDAL / Rasterio (Python for Satellite Data)

GDAL is the foundational library for raster/vector I/O. Rasterio is a Pythonic wrapper around GDAL for raster operations.

**How it translates to code:**
```python
import rasterio
from rasterio.warp import reproject, Resampling, calculate_default_transform
from rasterio.mask import mask as rasterio_mask
from rasterio.merge import merge
import numpy as np

# --- Reprojection ---
def reproject_raster(src_path: str, dst_path: str, dst_crs: str = "EPSG:32736"):
    """Reproject a raster to a new CRS."""
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )
        profile = src.profile.copy()
        profile.update(crs=dst_crs, transform=transform, width=width, height=height)
        
        with rasterio.open(dst_path, "w", **profile) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_crs=src.crs,
                    dst_crs=dst_crs,
                    resampling=Resampling.nearest,
                )

# --- Clip by polygon ---
def clip_raster_by_polygon(raster_path: str, polygon_gdf, out_path: str):
    """Clip a raster to a polygon boundary."""
    with rasterio.open(raster_path) as src:
        out_image, out_transform = rasterio_mask(
            src, polygon_gdf.geometry, crop=True, nodata=0
        )
        profile = src.profile.copy()
        profile.update(
            height=out_image.shape[1],
            width=out_image.shape[2],
            transform=out_transform,
        )
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(out_image)

# --- Mosaic multiple rasters ---
def mosaic_rasters(raster_paths: list[str], out_path: str):
    """Merge multiple rasters into a single mosaic."""
    src_files = [rasterio.open(p) for p in raster_paths]
    mosaic, transform = merge(src_files)
    profile = src_files[0].profile.copy()
    profile.update(height=mosaic.shape[1], width=mosaic.shape[2], transform=transform)
    
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(mosaic)
    for src in src_files:
        src.close()

# --- Statistics ---
def raster_stats(raster_path: str) -> dict:
    """Compute basic statistics for a raster."""
    with rasterio.open(raster_path) as src:
        data = src.read(1).astype(np.float32)
        nodata = src.nodata
        if nodata is not None:
            data = data[data != nodata]
        return {
            "min": float(np.nanmin(data)),
            "max": float(np.nanmax(data)),
            "mean": float(np.nanmean(data)),
            "std": float(np.nanstd(data)),
            "count": int(data.size),
        }
```

**Where in AfriMine:** Core data processing library. Every raster operation — band stacking, reprojection, clipping, mosaicking, statistics — goes through rasterio/GDAL. This is the workhorse of the satellite data pipeline.

---

### E4. Microsoft Planetary Computer

Free cloud platform providing STAC (SpatioTemporal Asset Catalog) access to Sentinel-2, Landsat, DEMs, and more. Data is hosted on Azure Blob Storage and accessible via HTTP.

**How it translates to code:**
```python
import pystac_client
import planetary_computer
import rasterio
from rasterio.session import AzureSession

def search_sentinel2(aoi: dict, date_range: str, cloud_cover: int = 20) -> list:
    """Search Planetary Computer for Sentinel-2 scenes.
    
    Args:
        aoi: GeoJSON geometry dict
        date_range: "2023-01-01/2023-12-31"
        cloud_cover: max cloud percentage
    """
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        intersects=aoi,
        datetime=date_range,
        query={"eo:cloud_cover": {"lt": cloud_cover}},
    )
    
    items = search.item_collection()
    return items

def download_bands(item, bands: list[str], out_dir: str):
    """Download specific bands from a STAC item."""
    import urllib.request
    import os
    os.makedirs(out_dir, exist_ok=True)
    
    for band_name in bands:
        asset = item.assets[band_name]
        url = asset.href  # already signed by planetary_computer.sign_inplace
        out_path = os.path.join(out_dir, f"{band_name}.tif")
        urllib.request.urlretrieve(url, out_path)
    return out_dir

def stack_from_stac(item, bands: list[str], out_path: str):
    """Stack bands directly from STAC URLs without downloading."""
    # Rasterio can read signed URLs directly
    import rasterio
    from rasterio.merge import merge
    
    srcs = [rasterio.open(item.assets[b].href) for b in bands]
    profile = srcs[0].profile.copy()
    profile.update(count=len(bands))
    
    with rasterio.open(out_path, "w", **profile) as dst:
        for i, src in enumerate(srcs, 1):
            dst.write(src.read(1), i)
            src.close()

# Example: search and process
# aoi = {"type": "Polygon", "coordinates": [[[29.5,2.5],[30.5,2.5],[30.5,3.5],[29.5,3.5],[29.5,2.5]]]}
# items = search_sentinel2(aoi, "2023-06-01/2023-08-31", cloud_cover=10)
# stack_from_stac(items[0], ["B02","B03","B04","B08","B11","B12"], "composite.tif")
```

**Where in AfriMine:** Alternative to GEE for satellite data access. Preferable when you need direct file access (not server-side computation). Azure colocation means fast access if AfriMine runs on Azure. STAC catalog makes it easy to search by location, date, and cloud cover programmatically.

---

## QUICK REFERENCE: Common Workflows

### Workflow 1: Mineral Prospectivity Mapping
```
1. Search Planetary Computer / GEE for Sentinel-2 over AOI
2. Load bands (B2, B3, B4, B8, B8A, B11, B12) via rasterio
3. Atmospheric correction (Sen2Cor L2A preferred)
4. Compute mineral ratios (iron, clay, chlorite)
5. Compute NDVI
6. Stack ratios + NDVI as features
7. Classify alteration zones (KMeans or RF with labeled data)
8. Combine with geological/geophysical layers in PostGIS
9. Train prospectivity model with spatial CV
10. Generate probability map → drill target ranking
```

### Workflow 2: Mining Activity Monitoring
```
1. Download Sentinel-2 time series (monthly composites)
2. Compute NDVI for each date
3. Run change detection (NDVI trend analysis)
4. Flag significant drops (>0.15 decrease)
5. Cross-reference with concession boundaries (PostGIS)
6. Alert on unauthorized activity outside permitted areas
```

### Workflow 3: Resource Estimation
```
1. Load drill hole data into PostGIS
2. Exploratory data analysis (histograms, trend surfaces)
3. Compute variogram (check anisotropy)
4. Fit variogram model (spherical/exponential)
5. Run kriging interpolation → grade surface + variance
6. Classify blocks by confidence (high/medium/low)
7. Generate block model for mine planning
```

---

## DEPENDENCIES

```bash
pip install rasterio[rasterio] geopandas shapely pyproj \
    scikit-learn scikit-gstat pykrige \
    pystac-client planetary-computer \
    rtree libpysal esda \
    earthengine-api \
    sqlalchemy psycopg2-binary
```
