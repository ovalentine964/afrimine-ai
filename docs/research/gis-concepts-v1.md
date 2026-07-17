# AfriMine AI — GIS & Remote Sensing Engineering Reference

> **Purpose:** Extract spatial analysis concepts as software specifications. Each concept is an "API endpoint" — what it does, what goes in, what comes out, and how to implement it.

---

## A. SATELLITE IMAGERY

### A1. Sentinel-2 Spectral Bands

**What it is:** Sentinel-2 captures 13 spectral bands per pixel — each band measures a specific wavelength range of reflected light. Different minerals absorb/reflect light differently at different wavelengths, making them identifiable.

**How it translates to CODE:**

| Band | Name | Resolution | Center λ | What It Detects | Mining Relevance |
|------|------|-----------|----------|-----------------|------------------|
| B1 | Coastal aerosol | 60m | 443nm | Aerosols, shallow water | Atmospheric correction |
| B2 | Blue | 10m | 490nm | Water, iron oxide baseline | Iron ratio denominator |
| B3 | Green | 10m | 560nm | Vegetation health | NDVI component |
| B4 | Red | 10m | 665nm | Iron oxide absorption | Iron ratio numerator |
| B5 | Red Edge 1 | 20m | 705nm | Vegetation red edge | Chlorophyll stress |
| B6 | Red Edge 2 | 20m | 740nm | Vegetation red edge | Canopy structure |
| B7 | Red Edge 3 | 20m | 783nm | Vegetation red edge | Biomass estimation |
| B8 | NIR | 10m | 842nm | Vegetation, moisture | NDVI component |
| B8A | NIR Narrow | 20m | 865nm | Water vapour | Atmospheric correction |
| B9 | Water vapour | 60m | 940nm | Water vapour | Atmospheric correction |
| B10 | SWIR - Cirrus | 60m | 1375nm | Cirrus clouds | Cloud masking |
| B11 | SWIR 1 | 20m | 610nm | Clay, minerals | Clay/alteration detection |
| B12 | SWIR 2 | 20m | 2190nm | Minerals, soil | Sulphate/carbonate detection |

**Data format:** Each band is a separate raster layer (GeoTIFF, 16-bit unsigned integer, DN values 0–10000). Sentinel-2 L2A products are surface reflectance (already atmospherically corrected).

**Python implementation:**
```python
import rasterio

def load_sentinel2_bands(product_path, bands=['B02','B03','B04','B08','B11','B12']):
    """Load Sentinel-2 bands from unzipped product directory."""
    band_data = {}
    for band in bands:
        # S2 L2A structure: R10m/, R20m/, R60m/ subdirectories
        res_dir = {'B02':'R10m','B03':'R10m','B04':'R10m','B08':'R10m',
                   'B11':'R20m','B12':'R20m'}
        path = f"{product_path}/{res_dir[band]}/{band}.jp2"
        with rasterio.open(path) as src:
            band_data[band] = src.read(1).astype('float32')
    return band_data

# Endpoint specification
# INPUT: Path to unzipped Sentinel-2 L2A product
# OUTPUT: Dict[str, np.ndarray] — band name → 2D array of reflectance values
# FORMAT: float32, range 0.0–1.0 (after dividing by 10000)
```

---

### A2. Band Ratios for Mineral Detection

**What it is:** Dividing one band by another normalizes illumination and highlights specific mineral signatures. Minerals have diagnostic absorption features at known wavelengths.

**How it translates to CODE:**

```python
import numpy as np

def iron_oxide_ratio(b4, b2):
    """
    Iron Oxide Index (IOI) = B4 / B2
    Iron oxides (hematite, goethite) absorb in blue, reflect in red.
    High values → iron-rich surface.
    """
    ratio = np.where(b2 > 0, b4 / b2, 0)
    return ratio

def clay_mineral_ratio(b11, b12):
    """
    Clay Mineral Index (CMI) = B11 / B12
    Clay minerals (kaolinite, illite) absorb in SWIR2, reflect in SWIR1.
    High values → clay alteration zones (hydrothermal indicator).
    """
    ratio = np.where(b12 > 0, b11 / b12, 0)
    return ratio

def ferrous_iron_ratio(b4, b2):
    """
    Ferrous Iron Index = (B4 - B2) / (B4 + B2)
    Similar to IOI but normalized to [-1, 1].
    """
    denominator = b4 + b2
    return np.where(denominator > 0, (b4 - b2) / denominator, 0)

def silica_index(b11, b12):
    """
    Silica Richness = B11 / B12
    High silica content → potential indicator of silicification (mineralization).
    Same formula as clay ratio — context determines interpretation.
    """
    return np.where(b12 > 0, b11 / b12, 0)

# ENDPOINT
# INPUT: Two np.ndarray (same shape) of surface reflectance
# OUTPUT: np.ndarray (same shape), float32, ratio values
# TYPICAL THRESHOLDS:
#   IOI > 1.5 → strong iron oxide presence
#   CMI > 1.2 → clay alteration zone
```

**Where in the platform:** Mineral prospectivity mapping pipeline. Takes preprocessed Sentinel-2 L2A bands, produces ratio layers that feed into the ML classification model.

---

### A3. NDVI (Normalized Difference Vegetation Index)

**What it is:** NDVI = (NIR - Red) / (NIR + Red). Healthy vegetation reflects strongly in NIR and absorbs in Red. Low NDVI in vegetated areas can indicate subsurface mineralization causing vegetation stress (a concept called "vegetation anomaly" in biogeochemical exploration).

**How it translates to CODE:**

```python
def ndvi(nir_band, red_band):
    """
    NDVI = (B08 - B04) / (B08 + B04)
    Range: -1 to +1
    < 0.1  → bare soil, water, rock
    0.1–0.3 → sparse vegetation
    0.3–0.6 → moderate vegetation
    > 0.6 → dense vegetation
    
    Mining use: Look for NDVI *anomalies* — patches where NDVI is
    significantly lower than surrounding area (vegetation stress
    over buried mineralization).
    """
    denominator = (nir_band + red_band).astype('float32')
    return np.where(denominator > 0, 
                    (nir_band - red_band) / denominator, 
                    0).astype('float32')

def ndvi_anomaly_detection(ndvi_image, window_size=51, threshold_std=2.0):
    """
    Detect local NDVI anomalies — pixels significantly lower than neighborhood.
    Indicates potential vegetation stress from subsurface minerals.
    """
    from scipy.ndimage import uniform_filter
    local_mean = uniform_filter(ndvi_image, size=window_size)
    local_sq_mean = uniform_filter(ndvi_image**2, size=window_size)
    local_std = np.sqrt(np.maximum(local_sq_mean - local_mean**2, 0))
    
    # Anomaly: NDVI more than threshold_std standard deviations below local mean
    anomaly = (ndvi_image < (local_mean - threshold_std * local_std)).astype('uint8')
    return anomaly

# ENDPOINT
# INPUT: np.ndarray NIR band (B08), np.ndarray Red band (B04), both float32 reflectance
# OUTPUT: np.ndarray float32 [-1, 1], same shape as input
# FORMAT: GeoTIFF, same CRS and extent as source imagery
```

**Where in the platform:** Biogeochemical exploration module. Flags vegetation stress zones as indirect mineralization indicators, especially in tropical/subtropical African regions with lateritic cover.

---

### A4. Alteration Mapping from Satellite

**What it is:** Hydrothermal alteration (hot fluids from mineralizing systems) changes the mineralogy of surrounding rock, creating detectable spectral signatures: argillic alteration (clays), phyllic alteration (sericite), propylitic alteration (chlorite, epidote), and silicification.

**How it translates to CODE:**

```python
def alteration_mapping(b2, b3, b4, b5, b6, b7, b8, b11, b12):
    """
    Multi-band alteration detection using spectral indices.
    Returns dict of alteration indicator layers.
    """
    results = {}
    
    # 1. Argillic Alteration (kaolinite + alunite)
    #    Strong absorption in B12, reflectance in B11
    #    Also uses B4/B2 (iron association)
    results['argillic'] = {
        'clay_index': np.where(b12 > 0, b11 / b12, 0),  # B11/B12 > 1.2
        'alunite_index': np.where(b4 > 0, b11 / b4, 0),  # Alunite: bright in B11
    }
    
    # 2. Phyllic Alteration (sericite/muscovite)
    #    Absorption features at ~2200nm (B12), reflectance at ~2100nm (B11)
    results['phyllic'] = {
        'sericite_index': np.where(b12 > 0, b11 / b12, 0),
    }
    
    # 3. Propylitic Alteration (chlorite + epidote)
    #    Moderate absorption in B11, higher reflectance in B12 relative to B11
    results['propyllic'] = {
        'chlorite_index': np.where(b11 > 0, b12 / b11, 0),  # Inverse of clay
    }
    
    # 4. Iron Oxide / Gossan
    #    Hematite/goethite: high B4/B2
    results['iron_oxide'] = {
        'hematite_index': np.where(b2 > 0, b4 / b2, 0),
        'goethite_index': np.where(b3 > 0, b4 / b3, 0),  # Slightly different signature
    }
    
    # 5. Silicification
    #    High reflectance across SWIR, low absorption features
    results['silica'] = {
        'quartz_index': np.where(b12 > 0, b11 / b12, 0),  # Context-dependent
    }
    
    # 6. Composite alteration map (normalized combination)
    clay_norm = _normalize(results['argillic']['clay_index'])
    iron_norm = _normalize(results['iron_oxide']['hematite_index'])
    results['composite'] = 0.5 * clay_norm + 0.5 * iron_norm
    
    return results

def _normalize(arr):
    """Min-max normalize to [0, 1]."""
    mn, mx = arr.min(), arr.max()
    return (arr - mn) / (mx - mn) if mx > mn else np.zeros_like(arr)

# ENDPOINT
# INPUT: 9 Sentinel-2 bands (B02-B12), float32 reflectance arrays
# OUTPUT: Dict[str, Dict[str, np.ndarray]] — alteration type → index name → raster
# FORMAT: GeoTIFF, 20m resolution (resample 10m bands to 20m first)
```

**Where in the platform:** Prospectivity mapping pipeline. Produces alteration layers as features for the ML mineral targeting model. Each alteration type corresponds to different mineral systems (porphyry Cu-Au, epithermal Au, VMS, etc.).

---

### A5. Spatial Resolution

**What it is:** Sentinel-2's 10m resolution means each pixel covers a 10×10m area on the ground. This determines what you can and cannot detect.

**How it translates to CODE / Platform Design:**

```python
# Resolution implications for AfriMine AI

RESOLUTION_LIMITS = {
    'sentinel2_10m': {
        'min_detectable_feature': '30-50m (3-5 pixels for reliable detection)',
        'what_you_see': [
            'Large open pits',
            'Tailings dams',
            'Major roads',
            'Large buildings',
            'Vegetation clearings',
            'River courses',
            'Large alteration zones (>100m)',
        ],
        'what_you_cant_see': [
            'Individual drill holes',
            'Small outcrops',
            'Narrow veins',
            'Individual vehicles',
            'Small test pits',
            'Rock samples',
        ],
        'mineral_mapping_use': 'Regional prospectivity, alteration halos, land cover',
    },
    'sentinel2_20m': {
        'bands': ['B05','B06','B07','B8A','B11','B12'],
        'min_detectable_feature': '60-100m',
        'mineral_mapping_use': 'Spectral ratios for clay/iron detection',
    },
    'planetscope_3m': {  # Commercial alternative
        'what_you_gain': 'Individual buildings, small pits, vehicle tracking',
        'use_case': 'Detailed site monitoring, illegal mining detection',
    },
    'maxar_30cm': {  # Very high resolution
        'what_you_gain': 'Individual people, vehicles, equipment',
        'use_case': 'Inspection, compliance monitoring',
    },
}

# When combining data at different resolutions, resample to coarsest:
def harmonize_resolution(data_dict, target_resolution='20m'):
    """Resample all layers to common resolution using bilinear interpolation."""
    # Implementation uses rasterio.warp.reproject
    pass

# ENDPOINT
# INPUT: Raster layer, target resolution
# OUTPUT: Resampled raster (bilinear for continuous, nearest for categorical)
# FORMAT: GeoTIFF with updated affine transform
```

---

## B. SPATIAL DATA FORMATS

### B1. GeoTIFF

**What it is:** A TIFF image file with embedded geospatial metadata — coordinate reference system (CRS), pixel size, and geographic extent. The standard format for raster satellite data.

**How it translates to CODE:**

```python
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS

def create_geotiff(data, output_path, crs, transform, dtype='float32'):
    """
    Create a GeoTIFF from a numpy array.
    
    Args:
        data: np.ndarray, shape (height, width) or (bands, height, width)
        output_path: str, e.g., 'output/ndvi_map.tif'
        crs: rasterio CRS object, e.g., CRS.from_epsg(32636) for UTM 36N
        transform: Affine transform (pixel size, rotation, origin)
        dtype: 'float32', 'uint8', 'uint16', 'int16'
    """
    if data.ndim == 2:
        data = data[np.newaxis, ...]  # Add band dimension
    
    with rasterio.open(
        output_path, 'w',
        driver='GTiff',
        height=data.shape[1],
        width=data.shape[2],
        count=data.shape[0],
        dtype=dtype,
        crs=crs,
        transform=transform,
        compress='lzw',  # Lossless compression
        tiled=True,       # For efficient partial reads
        blockxsize=256,
        blockysize=256,
    ) as dst:
        dst.write(data)

def read_geotiff_extent(path):
    """Read metadata without loading full array."""
    with rasterio.open(path) as src:
        return {
            'bounds': src.bounds,       # (left, bottom, right, top)
            'shape': (src.height, src.width),
            'crs': src.crs.to_epsg(),
            'resolution': (src.res[0], src.res[1]),
            'bands': src.count,
            'dtype': str(src.dtypes[0]),
            'transform': src.transform,
            'nodata': src.nodata,
        }

# ENDPOINT
# INPUT: np.ndarray + metadata (CRS, transform, path)
# OUTPUT: .tif file on disk, readable by any GIS software
# FORMAT: GeoTIFF with LZW compression, tiled layout
# TYPICAL SIZE: ~100MB for a 10,000×10,000 pixel scene at float32
```

---

### B2. Shapefile & GeoJSON

**What it is:** Vector formats for discrete geographic features — sample points, claim boundaries, fault lines. Shapefile is legacy (multiple files); GeoJSON is modern (single JSON file, web-friendly).

**How it translates to CODE:**

```python
import geopandas as gpd
import json
from shapely.geometry import Point, Polygon, LineString

def create_sample_points(samples_df, lon_col='longitude', lat_col='latitude', 
                         crs_epsg=4326, output_path='samples.geojson'):
    """
    Convert a DataFrame of samples to GeoJSON.
    
    INPUT: DataFrame with lon, lat columns + attributes (grade, element, date)
    OUTPUT: GeoJSON FeatureCollection
    """
    geometry = [Point(xy) for xy in zip(samples_df[lon_col], samples_df[lat_col])]
    gdf = gpd.GeoDataFrame(samples_df, geometry=geometry, crs=f'EPSG:{crs_epsg}')
    gdf.to_file(output_path, driver='GeoJSON')
    return gdf

def create_claim_boundary(polygon_coords, claim_id, crs_epsg=4326):
    """
    Create a mining claim boundary polygon.
    
    INPUT: List of (lon, lat) tuples forming closed ring, claim ID
    OUTPUT: GeoJSON Feature with properties
    """
    poly = Polygon(polygon_coords)
    gdf = gpd.GeoDataFrame({
        'claim_id': [claim_id],
        'geometry': [poly],
        'area_sqkm': [poly.area * 111.32**2],  # Rough conversion at equator
    }, crs=f'EPSG:{crs_epsg}')
    return gdf

# GeoJSON structure (what the frontend receives):
SAMPLE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [36.8219, -1.2921]},
        "properties": {
            "sample_id": "KSM-001",
            "gold_ppb": 450,
            "rock_type": "andesite",
            "alteration": "argillic",
            "date_collected": "2025-03-15"
        }
    }]
}

# ENDPOINT
# INPUT: Tabular data with spatial coordinates + attributes
# OUTPUT: .geojson or .shp file, or GeoDataFrame in memory
# FORMAT: GeoJSON (web API), Shapefile (QGIS interop), GeoPackage (modern alternative)
# EPSG:4326 (WGS84) for web display; EPSG:326XX (UTM) for distance calculations
```

---

### B3. Coordinate Reference Systems (CRS)

**What it is:** A CRS defines how 3D Earth maps to 2D coordinates. WGS84 (EPSG:4326) is GPS standard (degrees). UTM zones are metric (meters) — essential for distance/area calculations.

**How it translates to CODE:**

```python
from pyproj import Transformer, CRS
import numpy as np

# Key CRS for African mining
CRS_REGISTRY = {
    'WGS84': 'EPSG:4326',           # GPS, lat/lon in degrees — WEB DISPLAY
    'UTM_36N': 'EPSG:32636',        # Tanzania, Kenya — METRIC CALCULATIONS
    'UTM_35S': 'EPSG:32735',        # South Africa, Zimbabwe
    'UTM_34S': 'EPSG:32734',        # Zambia, DRC (south)
    'UTM_33N': 'EPSG:32633',        # Egypt, Libya
    'UTM_36S': 'EPSG:32736',        # Tanzania (southern)
    'Arc_1960': 'EPSG:4210',        # Legacy East Africa datum
    'Hartebeesthoek94': 'EPSG:4148', # South Africa datum
}

def get_utm_zone(longitude):
    """Calculate UTM zone number from longitude."""
    return int((longitude + 180) / 6) + 1

def auto_utm_crs(longitude, latitude):
    """Automatically determine the correct UTM CRS for a location."""
    zone = get_utm_zone(longitude)
    hemisphere = 'north' if latitude >= 0 else 'south'
    epsg = 32600 + zone if hemisphere == 'north' else 32700 + zone
    return CRS.from_epsg(epsg)

def transform_coordinates(lon, lat, from_crs='EPSG:4326', to_crs='EPSG:32636'):
    """Convert coordinates between CRS."""
    transformer = Transformer.from_crs(from_crs, to_crs, always_xy=True)
    x, y = transformer.transform(lon, lat)
    return x, y

def haversine_distance_m(lon1, lat1, lon2, lat2):
    """Accurate distance between two WGS84 points in meters."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlam/2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

# RULE: Always store data in WGS84 (EPSG:4326). Transform to UTM for:
#   - Buffer calculations
#   - Distance queries  
#   - Area computations
#   - Spatial indexing

# ENDPOINT
# INPUT: Coordinates + source CRS + target CRS
# OUTPUT: Transformed coordinates
# FORMAT: Always return (lon, lat) for GeoJSON, (x_m, y_m) for metric operations
```

---

### B4. Spatial Indexing (R-tree)

**What it is:** An R-tree is a spatial data structure that accelerates "find things near X" queries from O(n) to O(log n). Essential when you have millions of sample points and need to query "all samples within 500m of this point."

**How it translates to CODE:**

```python
import geopandas as gpd
from shapely.geometry import Point, box
from rtree import index as rtree_index
import numpy as np

class SpatialSampleIndex:
    """
    R-tree backed spatial index for mineral sample database.
    
    In production, this is handled by PostGIS (see F4), but this shows the concept.
    """
    
    def __init__(self):
        self.idx = rtree_index.Index()
        self.samples = {}  # id → sample_data
    
    def insert(self, sample_id, lon, lat, properties=None):
        """Insert a sample point. O(log n)."""
        self.idx.insert(sample_id, (lon, lat, lon, lat))  # bbox = point
        self.samples[sample_id] = {'lon': lon, 'lat': lat, **(properties or {})}
    
    def query_radius(self, lon, lat, radius_meters):
        """
        Find all samples within radius_meters of (lon, lat).
        Uses R-tree for candidate filtering, then exact distance check.
        """
        # Approximate bbox (crude but fast)
        delta_deg = radius_meters / 111320  # ~1 degree ≈ 111.32km
        candidates = list(self.idx.intersection(
            (lon - delta_deg, lat - delta_deg, lon + delta_deg, lat + delta_deg)
        ))
        
        # Exact distance filter
        results = []
        for sid in candidates:
            s = self.samples[sid]
            dist = haversine_distance_m(lon, lat, s['lon'], s['lat'])
            if dist <= radius_meters:
                results.append({**s, 'sample_id': sid, 'distance_m': dist})
        
        return sorted(results, key=lambda x: x['distance_m'])
    
    def query_bbox(self, min_lon, min_lat, max_lon, max_lat):
        """Find all samples within a bounding box."""
        return [self.samples[sid] for sid in 
                self.idx.intersection((min_lon, min_lat, max_lon, max_lat))]

# ENDPOINT
# INPUT: Point (lon, lat) + radius in meters
# OUTPUT: List of samples within radius, sorted by distance
# FORMAT: JSON array of sample objects with distance_m field
# PERFORMANCE: O(log n) for candidate generation, typically <10ms for 1M samples
```

**Where in the platform:** Every spatial query — "show me samples near this anomaly," "find claims within 5km of this prospect," "what's the nearest road access point?"

---

## C. GIS OPERATIONS

### C1. Buffering

**What it is:** Creating a polygon around a feature at a specified distance. Mining use: exclusion zones around rivers, safety perimeters around pits, prospectivity halos around known deposits.

```python
from shapely.geometry import Point, shape
import geopandas as gpd

def buffer_features(gdf, distance_m, dissolve=True):
    """
    Create buffer polygons around GeoDataFrame features.
    
    IMPORTANT: Must use projected CRS (UTM) for metric buffers.
    WGS84 (degrees) does NOT produce correct metric buffers.
    
    Args:
        gdf: GeoDataFrame in WGS84 (will be reprojected internally)
        distance_m: Buffer distance in meters
        dissolve: If True, merge overlapping buffers into one polygon
    
    Returns:
        GeoDataFrame with buffer polygons, reprojected back to WGS84
    """
    # Auto-detect UTM zone
    centroid = gdf.geometry.unary_union.centroid
    utm_crs = auto_utm_crs(centroid.x, centroid.y)
    
    # Reproject → buffer → reproject back
    gdf_utm = gdf.to_crs(utm_crs)
    gdf_utm['geometry'] = gdf_utm.geometry.buffer(distance_m)
    
    if dissolve:
        dissolved = gpd.GeoDataFrame(
            geometry=[gdf_utm.geometry.unary_union], crs=utm_crs
        )
        return dissolved.to_crs('EPSG:4326')
    
    return gdf_utm.to_crs('EPSG:4326')

# Mining-specific buffer rules
BUFFER_RULES = {
    'river_exclusion': 100,      # 100m from rivers (environmental)
    'road_access': 50,           # 50m from roads (infrastructure)
    'fault_proximity': 500,      # 500m from faults (prospectivity)
    'known_deposit_halo': 2000,  # 2km halo around known deposits
    'community_exclusion': 500,  # 500m from settlements
}

# ENDPOINT
# INPUT: GeoDataFrame + buffer distance in meters
# OUTPUT: GeoDataFrame with buffer polygon geometries
# FORMAT: GeoJSON for web, Shapefile for QGIS
# WARNING: Always reproject to UTM before buffering. Buffering in degrees = WRONG.
```

---

### C2. Overlay (Spatial Join & Layer Combination)

**What it is:** Combining multiple spatial layers to answer questions like "which samples fall within claim boundaries?" or "what's the NDVI value at each sample location?"

```python
import geopandas as gpd
import rasterio
from rasterio.sample import sample_gen

def spatial_join_samples_claims(samples_gdf, claims_gdf):
    """
    Find which samples fall within which mining claims.
    
    INPUT: samples_gdf (points), claims_gdf (polygons)
    OUTPUT: samples_gdf with 'claim_id' column added
    """
    # Spatial join: assign claim attributes to each sample point
    joined = gpd.sjoin(samples_gdf, claims_gdf, how='left', predicate='within')
    return joined

def extract_raster_values_at_points(points_gdf, raster_path, band=1):
    """
    Extract raster values (e.g., NDVI, alteration index) at sample locations.
    
    INPUT: points_gdf (GeoDataFrame with geometry), raster_path (GeoTIFF)
    OUTPUT: points_gdf with raster values added as new column
    """
    with rasterio.open(raster_path) as src:
        # Ensure CRS match
        if points_gdf.crs != src.crs:
            points_gdf = points_gdf.to_crs(src.crs)
        
        coords = [(p.x, p.y) for p in points_gdf.geometry]
        values = list(sample_gen(src, coords))
        points_gdf[f'band_{band}_value'] = [v[0] for v in values]
    
    return points_gdf

def multi_layer_overlay(sample_points_path, layers_dict):
    """
    Overlay multiple raster layers onto sample points.
    This is the core "feature extraction" for ML.
    
    INPUT:
        sample_points_path: path to GeoJSON with sample locations
        layers_dict: {
            'ndvi': 'path/to/ndvi.tif',
            'clay_index': 'path/to/clay.tif',
            'iron_index': 'path/to/iron.tif',
            'slope': 'path/to/slope.tif',
            'distance_to_fault': 'path/to/dist_fault.tif',
        }
    
    OUTPUT: DataFrame where each row is a sample, columns are layer values
    """
    samples = gpd.read_file(sample_points_path)
    
    for layer_name, raster_path in layers_dict.items():
        samples = extract_raster_values_at_points(samples, raster_path)
        samples = samples.rename(columns={f'band_1_value': layer_name})
    
    return samples

# ENDPOINT
# INPUT: Points layer + one or more raster/polygon layers
# OUTPUT: Enriched GeoDataFrame with attributes from all layers
# FORMAT: DataFrame for ML, GeoJSON for web display
```

---

### C3. Proximity Analysis

**What it is:** Computing distance from each point/pixel to the nearest feature of a given type. In mining: distance to faults (mineralization often occurs near faults), roads (access), rivers (environmental constraints), existing mines (learning from analogues).

```python
import numpy as np
from scipy.ndimage import distance_transform_edt
import rasterio

def proximity_raster(vector_path, reference_raster_path, output_path):
    """
    Create a raster where each pixel value = distance (meters) to nearest vector feature.
    
    Uses Euclidean Distance Transform for speed.
    
    INPUT:
        vector_path: GeoJSON/Shapefile with lines or polygons (e.g., faults, rivers)
        reference_raster_path: Template raster (defines extent, resolution, CRS)
        output_path: Where to save the distance raster
    
    OUTPUT: GeoTIFF where pixel values = distance in meters to nearest feature
    """
    with rasterio.open(reference_raster_path) as ref:
        profile = ref.profile.copy()
        transform = ref.transform
        out_shape = (ref.height, ref.width)
        crs = ref.crs
    
    # Rasterize vector features (burn features into raster)
    import rasterio.features
    import geopandas as gpd
    
    gdf = gpd.read_file(vector_path)
    if gdf.crs != crs:
        gdf = gdf.to_crs(crs)
    
    # Create binary raster: 1 = feature present, 0 = no feature
    shapes = [(geom, 1) for geom in gdf.geometry]
    feature_raster = rasterio.features.rasterize(
        shapes, out_shape=out_shape, transform=transform, fill=0, dtype='uint8'
    )
    
    # Compute distance transform (pixels to nearest 1-valued pixel)
    pixel_size = abs(transform.a)  # meters per pixel (assuming UTM)
    distance_pixels = distance_transform_edt(feature_raster == 0)
    distance_meters = distance_pixels * pixel_size
    
    # Save
    profile.update(dtype='float32', count=1)
    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(distance_meters.astype('float32'), 1)
    
    return distance_meters

# Mining proximity layers to compute:
PROXIMITY_LAYERS = {
    'dist_to_faults': 'Faults are conduits for mineralizing fluids',
    'dist_to_rivers': 'Environmental exclusion + alluvial proximity',
    'dist_to_roads': 'Infrastructure access score',
    'dist_to_known_deposits': 'Analogue-based prospectivity',
    'dist_to_intrusions': 'Porphyry/skarn proximity indicator',
    'dist_to_contacts': 'Lithological contacts — structural traps',
}

# ENDPOINT
# INPUT: Vector features (lines/polygons) + reference raster for extent
# OUTPUT: GeoTIFF with float32 distance values in meters
# TYPICAL: Input 50k fault lines → output 10,000×10,000 distance raster in