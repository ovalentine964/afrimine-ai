# AI Tools for Mining: Comprehensive Inventory
## Focus: Small-Scale Gold + Copper Operation in Rural Kenya

**Compiled:** July 2026
**Purpose:** Complete inventory of AI tools, platforms, and repositories applicable to mining operations

---

## TABLE OF CONTENTS

1. [GitHub Repositories](#1-github-repositories)
2. [AI Platforms for Mining](#2-ai-platforms-for-mining)
3. [Quantum Computing in Mining](#3-quantum-computing-in-mining)
4. [Emerging AI Systems](#4-emerging-ai-systems)
5. [Cost Analysis](#5-cost-analysis)
6. [Feasibility for Kenya Small-Scale Operation](#6-feasibility-for-kenya-small-scale-operation)

---

## 1. GITHUB REPOSITORIES

### 1.1 Mineral Exploration & ML (Resource Lists)

| Repository | Stars | Description | Link |
|---|---|---|---|
| **RichardScottOZ/mineral-exploration-machine-learning** | 330+ | Comprehensive curated list of ML resources for mineral exploration. Covers prospectivity mapping, geology, geochemistry, geophysics, NLP, remote sensing. Includes Africa-specific datasets (Namibia, Sudan). | https://github.com/RichardScottOZ/mineral-exploration-machine-learning |
| **softwareunderground/awesome-open-geoscience** | 1.8k | Curated list of open-source geoscience tools. Covers simulation, geospatial, geophysics, geology, groundwater, geostatistics, geochemistry. | https://github.com/softwareunderground/awesome-open-geoscience |
| **lasio** (kinverarity1) | 397 | Python library for reading/writing well log data (LAS files). Essential for drill core analysis. | https://github.com/kinverarity1/lasio |

### 1.2 Geological Modeling

| Repository | Description | Link |
|---|---|---|
| **gempy-project/gempy** | Open-source Python 3D structural geological modeling. Implicit creation of complex geological models from interface/orientation data. Supports stochastic modeling for uncertainty. | https://github.com/gempy-project/gempy |
| **agilescientific/striplog** | Lithology and stratigraphic logs for wells or outcrop. Python library for visualizing geological sequences. | https://github.com/agilescientific/striplog |
| **GeoStat-Framework** | Group of repos for kriging and geostatistics. Includes pykrige and other spatial interpolation tools. | https://github.com/GeoStat-Framework |
| **GemPy** | 3D geological modeling with Bayesian inference capabilities. Can integrate with machine learning pipelines. | https://github.com/gempy-project/gempy |

### 1.3 Prospectivity Mapping & Mineral Targeting

| Repository | Description | Link |
|---|---|---|
| **EIS Toolkit** (GispoCoding) | Python library for mineral prospectivity mapping from EIS Horizon EU Project. Ready-to-use workflows. | https://github.com/GispoCoding/eis_toolkit |
| **PySpatialML** | Library for spatial prediction with ML, automatic handling of raster data to GeoTIFF. | https://github.com/RichardScottOZ/Pyspatialml |
| **EarthByte/porphyry-prospectivity-global** | Spatio-temporal global mapping of porphyry copper deposits. Directly relevant for copper exploration. | https://github.com/EarthByte/porphyry-prospectivity-global |
| **EarthByte/STAMP_PNG** | SpatioTemporAl Mineral Prospectivity Modelling. Tested in Papua New Guinea conditions. | https://github.com/EarthByte/STAMP_PNG |
| **GeoscienceAustralia/minpot-toolkit** | Mineral potential mapping toolkit with sedimentary copper analysis. | https://github.com/GeoscienceAustralia/minpot-toolkit |
| **GeoscienceAustralia/MPM-WofE** | Mineral Potential Mapping using Weights of Evidence method. | https://github.com/GeoscienceAustralia/MPM-WofE |
| **EarthByte/MPM_Curnamona_REE** | DEEP-SEAM: Explainable semi-supervised deep learning for mineral prospectivity mapping. | https://github.com/EarthByte/MPM_Curnamona_REE |

### 1.4 Mining Detection (Satellite-Based)

| Repository | Description | Link |
|---|---|---|
| **earthrise-media/mining-detector** | Automated detection of artisanal gold mines in Sentinel-2 satellite imagery. **DIRECTLY RELEVANT** for Kenya ASM operations. | https://github.com/earthrise-media/mining-detector |
| **Ashok080/GeoMind-AI** | Mineral detection using satellite imagery + AI. Python-based with Streamlit dashboard. | https://github.com/Ashok080/GeoMind-AI |
| **erwin-project/Mineral-Detection-using-AI** | AI-based mineral detection system. | https://github.com/erwin-project/Mineral-Detection-using-AI |

### 1.5 Ore Grade Estimation

| Repository/Resource | Description | Link |
|---|---|---|
| **Bahram Jafrasteh repos** | ML for ore grade estimation using Gaussian Processes, neural networks, and geostatistics. Published research with code. | https://bahramjafrasteh.github.io/ |
| **Comparison of ML methods for copper ore grade estimation** | Academic paper with Python implementations for copper ore specifically. | Published in Neurocomputing |

### 1.6 DARPA CRITICALMAAS Tools

| Repository | Description | Link |
|---|---|---|
| **DARPA-CRITICALMAAS** (org) | US government-funded AI tools for critical mineral assessment. Multiple repos. | https://github.com/DARPA-CRITICALMAAS |
| **uncharted-ta1** | Automated feature extraction and georeferencing of geological maps. | https://github.com/DARPA-CRITICALMAAS/uncharted-ta1 |
| **sri-ta2-mappable-criteria** (QueryPlot) | Generating mineral evidence maps from geological queries. | https://github.com/DARPA-CRITICALMAAS/sri-ta2-mappable-criteria |

### 1.7 ML Frameworks for Geoscience

| Repository | Description | Link |
|---|---|---|
| **UNCOVER-ML Framework** | Large-scale spatial ML framework for mineral exploration. | https://github.com/RichardScottOZ/uncover-ml |
| **Landshark** | Large-scale spatial inference with TensorFlow. | https://github.com/data61/landshark |
| **TorchGeo** (Microsoft) | PyTorch library for remote sensing models. | https://github.com/microsoft/torchgeo |
| **terratorch** (IBM) | Flexible fine-tuning framework for Geospatial Foundation Models. | https://github.com/IBM/terratorch |
| **scikit-map** | Python library for spatial data processing and ML. | https://github.com/scikit-map/scikit-map |
| **truly-spatial-random-forest** | Spatial Random Forest algorithm designed specifically for geoscience data. | https://github.com/RichardScottOZ/truly-spatial-random-forest |

### 1.8 Geochemistry & XRF Analysis

| Resource | Description |
|---|---|
| **PySpatStat** | Spatial statistics in Python, useful for geochemical anomaly detection. |
| **scikit-learn + geochem pipelines** | Multiple published workflows for using scikit-learn for geochemical data classification. |
| **R-based geochemistry** | Packages like `compositions`, `robcompositions` for geochemical data analysis. |

---

## 2. AI PLATFORMS FOR MINING

### 2.1 Major Mining Company AI Systems

#### Rio Tinto — Mine of the Future™
- **Autonomous Haulage System (AHS):** 400+ autonomous trucks across Pilbara operations
- **AutoHaul™:** World's first autonomous heavy-haul railway
- **Mine Automation System (MAS):** Integrated command center
- **AI for drilling optimization:** Predictive models for blast hole drilling
- **Status:** Fully operational, proprietary, not available externally
- **Cost:** Billions in R&D investment over 15+ years

#### BHP — Digital Mine
- **AI-powered predictive maintenance** across equipment fleet
- **Computer vision** for conveyor belt monitoring
- **Autonomous drilling** systems
- **Digital twins** of processing plants
- **Status:** Operational, some partnerships possible

#### Barrick Gold — Digital Transformation
- **AI-driven geological modeling** for ore body characterization
- **Predictive analytics** for gold recovery optimization
- **IoT sensor networks** across mine sites
- **Partnership with Cisco** for edge computing at remote sites
- **Status:** Operational, proprietary

### 2.2 AI Startups & Platforms

#### KoBold Metals
- **What:** AI-powered mineral exploration company (copper, lithium, cobalt, nickel)
- **Technology:** Proprietary ML models analyzing geological, geochemical, geophysical data
- **Funding:** $537M raised (Jan 2025)
- **Operations:** Active in Zambia, DRC, Australia, Canada, USA
- **Relevance:** They operate in Africa; their approach (data fusion + ML) is the gold standard
- **Cost:** Not available as a service; they are a mining company
- **Website:** https://koboldmetals.com/

#### Earth AI
- **What:** Vertically integrated AI-powered mineral explorer
- **Technology:** Mineral Targeting Platform (MTP) — AI for prospectivity mapping
- **Funding:** $20M raised (Jan 2025)
- **Results:** Confirmed 6 new tungsten, cobalt, and gold prospects
- **Location:** Australia-based
- **Relevance:** Their methodology (AI prospectivity + targeted drilling) is directly applicable
- **Website:** https://earth-ai.com/

#### GoldSpot Discoveries (now part of SmartMining)
- **What:** AI and ML targeting technology for mineral exploration
- **Technology:** Data integration, ML-based target generation, drill hole optimization
- **Clients:** Works with exploration and mining companies globally
- **Relevance:** Offers consulting/services; could be engaged for Kenya project
- **Cost:** Project-based consulting, typically $50K-$200K per engagement
- **Website:** https://goldspot.ca/

#### VerAI Discoveries
- **What:** AI platform for mineral exploration targeting
- **Technology:** ML analysis of geophysical, geochemical, and geological data
- **Focus:** Battery metals and critical minerals
- **Website:** https://veraidiscoveries.com/

#### Minerva Intelligence
- **What:** AI-powered geological reasoning and data integration
- **Technology:** GEOVISUAL, GRAI (Geological Reasoning AI)
- **Capability:** Automated geological map interpretation
- **Website:** https://minervaintelligence.com/

### 2.3 Open-Source / Free Tier Platforms

| Platform | Description | Cost | Feasibility |
|---|---|---|---|
| **QGIS** | Open-source GIS with extensive plugin ecosystem for geological mapping | Free | ★★★★★ |
| **Google Earth Engine** | Cloud-based satellite imagery analysis. Free for research/non-commercial. Sentinel-2, Landsat, ASTER data. | Free (research) | ★★★★★ |
| **Sentinel Hub (EO Browser)** | Free access to Sentinel-2 satellite imagery with API | Free tier available | ★★★★★ |
| **USGS EarthExplorer** | Free access to Landsat, ASTER, and geological survey data | Free | ★★★★★ |
| **OpenDroneMap** | Open-source drone imagery processing for 3D mapping | Free | ★★★★ |
| **Micromine** | Geological modeling and mine planning. Academic licenses available. | $5K-$50K/yr | ★★★ |
| **Leapfrog (Seequent)** | 3D geological modeling. Industry standard. | $10K-$30K/yr | ★★★ |
| **GOCAD Mining Suite** | Advanced 3D geological modeling | $20K-$100K/yr | ★★ |

### 2.4 Computer Vision for Ore Classification

| Tool/Approach | Description | Cost |
|---|---|---|
| **YOLOv8/v9 for rock classification** | Train custom object detection on ore images. Multiple published papers. | Free (open-source) |
| **TensorFlow/PyTorch CNN models** | Image classification for ore type identification from photos | Free |
| **Mineral thin section analysis** | Published ML models for petrographic analysis | Free (academic) |
| **Conveyor belt vision systems** | Real-time ore grade estimation from belt camera images | $50K-$500K (commercial) |

---

## 3. QUANTUM COMPUTING IN MINING

### 3.1 Current State (2026)

**Verdict: NOT PRACTICAL for any mining operation today, especially small-scale.**

#### What Exists
- **Theoretical research** on quantum algorithms for geological modeling (published papers)
- **Quantum-inspired** optimization algorithms (running on classical hardware) being tested by large miners
- **IBM Qiskit** and **Google Cirq** have some geoscience research applications
- **D-Wave** quantum annealing tested for mine scheduling optimization (academic only)

#### Companies Working on Quantum + Mining
| Company | Status | Practical? |
|---|---|---|
| **Rio Tinto + IBM** | Research partnership on quantum for ore body modeling | No — experimental |
| **BHP + Microsoft Azure Quantum** | Exploring quantum for supply chain optimization | No — proof of concept |
| **Goldcorp (now Newmont)** | Historical quantum computing challenges for exploration | No — discontinued |
| **Multiverse Computing** | Quantum-inspired algorithms for mining optimization | Semi-practical (runs on classical) |

#### Why It's Not Practical Now
1. **Hardware:** Current quantum computers (100-1000 qubits) are too small for geological modeling
2. **Error rates:** Quantum decoherence makes real-world geological calculations unreliable
3. **Cost:** Quantum cloud access costs $1-$10 per quantum second; no mining-specific advantage yet
4. **Timeline:** Practical quantum advantage for mining estimated at 10-15 years away
5. **Data requirements:** Geological data needs classical preprocessing that eliminates quantum advantage

#### What IS Useful Now
- **Quantum-inspired algorithms** (simulated annealing, quantum monte carlo) run on classical hardware
- **Variational quantum eigensolvers** for mineral chemistry (research stage only)

### 3.2 Recommendation
**Skip quantum computing entirely.** Focus on classical ML/AI which offers proven, practical, cost-effective solutions today. Revisit in 2035+.

---

## 4. EMERGING AI SYSTEMS USEFUL FOR MINING

### 4.1 Multi-Agent Systems for Mining Operations

| System/Approach | Description | Maturity |
|---|---|---|
| **CrewAI / AutoGen** (general) | Multi-agent orchestration frameworks. Can coordinate geological analysis, logistics, safety monitoring agents. | Production-ready frameworks; mining applications are custom builds |
| **Mine dispatch optimization** | Multi-agent systems for truck/shovel fleet management. Commercial: Modular Mining DISPATCH, Caterpillar MineStar. | Commercial ($100K+) |
| **Safety monitoring agents** | Multi-sensor fusion agents for hazard detection (ground stability, gas, equipment proximity) | Emerging |

### 4.2 Voice AI for Field Operations

| Solution | Description | Cost | Kenya Feasibility |
|---|---|---|---|
| **OpenAI Whisper** | Open-source speech-to-text. Can run on edge devices. Supports Swahili. | Free | ★★★★★ |
| **Google Speech-to-Text** | Cloud API with Swahili support | $0.006-0.024/min | ★★★★ |
| **Coqui STT** (open-source) | Offline speech recognition. Trainable for local languages. | Free | ★★★★ |
| **ElevenLabs / Bark** | Voice synthesis for reports and alerts | Free-$22/mo | ★★★ |
| **Custom voice interfaces** | Build voice-controlled field data entry using Whisper + LLM | Dev cost ~$5K | ★★★★★ |

**Application:** Voice-driven field logging — geologists speak observations, AI transcribes and structures into geological reports. Eliminates paperwork in remote field conditions.

### 4.3 Vision AI for Mineral Identification

| Solution | Description | Cost |
|---|---|---|
| **Rock Identifier Apps** (commercial) | Phone camera → mineral ID. Accuracy: 70-85%. | $5-$30/yr |
| **Custom CNN models** | Train on your specific ore types. Published accuracy: 90-97%. | Free (dev cost ~$2K-$10K) |
| **Hyperspectral + ML** | Combine portable spectrometer with ML for precise mineral ID. | $5K-$50K (hardware) |
| **Drone + computer vision** | Aerial rock type mapping using drone imagery + deep learning. | $2K-$20K |
| **Portable microscope + ML** | USB microscope + trained model for thin section analysis | $500-$2K |

### 4.4 LLMs for Geological Report Generation

| Approach | Description | Cost |
|---|---|---|
| **GPT-4 / Claude / DeepSeek** | General LLMs fine-tuned or prompted for geological report writing | $20-$200/mo API |
| **GeoLLM** (emerging) | Domain-specific geological language models being developed | Research stage |
| **RAG + geological knowledge base** | Build retrieval-augmented generation over geological literature, NI 43-101 reports, JORC codes | $5K dev cost |
| **Automated NI 43-101 / JORC drafting** | LLM-assisted generation of compliance reports from drill data | Custom build |
| **DARPA CRITICALMAAS NLP** | Text extraction from geological maps and reports (open-source tools) | Free |

### 4.5 Edge AI for Remote Mining Sites

| Solution | Description | Cost | Kenya Suitability |
|---|---|---|---|
| **NVIDIA Jetson Nano/Orin** | Edge AI computer. Runs ML models locally. Solar-powerable. | $150-$500 | ★★★★★ |
| **Raspberry Pi + Coral TPU** | Ultra-low-cost edge AI. Good for simple classification tasks. | $100-$200 | ★★★★★ |
| **Intel Movidius** | USB neural compute stick for vision AI on any device | $70-$100 | ★★★★ |
| **TensorFlow Lite** | Optimized ML models for mobile/edge deployment | Free | ★★★★★ |
| **ONNX Runtime** | Cross-platform ML inference. Runs on ARM processors. | Free | ★★★★★ |
| **Smart barrel IoT** (IEEE paper) | IoT-enabled sensors + edge AI for supply chain tracking in ASM | Research prototype | ★★★ |

### 4.6 Drone-Based Geological Survey

| Solution | Description | Cost |
|---|---|---|
| **DJI Mini 4 Pro** | Consumer drone with good camera. Legal in Kenya with KCAA permit. | $759-$1,000 |
| **DJI Mavic 3 Enterprise** | Professional survey drone with RTK positioning | $3,500-$5,000 |
| **OpenDroneMap** | Free photogrammetry software for 3D terrain models from drone photos | Free |
| **Pix4D** | Professional drone mapping software | $350/mo |
| **Agisoft Metashape** | 3D reconstruction from photos. Academic license available. | $179 (edu) |
| **DroneDeploy** | Cloud-based drone mapping platform | $500/mo |

**Key capability:** Drones + photogrammetry can create high-resolution 3D terrain models, detect geological structures, and map artisanal mine sites for as little as $1,000 total investment.

---

## 5. COST ANALYSIS

### 5.1 Budget Tiers for AI in Mining

#### Tier 1: Ultra-Low Budget ($500 - $5,000)
**Best for: Individual prospectors, small cooperatives**

| Item | Cost | Impact |
|---|---|---|
| QGIS + Google Earth Engine setup | Free | Satellite-based geological mapping |
| Sentinel-2 imagery analysis | Free | Hydrothermal alteration mapping |
| Python ML scripts (scikit-learn) | Free | Geochemical anomaly detection |
| OpenDroneMap + used DJI Mini | $300-$800 | 3D terrain modeling |
| Raspberry Pi + Coral TPU | $150 | Edge AI for field classification |
| Smartphone mineral ID apps | $30 | Quick field mineral identification |
| **TOTAL** | **$500-$1,000** | Basic AI-assisted exploration |

#### Tier 2: Small Operation Budget ($5,000 - $50,000)
**Best for: Small mining companies, cooperatives**

| Item | Cost | Impact |
|---|---|---|
| Everything in Tier 1 | $1,000 | Foundation |
| Professional drone (DJI Mavic 3E) | $5,000 | High-accuracy survey |
| NVIDIA Jetson Orin for edge AI | $500 | On-site real-time analysis |
| Portable XRF rental (3 months) | $3,000-$6,000 | Rapid geochemical analysis |
| Custom ML model development | $5,000-$15,000 | Ore grade estimation, mineral classification |
| GemPy 3D geological modeling | Free | Ore body visualization |
| GoldSpot consulting (1 project) | $50K | AI-powered drill targeting |
| **TOTAL** | **$15,000-$75,000** | Professional-grade AI exploration |

#### Tier 3: Medium Operation Budget ($50,000 - $500,000)
**Best for: Established small-medium miners**

| Item | Cost | Impact |
|---|---|---|
| Everything in Tier 2 | $75,000 | Foundation |
| Leapfrog geological modeling license | $15,000-$30,000/yr | Industry-standard 3D modeling |
| Custom computer vision system | $20,000-$50,000 | Conveyor belt ore sorting |
| Multi-sensor IoT deployment | $10,000-$50,000 | Real-time environmental monitoring |
| AI-powered drill targeting | $50,000-$100,000 | Optimized exploration drilling |
| LLM-powered reporting system | $5,000-$15,000 | Automated compliance reports |
| **TOTAL** | **$175,000-$320,000** | Comprehensive AI integration |

### 5.2 Ongoing Costs

| Item | Monthly Cost | Notes |
|---|---|---|
| Cloud computing (AWS/GCP) | $50-$500 | For ML model training and satellite data processing |
| Satellite imagery subscriptions | $0-$200 | Sentinel-2 is free; commercial imagery costs more |
| API costs (LLM, vision) | $20-$200 | For report generation and analysis |
| Drone maintenance & batteries | $50-$100 | Replacement parts, new batteries |
| Data connectivity (Starlink) | $50-$120/mo | Internet for remote sites |

---

## 6. FEASIBILITY FOR KENYA SMALL-SCALE OPERATION

### 6.1 Top 10 Most Practical Tools (Ranked)

| Rank | Tool | Cost | Impact | Feasibility |
|---|---|---|---|---|
| 1 | **Google Earth Engine + Sentinel-2** | Free | Satellite-based alteration mapping, land use monitoring | ★★★★★ |
| 2 | **QGIS + Python (scikit-learn)** | Free | Geochemical data analysis, prospectivity mapping | ★★★★★ |
| 3 | **earthrise-media/mining-detector** | Free | Detect artisanal gold mining sites from satellite | ★★★★★ |
| 4 | **Drone + OpenDroneMap** | $500-$5,000 | 3D terrain models, mine site mapping | ★★★★★ |
| 5 | **GemPy** | Free | 3D geological modeling from surface data | ★★★★ |
| 6 | **NVIDIA Jetson + TensorFlow Lite** | $150-$500 | Edge AI for real-time mineral classification | ★★★★ |
| 7 | **Whisper (voice AI)** | Free | Voice-driven field logging in Swahili | ★★★★ |
| 8 | **EIS Toolkit** | Free | Prospectivity mapping workflows | ★★★★ |
| 9 | **Custom YOLOv8 ore classifier** | $2K-$10K dev | Real-time ore type identification from camera | ★★★ |
| 10 | **Portable XRF + ML pipeline** | $3K-$6K rental | Rapid geochemical analysis with ML interpretation | ★★★ |

### 6.2 Specific Recommendations for Gold + Copper in Kenya

#### For Gold Exploration:
1. **Sentinel-2 hydrothermal alteration mapping** — Use band ratios (e.g., clay minerals, iron oxides) to identify gold-associated alteration halos. Free.
2. **earthrise-media/mining-detector** — Already trained on artisanal gold mine detection from satellite. Can identify existing mining activity patterns.
3. **Stream sediment geochemistry + ML** — Collect stream sediment samples, analyze with portable XRF, use random forest models to identify gold anomalies.

#### For Copper Exploration:
1. **EarthByte porphyry copper models** — Open-source spatio-temporal models for porphyry copper deposits. Can be adapted for East African copper belt.
2. **ASTER satellite data** — Free, good spectral resolution for copper-bearing minerals (malachite, chalcopyrite).
3. **Geophysical data integration** — Combine magnetic/gravity data with ML for copper target generation.

#### For Mine Operations:
1. **Drone surveying** — Weekly drone flights for stockpile volume estimation, pit progress tracking
2. **Edge AI safety monitoring** — Jetson-based system for equipment proximity detection, ground instability warnings
3. **Voice logging** — Field geologists speak observations in Swahili → Whisper transcribes → LLM structures into reports

### 6.3 Infrastructure Requirements

| Requirement | Solution | Cost |
|---|---|---|
| **Internet** | Starlink Mini | $50-$120/mo |
| **Power** | Solar panel + battery for edge devices | $200-$500 |
| **Computing** | Cloud (AWS/GCP) for training; Jetson for edge | $50-$200/mo |
| **Data storage** | External SSD + cloud backup | $100-$200 |
| **Connectivity** | Mesh network for mine site | $500-$2,000 |

### 6.4 Implementation Roadmap

**Phase 1 (Month 1-2): Foundation — $1,000**
- Set up QGIS + Google Earth Engine
- Download Sentinel-2 imagery for the concession area
- Run hydrothermal alteration mapping
- Deploy mining-detector to identify existing activity

**Phase 2 (Month 2-4): Field AI — $3,000**
- Acquire drone + set up OpenDroneMap
- Build 3D terrain model of concession
- Deploy Raspberry Pi/Jetson for field data collection
- Set up Whisper voice logging

**Phase 3 (Month 4-8): Analysis — $5,000-$15,000**
- Collect geochemical samples, analyze with portable XRF
- Train ML models on collected data
- Build prospectivity maps using EIS Toolkit or custom models
- Generate drill target recommendations

**Phase 4 (Month 8-12): Operations — $5,000-$20,000**
- Deploy edge AI for ore classification
- Implement drone-based stockpile monitoring
- Set up automated reporting with LLMs
- Iterate and improve models with new data

---

## 7. KEY ACADEMIC PAPERS & DATASETS

### Datasets
- **USGS Mineral Resources Data** — https://mrdata.usgs.gov/
- **Geoscience Australia datasets** — Multiple open datasets for ML training
- **Zenodo mineral exploration datasets** — Search for "mineral exploration" on zenodo.org
- **DARPA CRITICALMAAS training data** — https://data.usgs.gov/datacatalog/data/USGS:63a100d6d34e0de3a1f2794f

### Key Papers
- "Machine learning for ore grade estimation using Gaussian Processes" — Jafrasteh et al.
- "Comparison of ML methods for copper ore grade estimation" — Neurocomputing
- "Automated detection of artisanal gold mines in Sentinel-2 imagery" — earthrise-media
- "Spatio-temporal data mining of craton edge-related mineralisation" — Hojat-Shirmard et al.
- "Deep learning for mineral prospectivity mapping" — Multiple EarthByte publications
- Remote sensing review: "Landsat-8, Sentinel-2, ASTER for mineral exploration" — MDPI Remote Sensing

---

## 8. COMMUNITIES & SUPPORT

| Community | Description | Link |
|---|---|---|
| **Software Underground** | Open-source geoscience community | https://softwareunderground.org/ |
| **r/geology** | Reddit geology community | https://reddit.com/r/geology |
| **SEG (Society of Economic Geologists)** | Professional society with student programs | https://www.segweb.org/ |
| **GitHub: mineral-exploration topic** | 44+ public repositories | https://github.com/topics/mineral-exploration |
| **GitHub: geology topic** | 576+ public repositories | https://github.com/topics/geology |
| **OreGenesis Slack/Discord** | Emerging communities for ML in geology | Search LinkedIn/GitHub |

---

## SUMMARY

**For a small-scale gold+copper operation in rural Kenya, the most impactful and cost-effective AI tools are:**

1. **Free satellite analysis** (Google Earth Engine + Sentinel-2) — Identify alteration zones, map existing mining activity
2. **Open-source ML** (Python + scikit-learn) — Geochemical anomaly detection, prospectivity mapping
3. **Drone mapping** (OpenDroneMap) — 3D site models for under $1,000
4. **Edge AI** (Jetson/Raspberry Pi) — Real-time mineral classification in the field
5. **Voice AI** (Whisper) — Swahili field logging, eliminates paperwork

**Total minimum viable investment: $1,000-$5,000 for Phase 1-2**

**Quantum computing: Skip entirely. Not practical for 10+ years.**

**The gap between what major miners (Rio Tinto, BHP, KoBold) use and what's available to small operators has narrowed dramatically thanks to open-source tools, free satellite data, and affordable edge computing.**
