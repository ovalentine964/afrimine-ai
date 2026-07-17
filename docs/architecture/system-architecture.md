# AfriMine AI — System Architecture Document

**Version:** 1.0  
**Date:** 2026-07-18  
**Classification:** Technical Architecture — Production Blueprint

---

## Executive Summary

AfriMine AI is a platform that democratizes mining intelligence for African communities, providing geological analysis, mineral estimation, and operational decision-making capabilities previously available only to major foreign mining corporations. The system is designed from the ground up for **low-bandwidth, offline-first, mobile-first** deployment across Sub-Saharan Africa, with Kenya as the initial launch market.

**Core Design Principles:**
1. **Offline-first** — The system must function fully without internet connectivity
2. **Mobile-first** — Android-primary (80%+ market share in Kenya)
3. **Edge-heavy** — Process data on-site, sync when connected
4. **Data-sovereign** — All African data stays in Africa
5. **Small-team deployable** — MVP buildable by 5-8 engineers

---

## 1. Core Platform Architecture

### 1.1 Architectural Decision: Modular Monolith → Microservices

**Decision:** Start as a **modular monolith** with clearly defined module boundaries, designed to extract into microservices as scale demands.

**Rationale:**
- Small initial team (5-8) cannot operate a microservices mesh
- Network constraints in mining regions make service-to-service latency unreliable
- A monolith deploys as a single binary — ideal for edge/offline scenarios
- Module boundaries are preserved so extraction is mechanical, not architectural

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AfriMine AI — System Overview                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐    │
│  │  Mobile App  │   │  Web Portal  │   │  Hardware Interfaces │    │
│  │  (Android)   │   │  (React PWA) │   │  (XRF/Spectro/Drone)│    │
│  └──────┬───────┘   └──────┬───────┘   └──────────┬───────────┘    │
│         │                  │                       │                │
│         └──────────┬───────┴───────────────────────┘                │
│                    │                                                │
│         ┌──────────▼──────────┐                                    │
│         │   API Gateway /     │   ◄── Also acts as offline sync    │
│         │   Sync Engine       │       coordinator                   │
│         └──────────┬──────────┘                                    │
│                    │                                                │
│  ┌─────────────────▼─────────────────────────────────────────────┐  │
│  │              MODULAR MONOLITH (Go Binary)                     │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │  │
│  │  │ Geology  │ │ Samples  │ │ Market   │ │ User & Auth      │ │  │
│  │  │ Module   │ │ Module   │ │ Module   │ │ Module           │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘ │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │  │
│  │  │ AI/ML    │ │ Reports  │ │ Compli-  │ │ Notifications    │ │  │
│  │  │ Module   │ │ Module   │ │ ance Mod │ │ Module           │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘ │  │
│  └────────────────────────┬──────────────────────────────────────┘  │
│                           │                                         │
│  ┌────────────────────────▼──────────────────────────────────────┐  │
│  │                    DATA LAYER                                 │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │  │
│  │  │ PostGIS  │ │ TimescaleDB│ Redis   │ │ Object Storage   │ │  │
│  │  │ (Primary)│ │ (Time     │ │ (Cache) │ │ (MinIO - samples │ │  │
│  │  │          │ │  series)  │ │         │ │  & imagery)      │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              AI/ML INFRASTRUCTURE                             │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │  │
│  │  │ Model    │ │ Training │ │ Edge     │ │ Quantum          │ │  │
│  │  │ Registry │ │ Pipeline │ │ Inference│ │ Interface        │ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Cloud Infrastructure

**Primary Cloud:** Self-hosted in Nairobi (co-located or local provider like NodeAfrica/Sasai)  
**Secondary:** AWS Africa (Cape Town) for burst capacity and DR  
**Edge:** On-device + ruggedized edge nodes at mine sites

```
┌─────────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE TOPOLOGY                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐     ┌──────────────────────────────────────┐   │
│  │ MINE SITE   │     │           NAIROBI DC                 │   │
│  │ (Edge)      │     │                                      │   │
│  │ ┌─────────┐ │     │  ┌─────────┐  ┌─────────┐           │   │
│  │ │Edge Node│ │◄───►│  │ App     │  │ Database│           │   │
│  │ │(ARM/x86)│ │sync │  │ Servers │  │ Cluster │           │   │
│  │ └─────────┘ │     │  └─────────┘  └─────────┘           │   │
│  │ ┌─────────┐ │     │  ┌─────────┐  ┌─────────┐           │   │
│  │ │Local DB │ │     │  │ ML GPU  │  │ MinIO   │           │   │
│  │ │(SQLite) │ │     │  │ Nodes   │  │ Storage │           │   │
│  │ └─────────┘ │     │  └─────────┘  └─────────┘           │   │
│  │ ┌─────────┐ │     │                                      │   │
│  │ │Android  │ │     └──────────────┬───────────────────────┘   │
│  │ │Device   │ │                    │                            │
│  │ └─────────┘ │     ┌──────────────▼───────────────────────┐   │
│  └─────────────┘     │         AWS CAPE TOWN (DR/Burst)     │   │
│                       │  ┌─────────┐  ┌─────────┐           │   │
│  ┌─────────────┐      │  │ DR      │  │ ML      │           │   │
│  │ MINE SITE 2 │      │  │ Replica │  │ Training│           │   │
│  │ (Edge)      │◄────►│  └─────────┘  └─────────┘           │   │
│  └─────────────┘      └──────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Bandwidth Strategy:**
- Edge nodes sync via **compressible delta sync** (only changed records)
- Images captured at 720p by default, with optional 4K upload when bandwidth allows
- ML inference runs locally; only results + metadata sync upstream
- For completely offline sites: **sneakernet mode** — export to SD card, physically transfer

### 1.3 Offline-First Design

**Core Technology:** CRDTs (Conflict-free Replicated Data Types) + Event Sourcing

```
┌──────────────────────────────────────────────────────────┐
│                 OFFLINE SYNC PROTOCOL                     │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────┐    ┌─────────────┐    ┌─────────────────┐   │
│  │ Device  │    │ Local Event │    │ Sync Engine     │   │
│  │ Action  │───►│ Store       │───►│ (when online)   │   │
│  └─────────┘    │ (SQLite +   │    │                 │   │
│                 │  WAL)       │    │ • Delta detect  │   │
│                 └─────────────┘    │ • CRDT merge    │   │
│                                    │ • Conflict res  │   │
│                                    │ • Compressed    │   │
│                                    │   upload        │   │
│                                    └────────┬────────┘   │
│                                             │             │
│                                    ┌────────▼────────┐   │
│                                    │ Central DB      │   │
│                                    │ (event-sourced) │   │
│                                    └─────────────────┘   │
│                                                           │
│  Conflict Resolution: Last-Write-Wins with field-level   │
│  merge for non-conflicting changes. Geological data      │
│  conflicts (e.g., two geologists editing same sample)    │
│  surface as "review needed" in the UI.                   │
└──────────────────────────────────────────────────────────┘
```

**Local Storage Stack on Android:**
- **Room/SQLite** for structured data
- **MMKV** for key-value config
- **WorkManager** for background sync scheduling
- **DataStore** for user preferences

### 1.4 Mobile Architecture (Android Primary)

```
┌─────────────────────────────────────────────────────────────┐
│                 ANDROID APP ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   UI Layer (Jetpack Compose)             │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │ │
│  │  │Dashboard │ │ Sampling │ │ Reports  │ │ Investor   │ │ │
│  │  │Screen    │ │ Workflow │ │ Viewer   │ │ Portal     │ │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │ │
│  └────────────────────────┬────────────────────────────────┘ │
│                           │                                   │
│  ┌────────────────────────▼────────────────────────────────┐ │
│  │              Domain Layer (Kotlin)                       │ │
│  │  Use Cases / Business Logic / State Management          │ │
│  └────────────────────────┬────────────────────────────────┘ │
│                           │                                   │
│  ┌────────────────────────▼────────────────────────────────┐ │
│  │              Data Layer                                  │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │ │
│  │  │ Local DB │ │ API      │ │ Camera   │ │ ML Kit /   │ │ │
│  │  │ (Room)   │ │ Client   │ │ Module   │ │ TF Lite    │ │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ON-DEVICE ML (TensorFlow Lite):                             │
│  • Ore classification model (~15MB)                          │
│  • Sample quality check                                      │
│  • Basic geological feature detection                        │
│  • Offline report generation templates                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 1.5 Edge Computing Architecture

**Edge Node Specs (Nairobi-assembled ruggedized units):**
- **Hardware:** Raspberry Pi 5 (8GB) or Jetson Nano for ML workloads
- **OS:** Ubuntu Server 22.04 LTS (ARM64)
- **Storage:** 512GB NVMe SSD (expandable)
- **Connectivity:** 4G/LTE modem + WiFi + Ethernet
- **Power:** 12V DC (solar-compatible)
- **Enclosure:** IP65-rated, operating temp -10°C to 50°C
- **Cost target:** <$300 per node

**Edge Software Stack:**
```
┌─────────────────────────────────────────────┐
│            EDGE NODE SOFTWARE                │
├─────────────────────────────────────────────┤
│                                              │
│  ┌─────────────────────────────────────────┐ │
│  │  AfriMine Edge Agent (Go binary)        │ │
│  │  • Local API server (port 8080)         │ │
│  │  • Sync client                          │ │
│  │  • Device manager                       │ │
│  └──────────────┬──────────────────────────┘ │
│                 │                             │
│  ┌──────────────▼──────────────────────────┐ │
│  │  Local Services                         │ │
│  │  • PostgreSQL + PostGIS                 │ │
│  │  • MinIO (local object store)           │ │
│  │  • Redis (cache + job queue)            │ │
│  │  • TFLite Runtime                       │ │
│  │  • Node-RED (hardware integration)      │ │
│  └─────────────────────────────────────────┘ │
│                                              │
│  ┌─────────────────────────────────────────┐ │
│  │  Hardware Drivers                       │ │
│  │  • XRF serial/USB interface             │ │
│  │  • Spectrometer API                     │ │
│  │  • Drone telemetry (MAVLink)            │ │
│  │  • Camera capture (USB/CSI)             │ │
│  └─────────────────────────────────────────┘ │
│                                              │
└─────────────────────────────────────────────┘
```

---

## 2. AI/ML Pipeline

### 2.1 Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AI/ML PIPELINE ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐                                                         │
│  │ DATA INPUTS  │                                                        │
│  └──────┬──────┘                                                         │
│         │                                                                │
│  ┌──────▼──────────┐  ┌──────────────────┐  ┌──────────────────────┐    │
│  │ Image Data      │  │ Spectral Data    │  │ Geological Survey    │    │
│  │ (camera/drone)  │  │ (XRF/spectro)    │  │ Data (maps/logs)    │    │
│  └──────┬──────────┘  └────────┬─────────┘  └──────────┬───────────┘    │
│         │                      │                        │                │
│  ┌──────▼──────────┐  ┌────────▼─────────┐  ┌──────────▼───────────┐    │
│  │ Image           │  │ Spectral         │  │ Geo-spatial          │    │
│  │ Preprocessing   │  │ Normalization    │  │ Feature Extraction   │    │
│  │ • Resize/Toss   │  │ • Baseline corr  │  │ • Topology           │    │
│  │ • Augmentation  │  │ • Noise filter   │  │ • Stratigraphy       │    │
│  │ • Feature detect│  │ • Element ID     │  │ • Historical matches │    │
│  └──────┬──────────┘  └────────┬─────────┘  └──────────┬───────────┘    │
│         │                      │                        │                │
│         └──────────────────────┼────────────────────────┘                │
│                                │                                         │
│                    ┌───────────▼───────────┐                             │
│                    │  FUSION ENGINE        │                             │
│                    │  (Multi-modal model)  │                             │
│                    │                       │                             │
│                    │  Combines:            │                             │
│                    │  • Visual features    │                             │
│                    │  • Chemical compos.   │                             │
│                    │  • Geo-spatial context│                             │
│                    └───────────┬───────────┘                             │
│                                │                                         │
│              ┌─────────────────┼─────────────────┐                      │
│              │                 │                  │                      │
│     ┌────────▼──────┐  ┌──────▼───────┐  ┌──────▼───────┐              │
│     │ Ore           │  │ Geological   │  │ Resource     │              │
│     │ Classification│  │ Estimation   │  │ Estimation   │              │
│     │ Model         │  │ Model        │  │ Model        │              │
│     │               │  │              │  │              │              │
│     │ • Ore type    │  │ • Formation  │  │ • Tonnage    │              │
│     │ • Grade est.  │  │ • Deposit    │  │ • Grade      │              │
│     │ • Quality     │  │   type       │  │ • Confidence │              │
│     └───────────────┘  └──────────────┘  └──────────────┘              │
│                                │                                         │
│                    ┌───────────▼───────────┐                             │
│                    │  REPORT GENERATOR     │                             │
│                    │  (NLP / Templates)    │                             │
│                    └───────────┬───────────┘                             │
│                                │                                         │
│              ┌─────────────────┼─────────────────┐                      │
│     ┌────────▼──────┐  ┌──────▼───────┐  ┌──────▼───────┐              │
│     │ Technical     │  │ Investor     │  │ Regulatory   │              │
│     │ Report        │  │ Summary      │  │ Filing       │              │
│     └───────────────┘  └──────────────┘  └──────────────┘              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Mineral Sample Analysis Pipeline

**Stage 1: Image Capture & Processing**
```
Input: Photo from phone camera or drone
  │
  ├── Quality gate: blur detection, lighting check, scale reference
  │   └── Reject + "retake guidance" if quality < threshold
  │
  ├── On-device pre-processing (TFLite):
  │   ├── Auto-crop to sample area
  │   ├── Color calibration (using reference card)
  │   └── Metadata extraction (GPS, timestamp, device)
  │
  └── Upload to edge node (compressed, ~200KB per image)
```

**Stage 2: Feature Extraction (Edge/Cloud)**
```
Input: Pre-processed image + metadata
  │
  ├── CNN Feature Extractor (MobileNetV3 → custom head)
  │   ├── Texture features (crystal structure, grain size)
  │   ├── Color distribution (mineral-specific signatures)
  │   ├── Morphological features (cleavage, fracture patterns)
  │   └── Vein/inclusion detection
  │
  └── Output: 128-dimensional feature vector
```

**Stage 3: Classification & Estimation**
```
Input: Feature vector + XRF data (if available) + geo-spatial context
  │
  ├── Ensemble Model:
  │   ├── Random Forest (fast, interpretable — runs on edge)
  │   ├── XGBoost (accurate — runs on edge)
  │   └── Neural Network (best accuracy — runs on cloud)
  │
  ├── Output:
  │   ├── Mineral type + confidence
  │   ├── Estimated grade (with uncertainty bounds)
  │   ├── Quality classification
  │   └── Recommended next steps
  │
  └── Human-in-the-loop: Geologist review queue for low-confidence results
```

### 2.3 Computer Vision for Ore Classification

**Model Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│              ORE CLASSIFICATION MODEL                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Backbone: EfficientNet-B2 (pretrained on ImageNet)          │
│  Fine-tuned on: African mineral dataset                      │
│                                                              │
│  Input: 260×260×3 RGB image                                  │
│  │                                                           │
│  ├── EfficientNet-B2 backbone (frozen for first 10 epochs)   │
│  │   └── Output: 1408-dim feature vector                     │
│  │                                                           │
│  ├── Attention Module (squeeze-excitation)                    │
│  │   └── Focus on mineral-relevant regions                   │
│  │                                                           │
│  ├── Multi-head Classification:                              │
│  │   ├── Head 1: Mineral type (20 classes)                   │
│  │   ├── Head 2: Grade range (5 classes)                     │
│  │   └── Head 3: Quality score (regression)                  │
│  │                                                           │
│  └── Output: {type, grade, quality, confidence, attention_map}│
│                                                              │
│  Model size: ~25MB (TFLite quantized)                        │
│  Inference time: ~80ms on Pixel 6a                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Training Data Strategy (see Section 2.6 for details):**
- Transfer learning from global mineral datasets
- Synthetic data augmentation
- Active learning from field captures
- Federated learning across mine sites

### 2.4 Geological Estimation Models

**Resource Estimation using Geostatistics + ML:**

```
┌─────────────────────────────────────────────────────────────┐
│           GEOLOGICAL ESTIMATION PIPELINE                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Input: Sample points with {GPS, depth, grade, mineral_type} │
│  │                                                           │
│  ├── Step 1: Variogram Analysis                              │
│  │   ├── Compute empirical variograms                        │
│  │   ├── Fit theoretical models (spherical, exponential)     │
│  │   └── Cross-validation for model selection                │
│  │                                                           │
│  ├── Step 2: Spatial Interpolation                            │
│  │   ├── Kriging (Ordinary Kriging for grade estimation)     │
│  │   ├── IDW (fallback when insufficient data for kriging)   │
│  │   └── ML-enhanced: XGBoost residuals on kriging estimates │
│  │                                                           │
│  ├── Step 3: Block Model Generation                          │
│  │   ├── Divide deposit into blocks (e.g., 10m × 10m × 5m)  │
│  │   ├── Estimate grade for each block                       │
│  │   └── Assign confidence scores                            │
│  │                                                           │
│  ├── Step 4: Resource Classification                         │
│  │   ├── Measured: <50m spacing, high confidence             │
│  │   ├── Indicated: 50-100m spacing, moderate confidence     │
│  │   └── Inferred: >100m spacing, low confidence             │
│  │                                                           │
│  └── Output: 3D block model + resource statement             │
│       (compliant with JORC/SAMREC/NI 43-101 standards)       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.5 Multi-Agent System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MULTI-AGENT SYSTEM                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    ORCHESTRATOR AGENT                            │ │
│  │  • Receives user requests                                       │ │
│  │  • Decomposes into sub-tasks                                    │ │
│  │  • Routes to specialist agents                                  │ │
│  │  • Aggregates results                                           │ │
│  └──────────────────────┬──────────────────────────────────────────┘ │
│                         │                                            │
│    ┌────────────────────┼────────────────────────┐                   │
│    │                    │                        │                   │
│  ┌─▼──────────┐  ┌─────▼──────────┐  ┌─────────▼────────┐          │
│  │ SAMPLING   │  │ ANALYSIS       │  │ REPORTING        │          │
│  │ AGENT      │  │ AGENT          │  │ AGENT            │          │
│  │            │  │                │  │                   │          │
│  │ • Plan     │  │ • Classify ore │  │ • Generate        │          │
│  │   sampling │  │ • Estimate     │  │   technical       │          │
│  │   routes   │  │   grade        │  │   reports         │          │
│  │ • Optimize │  │ • Identify     │  │ • Investor        │          │
│  │   coverage │  │   anomalies    │  │   summaries       │          │
│  │ • Field    │  │ • Cross-ref    │  │ • Regulatory      │          │
│  │   guidance │  │   databases    │  │   filings         │          │
│  └────────────┘  └────────────────┘  └──────────────────┘          │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  SUPPORTING AGENTS                                               │ │
│  │                                                                  │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │ │
│  │  │ MARKET       │  │ COMPLIANCE   │  │ QUALITY ASSURANCE    │  │ │
│  │  │ AGENT        │  │ AGENT        │  │ AGENT                │  │ │
│  │  │              │  │              │  │                       │  │ │
│  │  │ • Price feeds│  │ • Check regs │  │ • Validate data      │  │ │
│  │  │ • Valuation  │  │ • Auto-file  │  │ • Flag anomalies     │  │ │
│  │  │ • Forecasts  │  │ • Audit trail│  │ • Confidence scoring │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  AGENT COMMUNICATION:                                                │
│  • Message bus: Redis Streams (lightweight, embedded)                │
│  • Protocol: JSON-RPC over message bus                               │
│  • State: Each agent owns its state; shared via event sourcing       │
│  • Failure: Agents are stateless processors; replay from events      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.6 Training Models with Limited African Geological Data

This is the hardest technical challenge. Here's the multi-pronged strategy:

**Strategy 1: Transfer Learning + Domain Adaptation**
```
Global Mineral Dataset (100K+ samples)
  │
  ├── Pre-train backbone (EfficientNet) on global data
  │   └── Learns: textures, colors, crystal structures
  │
  ├── Fine-tune on available African samples (start: ~500-2000)
  │   ├── Freeze backbone, train classification heads
  │   ├── Gradually unfreeze top layers
  │   └── Use aggressive augmentation
  │
  └── Domain adaptation: Adversarial training to reduce
      bias toward non-African geological formations
```

**Strategy 2: Synthetic Data Generation**
```
  ├── Geological Simulation
  │   ├── Use known African geological parameters
  │   ├── Simulate mineral formation processes
  │   └── Generate synthetic sample images
  │
  ├── GAN-based Augmentation
  │   ├── Train StyleGAN on real African samples
  │   ├── Generate variations preserving geological realism
  │   └── Expert geologist validation of synthetic samples
  │
  └── Physics-based Rendering
      ├── 3D mineral models with realistic lighting
      ├── Render from multiple angles
      └── Simulate weathering and surface effects
```

**Strategy 3: Active Learning Loop**
```
  ┌─────────────┐     ┌─────────────┐     ┌──────────────┐
  │ Model makes │────►│ Low         │────►│ Sent to      │
  │ prediction  │     │ confidence? │     │ geologist    │
  └─────────────┘     └──────┬──────┘     └──────┬───────┘
                             │ No                  │
                       ┌─────▼─────┐        ┌─────▼──────┐
                       │ Accept    │        │ Expert     │
                       │ result    │        │ labels +   │
                       └───────────┘        │ adds to    │
                                            │ training   │
                                            └────────────┘

  Each field interaction improves the model.
  Target: 90% accuracy within 12 months of deployment.
```

**Strategy 4: Federated Learning**
```
  Mine Site A          Mine Site B          Mine Site C
  ┌──────────┐        ┌──────────┐        ┌──────────┐
  │ Local    │        │ Local    │        │ Local    │
  │ Training │        │ Training │        │ Training │
  └────┬─────┘        └────┬─────┘        └────┬─────┘
       │                   │                   │
       │   Gradients only  │                   │
       │   (no raw data)   │                   │
       └───────────┬───────┴───────────────────┘
                   │
           ┌───────▼───────┐
           │ Central Model │
           │ Aggregation   │
           │ (Nairobi)     │
           └───────────────┘

  Benefits:
  • Data stays at mine site (data sovereignty)
  • Model improves from all sites' experience
  • Works with intermittent connectivity
```

---

## 3. Quantum Computing Integration

### 3.1 Where Quantum Adds Value NOW vs Future

```
┌─────────────────────────────────────────────────────────────────────┐
│                QUANTUM COMPUTING READINESS MATRIX                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  VALUE │                                                             │
│  HIGH  │                                    ┌─────────────────────┐  │
│        │                                    │ Quantum Optimization│  │
│        │                                    │ (mine planning,     │  │
│        │                                    │  logistics)         │  │
│        │                              ┌─────┴───────────────────┐ │  │
│        │                              │ Quantum Chemistry       │ │  │
│        │                              │ (mineral processing     │ │  │
│        │                              │  simulation)            │ │  │
│        │                        ┌─────┴───────────────────────┐ │  │
│        │                        │ Quantum ML                  │ │  │
│  MED   │                        │ (kernel methods, feature    │ │  │
│        │                        │  space exploration)         │ │  │
│        │                  ┌─────┴───────────────────────────┐ │  │
│        │                  │ Quantum Monte Carlo             │ │  │
│        │                  │ (resource estimation)           │ │  │
│        │            ┌─────┴───────────────────────────────┐ │  │
│  LOW   │            │ Current NISQ devices                │ │  │
│        │            │ (limited practical value today)      │ │  │
│        │            └─────────────────────────────────────┘ │  │
│        └──────────────────────────────────────────────────────────  │
│           NOW          2-3 YEARS        5+ YEARS      TIME         │
│           (2026)       (2028-29)        (2031+)                    │
│                                                                      │
│  PRAGMATIC DECISION: Design for quantum-ready, deploy classical     │
│  today. Use quantum cloud services for specific optimization        │
│  problems where they demonstrably outperform classical.             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Quantum-Ready Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              QUANTUM-READY ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                 APPLICATION LAYER                                │ │
│  │  Problem Definition → Abstraction → Solver Selection            │ │
│  └────────────────────────┬────────────────────────────────────────┘ │
│                           │                                          │
│  ┌────────────────────────▼────────────────────────────────────────┐ │
│  │                 SOLVER ABSTRACTION LAYER                         │ │
│  │                                                                  │ │
│  │  ┌──────────────────────────────────────────────────────────┐   │ │
│  │  │  Problem Format: Standard mathematical formulation       │   │ │
│  │  │  (QUBO, Ising, LP, etc.)                                │   │ │
│  │  └──────────────────────┬───────────────────────────────────┘   │ │
│  │                         │                                        │ │
│  │         ┌───────────────┼───────────────┐                       │ │
│  │         │               │               │                       │ │
│  │  ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐               │ │
│  │  │ Classical   │ │ Quantum     │ │ Hybrid      │               │ │
│  │  │ Solver      │ │ Cloud       │ │ Solver      │               │ │
│  │  │             │ │             │ │             │               │ │
│  │  │ • Gurobi   │ │ • IBM Qiskit│ │ • Classical │               │ │
│  │  │ • OR-Tools │ │ • AWS       │ │   pre/post  │               │ │
│  │  │ • Custom   │ │   Braket    │ │   processing│               │ │
│  │  │   heurist. │ │ • Azure Q   │ │ • Quantum   │               │ │
│  │  │            │ │ • D-Wave    │ │   core loop │               │ │
│  │  └────────────┘ └─────────────┘ └─────────────┘               │ │
│  │                                                                  │ │
│  │  RUNTIME DECISION LOGIC:                                         │ │
│  │  if problem_size < quantum_advantage_threshold:                  │ │
│  │      use classical_solver()                                      │ │
│  │  elif quantum_hardware_available AND problem_fits_hardware:      │ │
│  │      use quantum_solver()                                        │ │
│  │  else:                                                           │ │
│  │      use hybrid_solver()                                         │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.3 Hybrid Classical-Quantum Workflows

**Workflow 1: Mine Planning Optimization (Near-term Quantum Value)**

```
┌─────────────────────────────────────────────────────────────┐
│         HYBRID QUANTUM-CLASSICAL MINE PLANNING               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Classical Phase:                                            │
│  ├── Generate block model from geological data               │
│
│  ├── Define constraints (environmental, legal, equipment)    │
│  └── Formulate as QUBO problem                               │
│                                                              │
│  Quantum Phase:                                              │
│  ├── Map QUBO → Ising model                                  │
│  ├── Run on D-Wave/quantum annealer                          │
│  │   (or simulate on classical for small problems)           │
│  └── Extract candidate solutions                             │
│                                                              │
│  Classical Phase:                                            │
│  ├── Validate solutions against all constraints              │
│  ├── Rank by NPV (Net Present Value)                         │
│  ├── Refine top candidates with local search                 │
│  └── Present optimized mine plan                             │
│                                                              │
│  WHEN THIS MATTERS: Complex multi-pit, multi-period         │
│  scheduling with 1000+ blocks. Classical solvers struggle;  │
│  quantum annealing shows advantage at ~500+ variables.      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Workflow 2: Quantum-Enhanced Resource Estimation**

```
  Problem: Estimate mineral grade across a deposit from sparse samples
  
  Classical approach: Kriging (assumes Gaussian fields)
  
  Quantum-enhanced approach:
  ├── Encode geological field as quantum state
  ├── Use quantum kernel methods for non-Gaussian fields
  ├── Quantum Monte Carlo for uncertainty quantification
  └── Classical post-processing for practical outputs
  
  Practical benefit: Better uncertainty estimates for
  non-standard deposit types common in African geology
  (e.g., Greenstone belt gold, lateritic nickel)
```

### 3.4 Specific Quantum Algorithms for Mineral Estimation

| Algorithm | Use Case | Quantum Provider | Practical Today? |
|-----------|----------|-----------------|------------------|
| QAOA (Quantum Approximate Optimization) | Mine scheduling, pit optimization | IBM Qiskit, AWS Braket | Partially — small problems |
| VQE (Variational Quantum Eigensolver) | Mineral processing chemistry simulation | IBM, Google | Research stage |
| Quantum Kernel Methods | Ore classification with complex feature spaces | AWS Braket, PennyLane | Experimental |
| Quantum Monte Carlo | Resource estimation uncertainty | D-Wave, classical simulators | Classical simulation useful now |
| Grover's Search | Database search for geological analogues | IBM, Google | Not practical yet (too few qubits) |
| Quantum Annealing | Combinatorial optimization (logistics, scheduling) | D-Wave | **Yes — for specific problems** |

**Implementation Decision:** For MVP, implement the solver abstraction layer with classical solvers only. Add quantum cloud integration in Phase 3 when use cases are validated with real data.

---

## 4. Data Architecture

### 4.1 Data Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CORE DATA MODEL                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐       ┌──────────────┐       ┌───────────────┐     │
│  │ CONCESSION  │ 1───N │ SURVEY       │ 1───N │ SAMPLE        │     │
│  │             │       │              │       │               │     │
│  │ id          │       │ id           │       │ id            │     │
│  │ name        │       │ concession_id│       │ survey_id     │     │
│  │ geometry    │       │ date         │       │ location (GPS)│     │
│  │ owner_id    │       │ type         │       │ depth         │     │
│  │ license_no  │       │ geologist_id │       │ image_urls[]  │     │
│  │ status      │       │ method       │       │ xrf_data      │     │
│  │ minerals[]  │       │ notes        │       │ spectro_data  │     │
│  └─────────────┘       └──────────────┘       │ classification│     │
│                                               │ grade_estimate│     │
│                                               │ confidence    │     │
│                                               │ reviewed      │     │
│                                               └───────────────┘     │
│                                                                      │
│  ┌─────────────┐       ┌──────────────┐       ┌───────────────┐     │
│  │ BLOCK_MODEL │       │ RESOURCE_    │       │ REPORT        │     │
│  │             │       │ STATEMENT    │       │               │     │
│  │ id          │       │ id           │       │ id            │     │
│  │ concession_id│      │ concession_id│       │ type          │     │
│  │ block_x/y/z │       │ measured_ton │       │ concession_id │     │
│  │ grade       │       │ indicated_ton│       │ generated_at  │     │
│  │ mineral     │       │ inferred_ton │       │ content       │     │
│  │ confidence  │       │ grades       │       │ format        │     │
│  │ method      │       │ classification│      │ status        │     │
│  └─────────────┘       └──────────────┘       └───────────────┘     │
│                                                                      │
│  ┌─────────────┐       ┌──────────────┐                             │
│  │ USER        │       │ MARKET_PRICE │                             │
│  │             │       │              │                             │
│  │ id          │       │ id           │                             │
│  │ role        │       │ mineral      │                             │
│  │ org         │       │ price_usd    │                             │
│  │ permissions │       │ source       │                             │
│  │ locale      │       │ timestamp    │                             │
│  └─────────────┘       └──────────────┘                             │
│                                                                      │
│  SPATIAL INDEX: PostGIS geometry columns on all location-bearing     │
│  tables. R-tree indexes for spatial queries.                         │
│                                                                      │
│  TIME SERIES: TimescaleDB hypertables for market prices, sensor      │
│  readings, and model performance metrics.                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Storage Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    STORAGE ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  TIER 1: HOT DATA (PostgreSQL + PostGIS)                             │
│  ├── Active concessions, recent samples, current users               │
│  ├── Full ACID, spatial queries, JSON support                        │
│  ├── ~100GB initial, grows ~10GB/year                                │
│  └── Backup: Daily pg_dump → MinIO, weekly full backup               │
│                                                                      │
│  TIER 2: WARM DATA (TimescaleDB extension on PostgreSQL)             │
│  ├── Market prices (5-min granularity), sensor data                  │
│  ├── Automatic compression after 30 days                             │
│  ├── Continuous aggregates for dashboards                            │
│  └── Retention: 5 years raw, indefinite aggregates                   │
│                                                                      │
│  TIER 3: COLD DATA (MinIO / S3-compatible)                           │
│  ├── Sample images, drone imagery, spectral files                    │
│  ├── ML model artifacts, training datasets                           │
│  ├── Report PDFs, exported datasets                                  │
│  ├── Lifecycle: Move to cold storage after 90 days                   │
│  └── Encryption at rest (AES-256)                                    │
│                                                                      │
│  TIER 4: EDGE CACHE (SQLite on device / PostgreSQL on edge node)     │
│  ├── Subset of hot data relevant to current site                     │
│  ├── Last 30 days of samples for current user                        │
│  ├── Cached report templates                                         │
│  └── Syncs to Tier 1 when connectivity available                     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.3 Market Price Integration

```
┌─────────────────────────────────────────────────────────────┐
│              MARKET PRICE PIPELINE                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Data Sources (prioritized):                                 │
│  ├── 1. LME (London Metal Exchange) API — metals             │
│  ├── 2. Kitco API — gold/silver spot prices                  │
│  ├── 3. Mining.com RSS — news + price updates                │
│  ├── 4. LBMA — precious metals fixings                      │
│  └── 5. Bloomberg Terminal (if client has access)            │
│                                                              │
│  Collection:                                                 │
│  ├── Cron job every 15 minutes during market hours           │
│  ├── Store in TimescaleDB hypertable                         │
│  ├── Compute: SMA, EMA, volatility, trend indicators         │
│  └── Alert triggers: price moves >2% in 1 hour              │
│                                                              │
│  Minerals Tracked:                                           │
│  ├── Gold (XAU), Silver (XAG), Platinum (XPT)               │
│  ├── Copper, Cobalt, Manganese, Titanium                     │
│  ├── Rare Earths (Nd, Dy — for tech mineral deposits)        │
│  └── Regional: Coltan (DRC), Graphite (Mozambique)           │
│                                                              │
│  API: REST endpoint returning current + historical prices    │
│  Cache: Redis with 5-min TTL for real-time, 1-hour for Hx   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.4 Regulatory Compliance Data

```
┌─────────────────────────────────────────────────────────────┐
│           REGULATORY DATA ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Kenya Mining Act 2016 Requirements:                         │
│  ├── License management (exploration, mining, dealer)        │
│  ├── Environmental impact assessments                        │
│  ├── Annual production reports                               │
│  ├── Royalty calculations (variable by mineral)              │
│  └── Community benefit agreements                            │
│                                                              │
│  Data Model:                                                 │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ compliance_filing                                    │     │
│  │ ├── id, concession_id, filing_type                   │     │
│  │ ├── deadline, submitted_at, status                   │     │
│  │ ├── document_url (MinIO)                             │     │
│  │ ├── regulatory_body (e.g., "Kenya Mining Ministry")  │     │
│  │ └── auto_generated (boolean)                         │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  Automation:                                                 │
│  ├── Auto-generate quarterly production reports              │
│  ├── Royalty calculator from production data + market prices │
│  ├── Deadline reminders (30/14/7 day alerts)                 │
│  └── Template-based filing for standard forms                │
│                                                              │
│  Multi-jurisdiction:                                         │
│  ├── Pluggable regulatory modules per country                │
│  ├── Kenya (Phase 1), Tanzania, Ghana, DRC (Phase 2+)       │
│  └── Each module defines: deadlines, forms, calculations     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. User Experience

### 5.1 Dashboard for Landowners

```
┌─────────────────────────────────────────────────────────────────────┐
│  AfriMine AI    🌍 Your Land    📊 Reports    ⚙️ Settings          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Welcome, James 🇰🇪                                                  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  YOUR CONCESSION: Kiambu Gold Plot #247                     │    │
│  │                                                              │    │
│  │  ┌─────────────────────────────────────────────────────┐    │    │
│  │  │                                                     │    │    │
│  │  │            [Interactive Map View]                    │    │    │
│  │  │     Shows concession boundary, sample points,       │    │    │
│  │  │     heat map of estimated mineral density            │    │    │
│  │  │                                                     │    │    │
│  │  └─────────────────────────────────────────────────────┘    │    │
│  │                                                              │    │
│  │  📊 ESTIMATED VALUE                                         │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │    │
│  │  │ Gold     │ │ Grade    │ │ Est.     │ │ Confidence│       │    │
│  │  │ ⚡ Detected│ │ 3.2 g/t  │ │ $2.1M    │ │ ██████░░ │       │    │
│  │  │          │ │          │ │          │ │ 72%       │       │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │    │
│  │                                                              │    │
│  │  📋 NEXT STEPS                                              │    │
│  │  ✅ 12 samples collected                                    │    │
│  │  ⏳ 3 samples pending analysis                              │    │
│  │  🔲 Need 8 more samples for "Indicated" classification     │    │
│  │  📅 Next survey: July 25 (scheduled)                       │    │
│  │                                                              │    │
│  │  💰 CURRENT GOLD PRICE: $2,345/oz (+1.2% today)            │    │
│  │                                                              │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  [📷 Take Sample]  [📄 Get Report]  [💬 Talk to Geologist]          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

Design principles:
• Visual, not text-heavy — icons, colors, progress bars
• Localized: English + Swahili (Phase 1), more languages later
• Touch-friendly: Large tap targets, swipe gestures
• Works offline: Shows last-synced data with "offline" indicator
• SMS fallback: Key alerts can go via SMS when no data
```

### 5.2 Technical Interface for Geologists

```
┌─────────────────────────────────────────────────────────────────────┐
│  AfriMine Pro   🔬 Analysis   📐 Modeling   📊 Data   📝 Reports   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  CONCESSION: Kiambu Gold Plot #247         Status: Exploration      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                                                               │   │
│  │  SAMPLE REGISTRY                    FILTER: All | Pending |   │   │
│  │  ────────────────────────────────────────────────────────     │   │
│  │  ID      │ Location      │ Type  │ Grade  │Confidence│Review │   │
│  │  ────────────────────────────────────────────────────────     │   │
│  │  KI-001  │ -1.123,36.789 │ Ore   │ 4.1g/t │  89%    │ ✅    │   │
│  │  KI-002  │ -1.124,36.790 │ Waste │ 0.2g/t │  91%    │ ✅    │   │
│  │  KI-003  │ -1.125,36.791 │ Ore   │ 2.8g/t │  67%    │ ⏳    │   │
│  │  KI-004  │ -1.125,36.792 │ ???   │ 1.5g/t │  45%    │ 🔲    │   │
│  │  ────────────────────────────────────────────────────────     │   │
│  │                                                               │   │
│  │  AI CLASSIFICATION (KI-004):                                  │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │ Primary:   Gold-bearing quartz vein (62% confidence)   │  │   │
│  │  │ Secondary: Lateritic overprint (23%)                   │  │   │
│  │  │ Suggested: Collect XRF data for confirmation           │  │   │
│  │  │                                                        │  │   │
│  │  │ [View Image] [View Spectral] [Override Classification] │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  │  BLOCK MODEL:                                                 │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │ 3D cross-section viewer (Three.js)                     │  │   │
│  │  │ Color-coded by grade: ■ High ■ Med ■ Low ■ Waste       │  │   │
│  │  │ Block size: 10m × 10m × 5m                             │  │   │
│  │  │ [Export Block Model] [Generate Section] [Kriging Params]│  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  KEYBOARD SHORTCUTS: S=Samples, M=Model, R=Report, /=Search        │
│  API ACCESS: /api/v1/docs (Swagger UI)                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 Investor Portal

```
┌─────────────────────────────────────────────────────────────────────┐
│  AfriMine Investor Portal    📈 Portfolio   📄 Reports   🔔 Alerts │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  PORTFOLIO OVERVIEW                                                  │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  Total Portfolio Value:    $12.4M                            │    │
│  │  Concessions:              3 active                          │    │
│  │  Resource Classification:  1 Measured, 1 Indicated, 1 Inf.   │    │
│  │  Year-over-Year:           +34% estimated value              │    │
│  │                                                              │    │
│  │  ┌──────────────────────────────────────────────────────┐   │    │
│  │  │  [Value over time chart - 12 months]                 │   │    │
│  │  │   📈                                                   │   │    │
│  │  └──────────────────────────────────────────────────────┘   │    │
│  │                                                              │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  CONCESSION DETAILS                                                  │
│  ┌───────────┬──────────┬──────────┬──────────┬──────────────────┐  │
│  │ Name      │ Mineral  │ Resource │ Grade    │ Est. Value       │  │
│  ├───────────┼──────────┼──────────┼──────────┼──────────────────┤  │
│  │ Kiambu #247│ Gold    │ 12.4t    │ 3.2 g/t  │ $2.1M            │  │
│  │ Nakuru #89 │ Copper  │ 45.2t    │ 1.8%     │ $8.7M            │  │
│  │ Turkana #15│ Lithium │ Inferred │ 0.9% Li₂O│ $1.6M            │  │
│  └───────────┴──────────┴──────────┴──────────┴──────────────────┘  │
│                                                                      │
│  AVAILABLE REPORTS:                                                  │
│  📄 Q2 2026 Technical Report (PDF) — Generated July 1, 2026        │
│  📄 Independent Valuation Summary — June 2026                       │
│  📄 Environmental Compliance Certificate — Valid through Dec 2026   │
│  📄 JORC-style Resource Statement — Updated June 15, 2026          │
│                                                                      │
│  DISCLAIMER: Estimates are based on AI-assisted analysis of         │
│  field samples. Independent verification by qualified geologist     │
│  recommended for investment decisions.                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.4 Mobile Field Sampling App

```
┌─────────────────────────────────────────────┐
│  ☰ AfriMine          📡 Online   👤 James   │
├─────────────────────────────────────────────┤
│                                              │
│  📍 CURRENT: Kiambu Plot #247               │
│  GPS: -1.1234, 36.7890  Accuracy: ±3m      │
│                                              │
│  ┌─────────────────────────────────────────┐ │
│  │                                         │ │
│  │         [LIVE CAMERA VIEW]              │ │
│  │                                         │ │
│  │    ┌─────────────────────────────┐      │ │
│  │    │  AI Detection Box           │      │ │
│  │    │  "Quartz vein detected"     │      │ │
│  │    │  Confidence: 78%            │      │ │
│  │    └─────────────────────────────┘      │ │
│  │                                         │ │
│  │  [Reference card visible in frame]      │ │
│  │                                         │ │
│  └─────────────────────────────────────────┘ │
│                                              │
│  SAMPLE TYPE:  [Rock ▼]                      │
│  DEPTH (m):    [0.5        ]                 │
│  NOTES:        [Optional... ]                │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 📷 Photo │  │ 📊 XRF   │  │ ✅ Submit│   │
│  └──────────┘  └──────────┘  └──────────┘   │
│                                              │
│  ⚠️ Offline mode — data will sync when       │
│     connected (14 pending samples)           │
│                                              │
│  QUICK ACTIONS:                              │
│  🗺️ View Map  📋 Sample List  📞 Call Support│
│                                              │
└─────────────────────────────────────────────┘

Key UX decisions:
• Camera-first: The primary action is photographing a sample
• AI guidance: Real-time overlay shows what the model detects
• Minimal typing: Dropdowns, buttons, voice notes > text fields
• Offline indicator always visible
• One-thumb operation: All critical actions within thumb reach
```

---

## 6. Integration Points

### 6.1 Hardware Interfaces

```
┌─────────────────────────────────────────────────────────────────────┐
│                HARDWARE INTEGRATION ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ DEVICE ABSTRACTION LAYER                                        │ │
│  │                                                                  │ │
│  │ Common interface: DevicePlugin (Go interface)                   │ │
│  │ type DevicePlugin interface {                                   │ │
│  │     Connect() error                                             │ │
│  │     ReadSample() (*Measurement, error)                          │ │
│  │     Calibrate() error                                           │ │
│  │     Status() DeviceStatus                                       │ │
│  │ }                                                               │ │
│  └──────────────────────┬──────────────────────────────────────────┘ │
│                         │                                            │
│    ┌────────────────────┼────────────────────────────┐               │
│    │                    │                            │               │
│  ┌─▼─────────────┐  ┌──▼──────────────┐  ┌─────────▼──────────┐    │
│  │ XRF ANALYZER  │  │ SPECTROMETER    │  │ DRONE              │    │
│  │               │  │                 │  │                    │    │
│  │ Supported:    │  │ Supported:      │  │ Supported:         │    │
│  │ • Olympus Vanta│ │ • ASD TerraSpec │  │ • DJI Mavic/Mini  │    │
│  │ • Thermo Niton│  │ • Ocean Insight │  │ • Custom (MAVLink) │    │
│  │ • Bruker S1   │  │ • SRM portable  │  │                    │    │
│  │               │  │                 │  │ Capabilities:      │    │
│  │ Protocol:     │  │ Protocol:       │  │ • Aerial survey    │    │
│  │ USB Serial    │  │ USB/Bluetooth   │  │ • Photogrammetry   │    │
│  │ (JSON-RPC)    │  │ (REST/SDK)      │  │ • Multispectral    │    │
│  │               │  │                 │  │ • Thermal          │    │
│  │ Data format:  │  │ Data format:    │  │                    │    │
│  │ Element ppm/% │  │ Spectral CSV    │  │ Protocol:          │    │
│  │ + metadata    │  │ + wavelengths   │  │ MAVLink/REST       │    │
│  └───────────────┘  └─────────────────┘  └────────────────────┘    │
│                                                                      │
│  CAMERA INTEGRATION:                                                 │
│  • Android Camera2 API for phone cameras                            │
│  • USB UVC for external cameras on edge nodes                       │
│  • Auto-capture: Detect sample in frame, trigger capture             │
│  • Calibration: Color reference card detection + auto white-balance  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Government & External Database Integration

```
┌─────────────────────────────────────────────────────────────────────┐
│              EXTERNAL SYSTEM INTEGRATIONS                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  GOVERNMENT SYSTEMS:                                                 │
│  ├── Kenya Mining Cadastre (eMC+)                                   │
│  │   ├── License verification API (if available)                    │
│  │   ├── Web scraping fallback for public data                      │
│  │   └── Manual upload interface for filings                        │
│  │                                                                  │
│  ├── NEMA (National Environment Management Authority)               │
│  │   ├── EIA report submission                                      │
│  │   └── Compliance status tracking                                 │
│  │                                                                  │
│  ├── Kenya Revenue Authority (KRA)                                  │
│  │   ├── Royalty calculation & reporting                            │
│  │   └── Tax compliance integration                                 │
│  │                                                                  │
│  └── County Government GIS portals                                  │
│      └── Land ownership verification                                │
│                                                                      │
│  INTERNATIONAL DATABASES:                                            │
│  ├── USGS Mineral Resources Data System                             │
│  │   └── Geological survey data, deposit type references            │
│  │                                                                  │
│  ├── Mindat.org API                                                 │
│  │   └── Mineral identification reference data                      │
│  │                                                                  │
│  ├── British Geological Survey (BGS)                                │
│  │   └── African geological maps (historical surveys)               │
│  │                                                                  │
│  ├── JORC / SAMREC / NI 43-101 standards                           │
│  │   └── Resource reporting templates and validation                │
│  │                                                                  │
│  └── UNFC (UN Framework Classification)                             │
│      └── International resource classification standards            │
│                                                                      │
│  FINANCIAL SYSTEMS:                                                  │
│  ├── M-Pesa API (Kenya primary payment)                             │
│  │   ├── Subscription payments                                      │
│  │   └── Community royalty distributions                            │
│  │                                                                  │
│  ├── Bank integrations (Equity Bank, KCB)                           │
│  │   └── Investor reporting, escrow for transactions                │
│  │                                                                  │
│  └── Stripe/PayPal (international investors)                        │
│      └── Cross-border payment processing                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Security & Compliance

### 7.1 Data Sovereignty

```
┌─────────────────────────────────────────────────────────────────────┐
│              DATA SOVEREIGNTY ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  PRINCIPLE: All data generated in Africa stays in Africa.            │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  KENYA DATA CENTER (Primary)                                │    │
│  │  ├── All user data, samples, geological data                │    │
│  │  ├── ML models trained on African data                      │    │
│  │  ├── Financial records                                      │    │
│  │  └── Location: Nairobi (NodeAfrica or Equinix)              │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  AWS CAPE TOWN (Secondary/DR)                               │    │
│  │  ├── Encrypted backup of all data                           │    │
│  │  ├── ML training compute (burst only)                       │    │
│  │  ├── Data encrypted in transit + at rest                    │    │
│  │  └── Access: Kenyan IP whitelist + VPN only                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  GLOBAL SERVICES (metadata only)                            │    │
│  │  ├── CDN: Cloudflare (cached public assets only)            │    │
│  │  ├── Error tracking: Self-hosted Sentry                     │    │
│  │  └── No PII or geological data leaves Africa                │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  COMPLIANCE FRAMEWORK:                                               │
│  ├── Kenya Data Protection Act 2019                                 │
│  │   ├── DPO appointment                                           │
│  │   ├── Consent management                                        │
│  │   ├── Data subject access requests                              │
│  │   └── Breach notification (72 hours)                            │
│  │                                                                  │
│  ├── African Union Convention on Cyber Security                     │
│  │   └── Cross-border data transfer rules                          │
│  │                                                                  │
│  └── GDPR alignment (for European investors accessing portal)       │
│      └── Data processing agreements, right to erasure               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Security Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                SECURITY ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  AUTHENTICATION:                                                     │
│  ├── Primary: Phone number + OTP (SMS via Africa's Talking)         │
│  ├── Secondary: Email + password (for web portal)                   │
│  ├── Investor portal: 2FA required (TOTP)                           │
│  ├── API keys: Scoped, rotatable, with usage tracking               │
│  └── Session: JWT with short expiry (15 min) + refresh token        │
│                                                                      │
│  AUTHORIZATION (RBAC):                                               │
│  ├── Roles: Landowner, Geologist, Investor, Admin, API User         │
│  ├── Permissions: Per-concession, per-action granularity            │
│  └── Policy engine: Casbin (Go-native, lightweight)                 │
│                                                                      │
│  ENCRYPTION:                                                         │
│  ├── In transit: TLS 1.3 everywhere                                 │
│  ├── At rest: AES-256 (database), server-side encryption (MinIO)    │
│  ├── Mobile: Android Keystore for local secrets                     │
│  ├── Edge: LUKS full-disk encryption on edge nodes                  │
│  └── Backups: GPG-encrypted before upload                           │
│                                                                      │
│  API SECURITY:                                                       │
│  ├── Rate limiting: 100 req/min per user, 1000/min per API key      │
│  ├── Input validation: Strict schema validation (all endpoints)     │
│  ├── CORS: Whitelist origins                                        │
│  └── Audit log: All write operations logged with user + timestamp   │
│                                                                      │
│  INCIDENT RESPONSE:                                                  │
│  ├── Automated alerts: Sentry + PagerDuty                           │
│  ├── Runbook: Documented procedures for common incidents            │
│  ├── Backup restore: Tested monthly, RTO < 4 hours                 │
│  └── Penetration testing: Annual third-party audit                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. Technology Stack

### 8.1 Complete Tech Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TECHNOLOGY STACK                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  BACKEND                                                             │
│  ├── Language: Go 1.22+                                             │
│  │   WHY: Single binary deployment, excellent concurrency,          │
│  │   small memory footprint, compiles for ARM (edge), great stdlib  │
│  │                                                                  │
│  ├── Framework: Chi (lightweight router) + net/http                  │
│  │   WHY: No heavy framework overhead, Go stdlib compatible         │
│  │                                                                  │
│  ├── ORM: sqlc (SQL-first, generates Go code)                       │
│  │   WHY: Type-safe SQL, no runtime reflection, fast                │
│  │                                                                  │
│  ├── Task Queue: Asynq (Redis-based)                                │
│  │   WHY: Simple, Redis already in stack, good for background jobs  │
│  │                                                                  │
│  └── API: REST (OpenAPI 3.0 spec) + gRPC (internal services)       │
│                                                                      │
│  DATABASE                                                            │
│  ├── Primary: PostgreSQL 16 + PostGIS 3.4                           │
│  │   WHY: Best spatial database, free, battle-tested, great ecosystem│
│  │                                                                  │
│  ├── Time series: TimescaleDB (PostgreSQL extension)                │
│  │   WHY: No separate DB needed, automatic partitioning             │
│  │                                                                  │
│  ├── Cache: Redis 7                                                 │
│  │   WHY: Caching, pub/sub, task queue backend, session store       │
│  │                                                                  │
│  ├── Object storage: MinIO                                          │
│  │   WHY: S3-compatible, self-hosted, free, runs on ARM             │
│  │                                                                  │
│  └── Edge: SQLite (mobile) + PostgreSQL (edge node)                 │
│                                                                      │
│  FRONTEND (Web)                                                      │
│  ├── Framework: React 18 + TypeScript                               │
│  │   WHY: Largest ecosystem, good for complex dashboards            │
│  │                                                                  │
│  ├── UI Library: Ant Design                                         │
│  │   WHY: Rich components, good data tables, i18n built-in          │
│  │                                                                  │
│  ├── Maps: MapLibre GL JS (open-source Mapbox fork)                │
│  │   WHY: Free, good performance, vector tiles                     │
│  │                                                                  │
│  ├── 3D Viewer: Three.js (block model visualization)               │
│  │   WHY: Industry standard for 3D web, large community            │
│  │                                                                  │
│  ├── Charts: Apache ECharts                                         │
│  │   WHY: Free, powerful, good for scientific data                  │
│  │                                                                  │
│  └── PWA: Workbox for offline capability                            │
│                                                                      │
│  MOBILE (Android)                                                    │
│  ├── Language: Kotlin                                                │
│  ├── UI: Jetpack Compose                                            │
│  │   WHY: Modern declarative UI, Google's direction                 │
│  │                                                                  │
│  ├── Architecture: MVVM + Clean Architecture                        │
│  ├── DI: Hilt (Dagger-based)                                        │
│  ├── Networking: Ktor Client                                        │
│  ├── Local DB: Room (SQLite wrapper)                                │
│  ├── ML: TensorFlow Lite                                            │
│  │   WHY: On-device inference, small models, GPU delegate           │
│  │                                                                  │
│  ├── Background: WorkManager                                        │
│  └── Min SDK: 26 (Android 8.0) — covers 95%+ of Kenya devices      │
│                                                                      │
│  AI/ML                                                               │
│  ├── Training: Python 3.11 + PyTorch 2.x                            │
│  │   WHY: Most flexible for research, best ecosystem                │
│  │                                                                  │
│  ├── Experiment tracking: MLflow (self-hosted)                      │
│  │   WHY: Free, model registry, experiment comparison               │
│  │                                                                  │
│  ├── Model serving: ONNX Runtime                                    │
│  │   WHY: Cross-platform (Python → TFLite), optimized inference     │
│  │                                                                  │
│  ├── Feature store: Feast (lightweight)                              │
│  │   WHY: Consistent features between training and serving          │
│  │                                                                  │
│  ├── Computer vision: PyTorch + torchvision + timm                  │
│  ├── Geostatistics: PyKrige + scikit-gstat                          │
│  ├── NLP (reports): Local LLM (Llama 3 / Mistral) via llama.cpp    │
│  │   WHY: Runs on edge, no cloud dependency, no API costs           │
│  │                                                                  │
│  └── Quantum: Qiskit + PennyLane (classical simulation)             │
│                                                                      │
│  INFRASTRUCTURE                                                      │
│  ├── Containers: Docker + Docker Compose (not K8s initially)        │
│  │   WHY: Simpler ops for small team, single-node deployments       │
│  │                                                                  │
│  ├── CI/CD: Gitea (self-hosted Git) + Woodpecker CI                 │
│  │   WHY: Free, self-hosted, lightweight, data sovereignty          │
│  │                                                                  │
│  ├── Monitoring: Prometheus + Grafana                                │
│  │   WHY: Industry standard, free, great dashboards                 │
│  │                                                                  │
│  ├── Logging: Loki + Promtail                                       │
│  │   WHY: Lightweight, Grafana-native, good for small scale         │
│  │                                                                  │
│  ├── Error tracking: Self-hosted Sentry                             │
│  ├── Reverse proxy: Caddy                                           │
│  │   WHY: Auto-HTTPS, simple config, good performance               │
│  │                                                                  │
│  └── DNS: Cloudflare (free tier for DNS + DDoS protection)          │
│                                                                      │
│  MESSAGING / NOTIFICATIONS                                           │
│  ├── SMS: Africa's Talking API                                      │
│  │   WHY: Pan-African SMS gateway, M-Pesa integration, good pricing │
│  │                                                                  │
│  ├── Push: Firebase Cloud Messaging (FCM)                           │
│  │   WHY: Free, reliable, good Android support                     │
│  │                                                                  │
│  └── Email: Self-hosted (Postal or simple SMTP)                     │
│                                                                      │
│  DATA PROCESSING                                                     │
│  ├── ETL: Apache Airflow (self-hosted)                              │
│  │   WHY: Orchestrates data pipelines, good UI, free                │
│  │                                                                  │
│  ├── Data validation: Great Expectations                            │
│  │   WHY: Data quality checks, documentation of data                │
│  │                                                                  │
│  └── Geospatial: GDAL + GeoPandas + Shapely                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 Open-Source Priority Justification

| Category | Proprietary Option | Open-Source Choice | Savings |
|----------|-------------------|-------------------|---------|
| Database | Oracle Spatial | PostgreSQL + PostGIS | $50K+/yr |
| Object storage | AWS S3 | MinIO | $10K+/yr |
| CI/CD | GitHub Actions | Gitea + Woodpecker | $5K+/yr |
| Monitoring | Datadog | Prometheus + Grafana | $20K+/yr |
| Error tracking | Sentry SaaS | Self-hosted Sentry | $3K+/yr |
| ML tracking | Weights & Biases | MLflow | $10K+/yr |
| Maps | Google Maps | MapLibre + OpenStreetMap | $5K+/yr |
| NLP | OpenAI API | Local LLM (Llama) | $15K+/yr |
| **Total savings** | | | **~$118K/yr** |

---

## 9. Implementation Phases

### Phase 1: MVP (Months 1-4) — $80K-120K

```
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 1: MVP — "Prove the Concept"                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  GOAL: Working system that can classify ore samples from photos      │
│  and generate basic geological reports for one mine site in Kenya.   │
│                                                                      │
│  DELIVERABLES:                                                       │
│  ✅ Android app (camera capture + sample submission)                 │
│  ✅ Basic ore classification model (5 mineral types)                 │
│  ✅ Simple web dashboard (landowner view)                            │
│  ✅ Basic report generation (PDF template)                           │
│  ✅ Offline capture with online sync                                 │
│  ✅ User auth (phone + OTP)                                          │
│                                                                      │
│  NOT IN SCOPE:                                                       │
│  ❌ Quantum computing                                                │
│  ❌ Investor portal                                                  │
│  ❌ Hardware integrations                                            │
│  ❌ Multi-site support                                               │
│  ❌ Advanced geostatistics                                           │
│                                                                      │
│  TEAM (5 people):                                                    │
│  ├── 1 Backend/ML engineer (Go + Python)                             │
│  ├── 1 Android engineer                                              │
│  ├── 1 Frontend engineer (React)                                     │
│  ├── 1 Geologist/domain expert (part-time consultant)                │
│  └── 1 Product/PM (can be founder)                                   │
│                                                                      │
│  BUDGET BREAKDOWN:                                                   │
│  ├── Salaries/contractors (4 months): $60K-80K                       │
│  ├── Cloud infrastructure: $2K                                       │
│  ├── Hardware (test devices, XRF rental): $5K                        │
│  ├── Geological data acquisition: $5K                                │
│  ├── Legal (company setup, data protection): $5K                     │
│  └── Contingency: $8K                                                │
│                                                                      │
│  SUCCESS METRICS:                                                    │
│  ├── Ore classification accuracy >75% on test set                    │
│  ├── 10 field samples processed end-to-end                           │
│  ├── 1 landowner successfully uses dashboard                         │
│  └── System works offline for 24+ hours                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 2: Production (Months 5-10) — $150K-250K

```
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 2: PRODUCTION — "Make It Real"                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  GOAL: Production-grade platform serving 10-50 mine sites with       │
│  accurate geological estimation and regulatory compliance.           │
│                                                                      │
│  DELIVERABLES:                                                       │
│  ✅ Full ore classification (20+ mineral types)                      │
│  ✅ Geostatistical estimation (kriging + ML hybrid)                  │
│  ✅ Block model generation                                           │
│  ✅ Investor portal with reports                                     │
│  ✅ Market price integration                                         │
│  ✅ Regulatory compliance module (Kenya Mining Act)                  │
│  ✅ Edge node deployment at 3+ sites                                 │
│  ✅ XRF device integration                                           │
│  ✅ Multi-language (English, Swahili)                                │
│  ✅ M-Pesa payment integration                                       │
│  ✅ Active learning pipeline operational                             │
│                                                                      │
│  TEAM (8 people):                                                    │
│  ├── 2 Backend engineers                                             │
│  ├── 1 ML engineer                                                   │
│  ├── 1 Android engineer                                              │
│  ├── 1 Frontend engineer                                             │
│  ├── 1 DevOps / Infrastructure                                       │
│  ├── 1 Geologist (full-time)                                         │
│  └── 1 Product/PM                                                    │
│                                                                      │
│  BUDGET BREAKDOWN:                                                   │
│  ├── Salaries (6 months): $120K-180K                                 │
│  ├── Cloud infrastructure: $8K                                       │
│  ├── Hardware (edge nodes, devices): $15K                            │
│  ├── Geological data + training: $10K                                │
│  ├── Security audit: $5K                                             │
│  ├── Legal + compliance: $5K                                         │
│  └── Contingency: $15K                                               │
│                                                                      │
│  SUCCESS METRICS:                                                    │
│  ├── Ore classification accuracy >85%                                │
│  ├── Resource estimation within 20% of independent verification      │
│  ├── 10+ paying customers                                            │
│  ├── 99.5% uptime                                                    │
│  └── <2s page load time                                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 3: Scale (Months 11-18) — $300K-500K

```
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 3: SCALE — "Expand the Impact"                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  GOAL: Multi-country platform with advanced AI, drone integration,   │
│  and quantum-ready optimization for mine planning.                   │
│                                                                      │
│  DELIVERABLES:                                                       │
│  ✅ Multi-site federation (federated learning operational)           │
│  ✅ Drone survey integration (photogrammetry, multispectral)         │
│  ✅ Advanced NLP report generation (local LLM)                       │
│  ✅ Spectrometer integration                                         │
│  ✅ Mine planning optimization (classical, quantum-ready)            │
│  ✅ Tanzania and Ghana regulatory modules                            │
│  ✅ API marketplace for third-party integrations                     │
│  ✅ Kubernetes migration for multi-node scaling                      │
│  ✅ Advanced 3D block model viewer                                   │
│  └── Quantum cloud integration (D-Wave / AWS Braket)                 │
│                                                                      │
│  TEAM (12-15 people):                                                │
│  ├── 3 Backend engineers                                             │
│  ├── 2 ML engineers                                                  │
│  ├── 2 Android engineers                                             │
│  ├── 1 Frontend engineer                                             │
│  ├── 1 DevOps / SRE                                                  │
│  ├── 2 Geologists                                                    │
│  ├── 1 QA engineer                                                   │
│  └── 1-2 Business development / Country managers                     │
│                                                                      │
│  BUDGET BREAKDOWN:                                                   │
│  ├── Salaries (8 months): $240K-380K                                 │
│  ├── Cloud infrastructure: $20K                                      │
│  ├── Hardware (drones, edge nodes at scale): $30K                    │
│  ├── Quantum cloud compute: $5K                                      │
│  ├── Multi-country legal + regulatory: $15K                          │
│  ├── Security + penetration testing: $10K                            │
│  └── Contingency: $20K                                               │
│                                                                      │
│  SUCCESS METRICS:                                                    │
│  ├── Ore classification accuracy >92%                                │
│  ├── 100+ active mine sites                                          │
│  ├── Operations in 3+ countries                                      │
│  ├── Revenue: $50K+/month                                            │
│  └── Model improvement: measurable month-over-month accuracy gains   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 4: Intelligence (Months 19-30) — $500K-1M

```
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 4: INTELLIGENCE — "The Platform"                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  GOAL: Full platform with autonomous exploration recommendations,    │
│  quantum-enhanced optimization, and pan-African coverage.            │
│                                                                      │
│  DELIVERABLES:                                                       │
│  ✅ Autonomous exploration recommendation agent                      │
│  ✅ Quantum-classical hybrid mine planning                           │
│  ✅ Real-time satellite imagery integration                          │
│  ✅ Community benefit tracking and distribution (M-Pesa)             │
│  ✅ Carbon footprint tracking for ESG reporting                      │
│  ✅ Marketplace: Connect landowners with investors                   │
│  ✅ White-label for government geological surveys                    │
│  ✅ 10+ country coverage                                             │
│                                                                      │
│  TEAM (20-25 people)                                                 │
│  BUDGET: $500K-1M for 12 months                                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 10. Cost Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TOTAL COST ESTIMATE                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Phase    │ Duration  │ Team  │ Budget Range  │ Cumulative           │
│  ────────┼───────────┼───────┼───────────────┼────────────          │
│  1 MVP   │ 4 months  │ 5     │ $80K-120K     │ $80K-120K           │
│  2 Prod  │ 6 months  │ 8     │ $150K-250K    │ $230K-370K          │
│  3 Scale │ 8 months  │ 12-15 │ $300K-500K    │ $530K-870K          │
│  4 Intel │ 12 months │ 20-25 │ $500K-1M      │ $1.03M-1.87M        │
│  ────────┼───────────┼───────┼───────────────┼────────────          │
│  TOTAL   │ 30 months │       │ $1.03M-1.87M  │                     │
│                                                                      │
│  INFRASTRUCTURE RECURRING (Monthly):                                 │
│  ├── Phase 1: $500/mo (single server + managed DB)                   │
│  ├── Phase 2: $2K/mo (multi-server + CDN + backups)                  │
│  ├── Phase 3: $5K/mo (Kubernetes cluster + GPU for training)         │
│  └── Phase 4: $10K/mo (multi-region + redundancy)                    │
│                                                                      │
│  REVENUE MODEL (to reach sustainability):                            │
│  ├── Per-sample analysis fee: $5-20/sample                           │
│  ├── Monthly subscription (landowner): $20-50/month                  │
│  ├── Investor portal access: $100-500/month                          │
│  ├── API access for third parties: Usage-based                       │
│  └── Break-even target: Month 18-24 (Phase 3)                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 11. Architecture Decision Records (Key Decisions)

| # | Decision | Options Considered | Choice | Rationale |
|---|----------|-------------------|--------|-----------|
| ADR-1 | Architecture style | Microservices, Modular Monolith, Serverless | Modular Monolith | Small team, offline-first requirements, single-binary deploys |
| ADR-2 | Primary language | Python, Go, Rust | Go | Compiles to single binary, ARM support, good performance, simple deployment |
| ADR-3 | Database | PostgreSQL, MongoDB, CockroachDB | PostgreSQL + PostGIS | Spatial queries critical, mature ecosystem, free, TimescaleDB extension |
| ADR-4 | Mobile framework | React Native, Flutter, Native Android | Native Kotlin + Compose | Best Android performance, camera/ML integration, 80%+ Android in Kenya |
| ADR-5 | ML serving | TensorFlow Serving, Triton, ONNX, TFLite | TFLite (edge) + ONNX (server) | TFLite for mobile, ONNX for cross-platform server inference |
| ADR-6 | Sync protocol | Firebase, Custom CRDT, PouchDB | Custom CRDT + Event Sourcing | Data sovereignty (no Google dependency), full control |
| ADR-7 | Cloud provider | AWS, Azure, GCP, Self-hosted | Self-hosted Nairobi + AWS Cape Town DR | Data sovereignty, cost control, latency |
| ADR-8 | NLP for reports | OpenAI API, Local LLM, Templates | Templates (MVP) → Local LLM (Phase 3) | Cost control, offline capability, data sovereignty |
| ADR-9 | Quantum | Build now, Design for, Ignore | Design quantum-ready, deploy classical | Quantum hardware not practical for this use case yet; architecture ready |
| ADR-10 | Maps | Google Maps, Mapbox, MapLibre | MapLibre + OpenStreetMap | Free, self-hostable, no per-request costs |

---

## 12. Risk Register

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Insufficient training data for African minerals | High | High | Transfer learning, synthetic data, active learning, geologist partnerships |
| Low bandwidth makes cloud sync impractical | High | Medium | Edge-first architecture, delta sync, sneakernet fallback |
| Government regulatory changes | Medium | Medium | Modular compliance engine, legal advisory |
| XRF/spectrometer device fragmentation | Medium | Medium | Device abstraction layer, start with 1-2 supported devices |
| Security breach exposing geological data | High | Low | Encryption at rest/transit, RBAC, security audits, data minimization |
| Quantum advantage not materializing | Low | Medium | Classical solvers as primary; quantum is additive, not required |
| Team attrition (small team risk) | High | Medium | Documentation-first culture, CI/CD, code review, bus factor >1 |
| User adoption resistance | High | Medium | Community engagement, Swahili UI, SMS fallback, local champions |

---

## 13. Appendix: Deployment Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PRODUCTION DEPLOYMENT                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────── EDGE (Mine Site) ──────────────────────────────────────┐   │
│  │                                                                        │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │   │
│  │  │ Android  │  │ Android  │  │ XRF      │  │ Drone    │              │   │
│  │  │ Device 1 │  │ Device 2 │  │ Device   │  │ (DJI)    │              │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘              │   │
│  │       │              │             │             │                     │   │
│  │       └──────────────┴──────┬──────┴─────────────┘                     │   │
│  │                             │ WiFi/LAN                                 │   │
│  │                    ┌────────▼────────┐                                 │   │
│  │                    │   Edge Node     │                                 │   │
│  │                    │ (RPi 5 / Jetson)│                                 │   │
│  │                    │                 │                                 │   │
│  │                    │ ┌─────────────┐ │                                 │   │
│  │                    │ │ AfriMine   │ │                                 │   │
│  │                    │ │ Edge Agent │ │                                 │   │
│  │                    │ └─────────────┘ │                                 │   │
│  │                    │ ┌─────────────┐ │                                 │   │
│  │                    │ │ PostgreSQL │ │                                 │   │
│  │                    │ │ + PostGIS  │ │                                 │   │
│  │                    │ └─────────────┘ │                                 │   │
│  │                    │ ┌─────────────┐ │                                 │   │
│  │                    │ │ TFLite     │ │                                 │   │
│  │                    │ │ Runtime    │ │                                 │   │
│  │                    │ └─────────────┘ │                                 │   │
│  │                    └────────┬────────┘                                 │   │
│  │                             │ 4G/LTE (when available)                  │   │
│  └─────────────────────────────┼──────────────────────────────────────────┘   │
│                                │                                              │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │
│                                │                                              │
│  ┌─────────────── NAIROBI DC ──┼───────────────────────────────────────────┐  │
│  │                             │                                           │  │
│  │                    ┌────────▼────────┐                                 │  │
│  │                    │   Caddy         │ (Reverse proxy + TLS)            │  │
│  │                    └────────┬────────┘                                 │  │
│  │                             │                                           │  │
│  │              ┌──────────────┼──────────────┐                           │  │
│  │              │              │              │                           │  │
│  │     ┌────────▼───────┐ ┌───▼──────────┐ ┌▼───────────────┐           │  │
│  │     │ App Server 1   │ │ App Server 2 │ │ ML GPU Server  │           │  │
│  │     │ (Go monolith)  │ │ (Go monolith)│ │ (Training)     │           │  │
│  │     └────────┬───────┘ └───┬──────────┘ └┬───────────────┘           │  │
│  │              │              │              │                           │  │
│  │              └──────────────┼──────────────┘                           │  │
│  │                             │                                           │  │
│  │     ┌───────────────────────┼───────────────────────┐                 │  │
│  │     │                       │                       │                 │  │
│  │  ┌──▼──────────┐  ┌────────▼────────┐  ┌───────────▼───────┐        │  │
│  │  │ PostgreSQL  │  │ Redis Cluster   │  │ MinIO Cluster     │        │  │
│  │  │ Primary +   │  │ (Cache + Queue) │  │ (Object Storage)  │        │  │
│  │  │ Replica     │  │                 │  │                   │        │  │
│  │  └─────────────┘  └─────────────────┘  └───────────────────┘        │  │
│  │                                                                       │  │
│  │  ┌─────────────┐  ┌─────────────────┐  ┌───────────────────┐        │  │
│  │  │ Prometheus  │  │ Gitea +         │  │ MinIO (Backups)   │        │  │
│  │  │ + Grafana   │  │ Woodpecker CI   │  │                   │        │  │
│  │  └─────────────┘  └─────────────────┘  └───────────────────┘        │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │
│                                                                              │
│  ┌─────────────── AWS CAPE TOWN (DR) ─────────────────────────────────────┐  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │  │
│  │  │ DB Replica   │  │ MinIO Mirror │  │ ML Training  │                 │  │
│  │  │ (standby)    │  │ (backup)     │  │ (burst)      │                 │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                 │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 14. Appendix: API Design (Key Endpoints)

```
API Version: v1
Base URL: https://api.afrimine.ai/v1
Auth: Bearer token (JWT)

SAMPLES
  POST   /samples                    — Submit new sample (image + metadata)
  GET    /samples                    — List samples (filterable)
  GET    /samples/{id}               — Get sample detail
  PATCH  /samples/{id}               — Update sample (geologist review)
  POST   /samples/{id}/classify      — Trigger AI classification
  GET    /samples/{id}/classification — Get classification result

CONCESSIONS
  POST   /concessions                — Create concession
  GET    /concessions                — List user's concessions
  GET    /concessions/{id}           — Get concession detail
  GET    /concessions/{id}/samples   — Samples for concession
  GET    /concessions/{id}/model     — Block model data
  GET    /concessions/{id}/estimate  — Resource estimate
  GET    /concessions/{id}/report    — Generate report

MARKET
  GET    /market/prices              — Current prices
  GET    /market/prices/{mineral}    — Price history
  GET    /market/alerts              — Price alerts

REPORTS
  POST   /reports/generate           — Generate report (async)
  GET    /reports/{id}               — Get report status/download
  GET    /reports                    — List reports

HARDWARE
  POST   /devices/register           — Register device (XRF, etc.)
  POST   /devices/{id}/measurements  — Submit measurement
  GET    /devices/{id}/status        — Device health

SYNC
  POST   /sync/push                  — Push local changes
  POST   /sync/pull                  — Pull remote changes
  GET    /sync/status                — Sync status

ADMIN
  GET    /admin/users                — User management
  GET    /admin/audit-log            — Audit trail
  GET    /admin/system-health        — System health
```

---

*End of Architecture Document*

**Next Steps:**
1. Review with geologist domain expert for geological model validation
2. Validate tech stack choices with engineering team
3. Begin Phase 1 sprint planning
4. Identify first pilot mine site in Kenya (Kiambu or Nakuru county)
5. Establish data partnership with Kenya Geological Survey
