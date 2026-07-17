# 🛸 Drone & Sensor Systems for Mineral Exploration in Nyatike, Migori County, Kenya

**Practical Guide — Equipment, Software, Costs & Field Survey Protocol**

---

## Executive Summary

This guide provides a practical, budget-conscious approach to using drones and sensors for detecting gold and copper deposits in the Nyatike area of Migori County, Kenya. The Nyatike region lies within the Migori-Nyanza Greenstone Belt, a gold-bearing geological province in the Lake Victoria Goldfields. The approach combines affordable drone platforms, portable sensors, free satellite imagery, open-source software, and AI-assisted data processing to create investor-ready resource estimates.

**Total estimated startup budget: $800–$2,500** (excluding laptop/PC already owned)

---

## 1. Geological Context — Nyatike, Migori County

### 1.1 Regional Geology

- **Province:** Lake Victoria Goldfields, Nyanza Greenstone Belt
- **Host Rocks:** Metavolcanic and metasedimentary rocks (Banded Iron Formations, schists, quartz veins)
- **Mineralization Types:**
  - **Alluvial gold** — in river gravels of Migori River and tributaries (primary target)
  - **Lode gold** — in quartz veins within shear zones in greenstone belt
  - **Copper** — associated with sulfide minerals in metavolcanic rocks, upper oxidation zone
- **Known deposits:** Macalder copper-gold mine (historical), Nyatike artisanal gold mining areas
- **Structural controls:** NE-trending shear zones, fold hinges, contacts between rock types

### 1.2 What We're Looking For

| Target | Indicator | Detection Method |
|--------|-----------|-----------------|
| Alluvial gold | Dark heavy mineral sands, iron staining, old river channels | Multispectral imagery, magnetometry, ground sampling |
| Copper (oxide zone) | Green/blue surface staining (malachite/azurite), gossans (iron oxide caps) | Multispectral, NIR spectroscopy, XRF |
| Quartz veins | White/linear features in terrain | Aerial photography, DTM analysis |
| Structural zones | Linear features, vegetation changes | Satellite imagery, drone DTM |

---

## 2. Drone Platforms (Under $2,000)

### 2.1 Tier 1: Budget Mapping Drone ($300–$500)

| Model | Price | Specs | Best For |
|-------|-------|-------|----------|
| **DJI Mini 2 SE** | ~$300 | 12MP, 31min flight, 10km range | Basic orthophoto mapping, reconnaissance |
| **DJI Mini 3** | ~$400 | 12MP, 38min flight, good video | Aerial documentation, basic mapping |
| **DJI Mini 4K** | ~$300 | 12MP, 31min flight | Budget aerial survey |

**Recommended for Nyatike: DJI Mini 2 SE or Mini 3** — lightweight (<249g), no special registration needed in many jurisdictions, good enough for 5m accuracy orthophotos with ground control points.

### 2.2 Tier 2: Serious Survey Drone ($800–$1,500)

| Model | Price | Specs | Best For |
|-------|-------|-------|----------|
| **DJI Mini 4 Pro** | ~$760 | 48MP, 34min, omnidirectional sensing | High-res mapping, photogrammetry |
| **DJI Air 3** | ~$1,100 | 48MP dual camera, 46min flight | Extended survey missions |
| **DJI Mavic 3 Classic** | ~$1,500 | 20MP Hasselblad, 46min, mechanical shutter | Professional photogrammetry |

### 2.3 Tier 3: Multispectral Drone ($1,500–$2,500)

| Model | Price | Specs | Best For |
|-------|-------|-------|----------|
| **DJI Mavic 3M** (Multispectral) | ~$4,000–$5,000 | 20MP RGB + 4×5MP multispectral (G/R/RE/NIR), RTK | Vegetation stress mapping, geological alteration detection |

**⚠️ Note:** The DJI Mavic 3M exceeds the $2,000 budget but is the gold standard for affordable multispectral. Consider splitting cost with partners or renting.

**Budget alternative:** Use a Tier 2 drone with a **modified camera** (see Section 3.3).

### 2.4 Essential Accessories

| Item | Price | Why |
|------|-------|-----|
| Extra batteries (×4 minimum) | $40–$80 each | Each flight = 20–30 min. Need 6+ batteries for a full survey day |
| ND filters set | $20–$40 | Reduce glare, improve image quality in bright equatorial sun |
| Landing pad | $15 | Protects drone from dust/debris at field sites |
| Carrying case | $30 | Transport protection for field work |
| MicroSD cards (128GB ×2) | $20 | Drone data storage |

---

## 3. Sensors for Mineral Detection

### 3.1 Sensor Priority Matrix for Gold & Copper

| Sensor | Detects | Budget Option | Price Range |
|--------|---------|---------------|-------------|
| **RGB Camera** (drone) | Surface features, quartz veins, gossans | Built into all drones | Included |
| **Multispectral Camera** | Vegetation stress (indicator of subsurface minerals), alteration zones | Modified consumer camera | $200–$500 |
| **Magnetometer** | Magnetic anomalies (BIF, shear zones, iron-bearing minerals) | DIY fluxgate or smartphone magnetometer | $50–$300 |
| **NIR Spectrometer** | Mineral identification (clay, iron oxides, carbonates) | Consumer NIR device | $300–$1,000 |
| **XRF Analyzer** | Elemental composition (gold, copper, lead, zinc) | Rental or used unit | $200/day rental or $15,000+ purchase |
| **Ground Penetrating Radar** | Subsurface structure, bedrock depth, buried channels | Professional drone-GPR | $10,000+ (rental recommended) |

### 3.2 Affordable Sensor Options

#### A) Magnetometer — DIY Fluxgate ($50–$200)

- **What it detects:** Magnetic anomalies from Banded Iron Formations, magnetite-bearing rocks, shear zones — all associated with gold mineralization in greenstone belts
- **DIY Option:** Build a fluxgate magnetometer using a Raspberry Pi + HMC5883L/GY-271 module (~$15 for the sensor module)
- **Better Option:** GY-271 QMC5883L 3-axis digital compass module connected to Arduino/Raspberry Pi
- **Integration:** Mount on drone with 3D-printed bracket, log GPS + magnetic readings via smartphone app
- **Cost:** $50–$150 total

**Raspberry Pi + Magnetometer Build:**
```
Components:
- Raspberry Pi Zero 2W: $15
- GY-271 QMC5883L magnetometer: $8
- GPS module (NEO-6M): $12
- MicroSD card: $8
- Power bank/battery: $15
- 3D-printed mount: $10
- Wires/connectors: $5
Total: ~$73
```

#### B) Modified Camera for Multispectral ($200–$400)

- **Concept:** Remove the IR-cut filter from a cheap point-and-shoot camera to capture Near-Infrared (NIR) light
- **Camera:** Used Sony WX-series or Canon PowerShot (~$50–$100 on eBay)
- **Conversion service:** LifePixel or DIY (~$100–$200)
- **Result:** False-color NIR imagery that reveals vegetation health stress (indicates subsurface mineralization)
- **Software:** Process with free OpenDroneMap or QGIS

#### C) Smartphone-Based Mineral ID ($0–$50)

| App | Platform | Function |
|-----|----------|----------|
| **Rock Identifier** | iOS/Android | AI-powered rock/mineral ID from photos |
| **Geology Toolkit** | Android | Mineral database with properties |
| **Google Earth** | All | Free satellite imagery for reconnaissance |
| **GPS Essentials** | Android | Waypoint logging for field sampling |
| **Sensor Kinetics** | iOS/Android | Access phone's built-in magnetometer |

#### D) Portable NIR Spectrometer ($300–$1,000)

- **ASD TerraSpec** (used/rented): Professional-grade, $300/day rental
- **SCiO Consumer NIR**: ~$300, limited mineral database but can distinguish some minerals
- **DIY NIR with Raspberry Pi + spectral sensor**: AS7265x spectral sensor (~$50), can detect absorption features of clay minerals, iron oxides

#### E) XRF Analyzer — Rental Strategy ($150–$300/day)

- **Why XRF:** Directly measures gold (Au), copper (Cu), lead (Pb), zinc (Zn), arsenic (As) in rock and soil samples
- **Brands:** Olympus Vanta, Bruker S1 Titan, Thermo Niton
- **Rental companies:** National equipment rental services, local geological suppliers
- **Strategy:** Rent for 2–3 days to analyze all collected samples
- **Alternative:** Send samples to a lab (~$10–$30 per sample for multi-element ICP analysis)

### 3.3 Sensor Integration with Drones

For the DIY enthusiast, sensors can be mounted on drones:

```
Drone Payload Integration:
┌─────────────────────────┐
│   DJI Mini 4 Pro        │
│   ┌─────────────────┐   │
│   │  Camera (built) │   │
│   └─────────────────┘   │
│   ┌─────────────────┐   │
│   │ 3D-printed tray │   │
│   │  - Magnetometer  │   │
│   │  - GPS logger    │   │
│   │  - Raspberry Pi  │   │
│   └─────────────────┘   │
│   Weight limit: 100-200g│
└─────────────────────────┘
```

**Weight considerations:**
- DJI Mini series: Max payload ~100g extra (keep total <250g for regulations)
- DJI Air/Mavic: Can carry 200–500g extra with custom mount
- Use 3D-printed mounts or velcro straps for sensor attachment

---

## 4. Free & Low-Cost Data Sources

### 4.1 Free Satellite Imagery

| Source | Resolution | Best For | URL |
|--------|-----------|----------|-----|
| **Sentinel-2 (ESA)** | 10m multispectral | Alteration mapping, vegetation indices | copernicus.eu |
| **Landsat 8/9 (NASA)** | 30m multispectral + thermal | Regional geological mapping | earthexplorer.usgs.gov |
| **ASTER (NASA)** | 15–90m SWIR/TIR | Hydrothermal alteration minerals | earthexplorer.usgs.gov |
| **Google Earth** | ~1m (varies) | Reconnaissance, feature identification | earth.google.com |
| **ALOS PALSAR** | 12.5m radar | Structural lineament detection | asf.alaska.edu |

### 4.2 Free Geological Data for Kenya

| Source | Content |
|--------|---------|
| **Kenya Geological Survey** | Geological maps, mineral occurrence records |
| **Kenya矿业部 (Mining Ministry)** | Mining license data, mineral rights maps |
| **USGS Mineral Resources Data System** | Known mineral occurrences |
| **British Geological Survey (BGS)** | Historical geological maps of East Africa |
| **OneGeology Portal** | International geological map compilation |

### 4.3 Spectral Analysis with Free Satellite Data

**How to detect alteration minerals from space (FREE):**

1. **Download Sentinel-2 imagery** for Nyatike area from Copernicus Open Access Hub
2. **Use QGIS** (free) with Semi-Automatic Classification Plugin (SCP)
3. **Calculate alteration indices:**
   - **Clay Minerals Index** (Band 11 / Band 12) — indicates argillic alteration (associated with gold)
   - **Iron Oxide Index** (Band 4 / Band 3) — gossans and iron-rich zones
   - **Ferric Iron / Ferrous Iron ratio** — oxidation state mapping
   - **NDVI** (vegetation index) — vegetation stress can indicate subsurface mineralization
4. **Create alteration maps** highlighting zones for ground follow-up

---

## 5. Software Stack (All Free/Low-Cost)

### 5.1 Drone Mapping & Photogrammetry

| Software | Cost | Function |
|----------|------|----------|
| **OpenDroneMap / WebODM** | Free (open source) | Photogrammetry: orthophotos, DTM, DSM, point clouds from drone photos |
| **Litchi** | ~$25 (mobile app) | Automated flight planning for DJI drones |
| **DJI Fly / DJI RC** | Free | Basic DJI drone control |
| **QGIS** | Free (open source) | GIS analysis, mapping, data integration |
| **CloudCompare** | Free (open source) | 3D point cloud visualization and analysis |
| **Google Earth Pro** | Free | Satellite imagery overlay, reconnaissance |

### 5.2 Geological & Geophysical Analysis

| Software | Cost | Function |
|----------|------|----------|
| **QGIS** + Plugins | Free | All GIS analysis, spectral processing, geological mapping |
| **Semi-Automatic Classification Plugin (SCP)** | Free | Satellite image classification, atmospheric correction |
| **EIS Toolkit** (QGIS Plugin) | Free | Mineral prospectivity mapping |
| **GMT (Generic Mapping Tools)** | Free | Geophysical data processing |
| **Python + libraries** | Free | Custom analysis scripts (NumPy, SciPy, scikit-learn, GDAL) |
| **ParaView** | Free | 3D visualization of subsurface models |

### 5.3 AI & Machine Learning for Pattern Recognition

| Tool | Cost | Application |
|------|------|-------------|
| **Google Earth Engine** | Free (with account) | Large-scale satellite analysis, time-series |
| **TensorFlow / PyTorch** | Free | Train custom mineral detection models |
| **scikit-learn** | Free | Classification of mineral zones from sensor data |
| **Orange Data Mining** | Free | Visual machine learning for geochemical data |
| **R (with gstat)** | Free | Geostatistics, kriging for resource estimation |

---

## 6. Step-by-Step Field Survey Protocol for Nyatike

### Phase 1: Desktop Study & Reconnaissance (Week 1–2) — $0

```
STEP 1.1: Compile Existing Data
├── Download Sentinel-2 imagery for Nyatike area
├── Download Landsat 8/9 data
├── Obtain geological maps from Kenya Geological Survey
├── Review historical mining records (Macalder mine, artisanal mining areas)
├── Plot known mineral occurrences in QGIS
└── Identify structural lineaments from satellite imagery

STEP 1.2: Spectral Alteration Mapping
├── Process Sentinel-2 with QGIS + SCP plugin
├── Calculate clay mineral index, iron oxide index, NDVI
├── Create alteration map highlighting targets
├── Cross-reference with geological map
└── Define 3–5 priority survey areas

STEP 1.3: Survey Planning
├── Define survey boundaries using Google Earth
├── Create KML polygon files for drone flight planning
├── Identify access routes, landing zones, safety concerns
├── Plan ground control point locations
└── Schedule field work (dry season preferred: Jan–Feb, Jun–Sep)
```

### Phase 2: Drone Aerial Survey (Week 3) — $300–$800

```
STEP 2.1: Ground Control Points (GCPs)
├── Place 6+ GCPs per survey area (checkerboard ceramic tiles, 30cm)
├── Record GPS coordinates with smartphone (±5m accuracy)
├── For better accuracy: use RTK GPS or survey-grade handheld ($50–$100/day rental)
└── Photograph each GCP for identification in post-processing

STEP 2.2: Drone Flight Missions
├── Program flights using Litchi app:
│   ├── Altitude: 80–120m AGL
│   ├── Speed: 15–25 km/h
│   ├── Photo overlap: 70% front, 70% side
│   ├── Flight line spacing: 40–60m
│   └── Photo interval: 5–7 seconds
├── Fly each survey area with 4–6 battery cycles
├── Monitor for obstacles, wind, battery levels
└── Log all flight data

STEP 2.3: Optional — Magnetometer Drone Survey
├── Mount DIY magnetometer on drone
├── Fly systematic grid lines at constant altitude (30–50m)
├── Log GPS + magnetic readings at 1–10 Hz
├── Maintain consistent speed and altitude for data quality
└── Process magnetic data to create anomaly maps
```

### Phase 3: Ground Truth & Sampling (Week 4) — $200–$500

```
STEP 3.1: Field Reconnaissance
├── Visit alteration anomalies identified from satellite/drone data
├── Document rock types, structures, alteration minerals
├── Photograph outcrops, mineralized zones, old workings
├── Use smartphone mineral ID apps for field identification
└── Log all observations with GPS waypoints

STEP 3.2: Systematic Sampling
├── Soil sampling: Grid at 50m × 50m or 100m × 100m spacing
│   ├── Collect 1–2 kg samples at 20–30cm depth
│   ├── Use GPS to record each sample location
│   └── Label bags clearly with sample ID, date, coordinates
├── Rock chip sampling:
│   ├── Sample quartz veins, altered zones, gossans
│   ├── 1–2 kg representative samples
│   └── Record host rock type, alteration, structural data
├── Stream sediment sampling:
│   ├── Collect from active stream channels
│   ├── Sample heavy mineral concentrates
│   └── Focus on confluences and behind boulders
└── Alluvial sampling (for gold):
    ├── Dig test pits in river terraces (1m × 1m × 1m)
    ├── Pan concentrates to check for visible gold
    └── Collect bulk samples (10–20 kg) for lab assay

STEP 3.3: Portable Analysis
├── Use smartphone magnetometer to check magnetic susceptibility of samples
├── Use NIR device/app to identify alteration minerals
├── Record color, hardness, density observations
└── Photograph all samples with scale bar
```

### Phase 4: Data Processing & Analysis (Week 5–6) — $100–$300

```
STEP 4.1: Drone Photogrammetry
├── Import photos into WebODM
├── Process to create:
│   ├── Orthophoto mosaic (georeferenced aerial photo)
│   ├── Digital Terrain Model (DTM) — bare earth
│   ├── Digital Surface Model (DSM) — includes vegetation
│   └── 3D Point Cloud
├── Export as GeoTIFF for QGIS import
└── Processing time: 4–12 hours per survey area (depending on PC)

STEP 4.2: GIS Data Integration
├── Import all data layers into QGIS:
│   ├── Drone orthophoto + DTM
│   ├── Satellite alteration maps
│   ├── Magnetic anomaly data (if collected)
│   ├── Sample locations + assay results
│   ├── Geological map overlay
│   └── Structural lineament interpretation
├── Create integrated geological interpretation map
└── Identify drill targets / priority zones

STEP 4.3: AI-Assisted Analysis
├── Use Python + scikit-learn for:
│   ├── Cluster analysis of geochemical data
│   ├── Classification of mineral zones from multispectral data
│   └── Anomaly detection in magnetic data
├── Use Google Earth Engine for:
│   ├── Time-series vegetation analysis
│   └── Multi-date change detection
└── Train simple ML model if sufficient data points exist
```

### Phase 5: Lab Analysis & Resource Estimation (Week 7–8) — $500–$2,000

```
STEP 5.1: Laboratory Analysis
├── Send priority samples to accredited lab:
│   ├── Gold: Fire assay + ICP (¥$15–$30/sample)
│   ├── Copper/multi-element: ICP-OES/MS ($10–$25/sample)
│   └── Recommended labs: SGS Kenya, ALS Kenya, or Nairobi-based labs
├── Consider portable XRF rental for screening (1–2 days, $200–$300/day)
└── Process 50–200 samples depending on budget

STEP 5.2: Resource Estimation
├── Create grade maps from assay results in QGIS
├── Use kriging or IDW interpolation for grade estimation
├── Calculate tonnage from DTM + sampling depth data
├── Estimate gold/copper content using:
│   ├── Surface area × average depth × bulk density × average grade
│   └── For alluvial: channel width × depth × length × grade
├── Apply appropriate geological confidence factors
└── Note: This is an INFERRED resource estimate — not NI 43-101 compliant

STEP 5.3: Investor-Ready Report
├── Compile all maps, data, and interpretations
├── Create professional report with:
│   ├── Executive summary
│   ├── Location and geology
│   ├── Exploration methodology
│   ├── Results (maps, assays, cross-sections)
│   ├── Resource estimate (with disclaimers)
│   └── Recommendations for next phase
└── Prepare presentation materials
```

---

## 7. Budget Summary

### Minimal Budget (~$800)

| Item | Cost |
|------|------|
| DJI Mini 2 SE drone | $300 |
| Extra batteries (×4) | $160 |
| Litchi app | $25 |
| Ground control points (DIY) | $20 |
| Soil/rock sampling supplies | $50 |
| Lab analysis (30 samples) | $600 |
| **TOTAL** | **~$1,155** |

### Recommended Budget (~$2,000)

| Item | Cost |
|------|------|
| DJI Mini 4 Pro drone | $760 |
| Extra batteries (×4) | $200 |
| Litchi app | $25 |
| DIY magnetometer (Raspberry Pi) | $100 |
| Modified NIR camera | $200 |
| Ground control points | $30 |
| Sampling supplies | $75 |
| Lab analysis (50 samples) | $1,000 |
| XRF rental (1 day) | $250 |
| **TOTAL** | **~$2,640** |

### Professional Budget (~$5,000–$8,000)

| Item | Cost |
|------|------|
| DJI Mavic 3M (Multispectral) | $4,500 |
| Extra batteries + accessories | $300 |
| Portable NIR spectrometer (used) | $500 |
| XRF rental (3 days) | $750 |
| Lab analysis (100 samples) | $2,000 |
| Professional survey GPS rental | $200 |
| Software (all free) | $0 |
| **TOTAL** | **~$8,250** |

---

## 8. Practical Tips for Nyatike Fieldwork

### 8.1 Regulatory

- **Kenya Civil Aviation Authority (KCAA):** Register drones >250g. DJI Mini series (<250g) may have lighter requirements but check current regulations
- **Mining license:** Ensure you have a valid prospecting/mineral right from Kenya's Mining Cadastre
- **Community engagement:** Inform local community leaders; artisanal miners may be valuable informants

### 8.2 Environmental & Safety

- **Best season:** Dry season (January–February, June–September) for accessible roads and clear skies
- **Equatorial conditions:** Strong sun — use ND filters, fly early morning (6–9 AM) or late afternoon (4–6 PM) for best light
- **Dust:** Protect drone motors and camera lens from red laterite dust
- **Security:** Travel with local guides; some artisanal mining areas have security concerns
- **Health:** Malaria prophylaxis, carry water, sun protection

### 8.3 Working with Artisanal Miners

- Artisanal miners in Nyatike have extensive local knowledge of gold-bearing zones
- Their excavations provide free exposure of subsurface geology
- **Engage respectfully:** Offer to share survey results; they can guide you to productive areas
- Document their workings with drone photography for geological understanding

---

## 9. Quick-Start Checklist

```
PRE-FIELD (2 weeks)
□ Download Sentinel-2 imagery for Nyatike
□ Process alteration maps in QGIS
□ Define survey areas and flight plans
□ Purchase drone + batteries + accessories
□ Install WebODM, QGIS, Litchi
□ Prepare sampling equipment
□ Obtain mining license/permissions
□ Contact local guide/community leaders

FIELD WEEK 1: Drone Survey
□ Place ground control points
□ Fly all survey areas
□ Collect magnetometer data (if equipped)
□ Conduct initial field reconnaissance
□ Document all observations with GPS

FIELD WEEK 2: Sampling
□ Systematic soil sampling on grid
□ Rock chip sampling of key outcrops
□ Stream sediment sampling
□ Alluvial test pitting and panning
□ Portable analysis (NIR, magnetometer)

POST-FIELD (2–4 weeks)
□ Process drone imagery in WebODM
□ Send samples to lab
□ Integrate all data in QGIS
□ Run spectral/geophysical analysis
□ Create geological interpretation
□ Compile resource estimate
□ Prepare investor report
```

---

## 10. Key Resources & Links

| Resource | URL |
|----------|-----|
| OpenDroneMap / WebODM | https://opendronemap.org |
| QGIS | https://qgis.org |
| Copernicus (Sentinel-2) | https://copernicus.eu |
| USGS Earth Explorer | https://earthexplorer.usgs.gov |
| Google Earth Engine | https://earthengine.google.com |
| QGIS in Mineral Exploration guide | https://qgis-in-mineral-exploration.readthedocs.io |
| Litchi Flight Planning | https://flylitchi.com |
| CloudCompare (point clouds) | https://cloudcompare.org |
| EIS Toolkit (mineral prospectivity) | https://github.com/GISPO/EIS_Toolbox |

---

## Disclaimer

This guide provides a framework for preliminary mineral exploration. Results from these methods are indicative, not definitive. For investor-grade resource estimates, NI 43-101 or JORC-compliant reports require professional geologists, qualified persons, and systematic drilling programs. The methods described here are suitable for **reconnaissance and target generation** — identifying where to focus more expensive professional exploration.

---

*Document prepared for Nyatike mineral exploration project — July 2026*
