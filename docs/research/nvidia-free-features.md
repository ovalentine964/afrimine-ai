# AfriMine AI — NVIDIA Free Offerings Inventory

**Date:** 2026-07-18
**Purpose:** Comprehensive inventory of every free NVIDIA service/tool/API applicable to AfriMine AI

---

## TIER 1: MUST USE (Free, Directly Applicable, High Value)

### 1. NVIDIA NIM (Inference Microservices) — Hosted API

| Attribute | Detail |
|---|---|
| **What's Free** | Free hosted API endpoints at build.nvidia.com for prototyping & development |
| **Models Available** | 100+ models including: Llama 3.1/4, Mistral 7B, DeepSeek V4, Gemma 2/3, FLUX image generation, Cosmos vision models, embedding models, ASR models |
| **Rate Limits** | Free credits on signup; unlimited prototyping for Developer Program members on self-hosted NIM (up to 2 nodes / 16 GPUs) |
| **AfriMine Use** | **LLM for geological report generation** (Llama 3.1 8B or Mistral 7B), **Vision models for mineral classification** (Cosmos Reason2-8B for visual understanding), **Embedding models** for knowledge retrieval |
| **How to Access** | API at build.nvidia.com (hosted) or download containers from NGC (self-hosted, requires NVIDIA GPU) |
| **Integration** | Easy — standard OpenAI-compatible API |
| **Vendor Lock-in** | Low — models are standard, can swap endpoints |
| **Verdict** | ⭐ **TOP PICK** — The hosted API is genuinely free for development. Self-hosted NIM requires owning an NVIDIA GPU but the container itself is free. |

### 2. NVIDIA Developer Program

| Attribute | Detail |
|---|---|
| **What's Free** | Free membership (5M+ members). Unlocks: NIM downloads, Omniverse access, CUDA toolkit, Nsight tools, DLI training, NGC catalog access, forums, documentation |
| **AfriMine Use** | **Gateway to almost everything else on this list.** Sign up FIRST. |
| **How to Access** | developer.nvidia.com/developer-program — free signup |
| **Integration** | N/A — it's an account tier |
| **Vendor Lock-in** | None |
| **Verdict** | ⭐ **ESSENTIAL — Sign up immediately.** |

### 3. NVIDIA TAO Toolkit (Train, Adapt, Optimize)

| Attribute | Detail |
|---|---|
| **What's Free** | TAO 7 is free to download and use. Includes: pre-trained vision models, transfer learning, fine-tuning, model optimization (pruning, quantization), export to TensorRT/ONNX |
| **Pre-trained Models** | RT-DETR (object detection), MaskGroundingDINO (segmentation), SigLip2 (image embeddings), NV-DINOv2 (visual features), Cosmos 3 (reasoning VLM), VisualChangeNet (change detection) |
| **AfriMine Use** | **Train custom mineral classifier** — fine-tune DINOv2 or SigLip2 on rock sample photos. Use RT-DETR for detecting minerals in field photos. Use VisualChangeNet for satellite change detection |
| **How to Access** | github.com/NVIDIA-TAO/tao-skills-bank + NGC containers |
| **Integration** | Medium — requires Python + NVIDIA GPU for training |
| **Vendor Lock-in** | Low — exports to standard formats (ONNX, TensorRT) |
| **Verdict** | ⭐ **TOP PICK — This is your mineral image classifier backbone.** Free, powerful, and directly applicable. |

### 4. NVIDIA CUDA Toolkit + cuDNN

| Attribute | Detail |
|---|---|
| **What's Free** | CUDA Toolkit is completely free for development and deployment. cuDNN is free with registration |
| **AfriMine Use** | **GPU acceleration for all ML inference and training.** Required for TAO, NIM self-hosting, RAPIDS, PyTorch/TensorFlow GPU support |
| **How to Access** | developer.nvidia.com/cuda-toolkit — download |
| **Integration** | Easy for cloud, Medium for edge (need NVIDIA GPU hardware) |
| **Vendor Lock-in** | Medium — CUDA is NVIDIA-only, but it's the industry standard |
| **Verdict** | ⭐ **FOUNDATION — Everything GPU-accelerated depends on this.** |

### 5. NVIDIA Jetson (Edge AI Platform)

| Attribute | Detail |
|---|---|
| **What's Free** | JetPack SDK (free), all NVIDIA AI software libraries (free), TensorRT (free), DeepStream SDK (free), Isaac ROS (free) |
| **Hardware Cost** | Jetson Orin Nano Super Developer Kit: **$249** (100 TOPS AI performance). Jetson Orin Nano module: ~$199. Old Jetson Nano: discontinued but ~$149 |
| **vs Raspberry Pi** | Jetson Orin Nano has **GPU with 1024 CUDA cores** vs Pi's CPU-only. 100 TOPS vs ~0 TOPS for AI. Can run TAO-optimized models natively. Pi needs Coral TPU ($60) or runs CPU-only (very slow) |
| **AfriMine Use** | **Edge mineral classification at mine site.** Run TAO-optimized mineral classifier directly on Jetson. Process camera input in real-time. No internet needed |
| **How to Access** | nvidia.com/jetson — buy developer kit, download JetPack |
| **Integration** | Medium — need to buy hardware, but software is free |
| **Vendor Lock-in** | Medium — Jetson-specific but has huge ecosystem |
| **Verdict** | ⭐ **TOP PICK for edge — Replace Raspberry Pi with Jetson Orin Nano.** $249 is worth it for real AI inference at mine site. |

### 6. NVIDIA RAPIDS

| Attribute | Detail |
|---|---|
| **What's Free** | Completely free, open-source (Apache 2.0). Libraries: cuDF (GPU pandas), cuML (GPU scikit-learn), cuGraph (GPU graph analytics), cuSpatial (GPU spatial/geospatial) |
| **AfriMine Use** | **GPU-accelerated geostatistics.** cuML for regression/kriging models. cuSpatial for spatial analysis of drill hole data. cuDF for processing large geological datasets 10-100x faster |
| **How to Access** | rapids.ai — conda/pip install. Also available on Google Colab (free GPU) |
| **Integration** | Easy — drop-in replacement for pandas/scikit-learn |
| **Vendor Lock-in** | Low — open source, standard Python APIs |
| **Verdict** | ⭐ **TOP PICK — Free, open-source, massive speedup for geostatistics.** |

---

## TIER 2: SHOULD USE (Free, Applicable, Medium Value)

### 7. NVIDIA NGC (GPU Cloud) Catalog

| Attribute | Detail |
|---|---|
| **What's Free** | Free access to NGC catalog: pre-trained models, containers, Helm charts, SDKs. NO free GPU hours — NGC is a registry, not a compute service |
| **AfriMine Use** | Download pre-built containers for TAO, NIM, RAPIDS, Triton, NeMo. Pre-trained model weights. Helm charts for Kubernetes deployment |
| **How to Access** | catalog.ngc.nvidia.com — free NGC account (linked to Developer Program) |
| **Integration** | Easy — it's a download registry |
| **Vendor Lock-in** | Low — containers run anywhere with NVIDIA GPU |
| **Verdict** | **SHOULD USE — Essential repository, but no free compute.** |

### 8. NVIDIA Triton Inference Server

| Attribute | Detail |
|---|---|
| **What's Free** | Completely free, open-source. Self-host your own inference server |
| **AfriMine Use** | **Self-host mineral classification model.** Serve TAO-trained model via REST/gRPC API. Supports PyTorch, TensorRT, ONNX models. Can run on Jetson |
| **On Raspberry Pi?** | ❌ No — requires NVIDIA GPU. But ✅ runs on Jetson |
| **How to Access** | github.com/triton-inference-server — Docker containers on NGC |
| **Integration** | Medium — requires Docker + NVIDIA GPU |
| **Vendor Lock-in** | Low — open source, standard APIs |
| **Verdict** | **SHOULD USE — If self-hosting models, Triton is the production-grade way.** |

### 9. NVIDIA Inception Program

| Attribute | Detail |
|---|---|
| **What's Free** | Free membership for AI startups. Benefits: cloud credits (up to $10K+ via partner programs), preferred hardware pricing, DLI training, networking events, GTC access, go-to-market support |
| **Eligibility** | Must be a startup (registered company). AI/data science focus. No stage restriction (seed to Series C+) |
| **AfriMine Use** | **Get cloud credits for training.** Hardware discounts for Jetson kits. Training resources. Investor networking (relevant for raising capital) |
| **How to Access** | nvidia.com/en-us/startups/ — apply online |
| **Integration** | N/A — it's a program membership |
| **Vendor Lock-in** | Low — benefits are additive |
| **Verdict** | **SHOULD USE — Apply immediately. Free cloud credits + network.** |

### 10. NVIDIA NeMo Framework

| Attribute | Detail |
|---|---|
| **What's Free** | Free, open-source framework for training/fine-tuning LLMs. Includes NeMo Curator (data processing), NeMo Guardrails (safety) |
| **AfriMine Use** | **Fine-tune LLM on geological data** for specialized report generation. Train on Kenyan geological survey reports, mining regulations, mineral databases |
| **How to Access** | github.com/NVIDIA/NeMo — pip install |
| **Integration** | Hard — requires significant GPU compute for training (A100 recommended) |
| **Vendor Lock-in** | Low — open source |
| **Verdict** | **SHOULD USE (but expensive to train) — Free framework, but compute costs money. Use hosted NIM for inference instead.** |

### 11. NVIDIA AI Workbench

| Attribute | Detail |
|---|---|
| **What's Free** | Free desktop application for AI development. Integrates with Jupyter, Git, Docker, conda. One-click deployment to Jetson, cloud, or local GPU |
| **AfriMine Use** | **Development environment for the team.** Package mineral classifier project. Deploy to Jetson at mine site. Reproducible environments |
| **How to Access** | developer.nvidia.com/ai-workbench — download |
| **Integration** | Easy — GUI-based |
| **Vendor Lock-in** | Medium — workflow tool |
| **Verdict** | **NICE TO HAVE — Useful dev tool but not critical.** |

### 12. NVIDIA Omniverse

| Attribute | Detail |
|---|---|
| **What's Free** | Developer Program members get free access to Omniverse libraries and developer tools. Individual developers can use for research/development/testing |
| **AfriMine Use** | **3D visualization of geological block models.** Visualize ore body geometry, drill holes, grade distributions in 3D. Import OpenUSD geological models |
| **How to Access** | developer.nvidia.com/omniverse — download via Developer Program |
| **Integration** | Hard — requires RTX GPU, complex 3D pipeline |
| **Vendor Lock-in** | Medium — OpenUSD is open but Omniverse is NVIDIA |
| **Verdict** | **SHOULD USE (if RTX GPU available) — Best 3D viz but hardware requirements are steep.** |

---

## TIER 3: NICE TO HAVE (Free, Tangentially Applicable)

### 13. NVIDIA Earth-2

| Attribute | Detail |
|---|---|
| **What's Free** | Earth-2 is NVIDIA's digital twin platform for climate/weather simulation. Includes FourCastNet (weather prediction), CorrDiff (downscaling). Available as NIM microservices on build.nvidia.com (FourCastNet is listed) |
| **AfriMine Use** | **Weather forecasting for mining operations.** Predict rainfall → flooding risk at mine site. NOT directly for satellite mineral mapping (Sentinel-2 analysis is separate) |
| **Sentinel-2?** | Earth-2 is NOT a satellite image processing tool. It's weather/climate. For Sentinel-2 mineral mapping, use Google Earth Engine (free) + custom ML models |
| **How to Access** | build.nvidia.com — FourCastNet NIM endpoint (free credits) |
| **Integration** | Medium |
| **Vendor Lock-in** | Low |
| **Verdict** | **NICE TO HAVE — Useful for weather ops, not mineral detection.** |

### 14. NVIDIA Morpheus

| Attribute | Detail |
|---|---|
| **What's Free** | Free, open-source cybersecurity AI framework |
| **AfriMine Use** | **Protect mining data & IoT sensor streams.** Detect anomalies in sensor data (potential tampering). Secure data pipeline from mine site to cloud |
| **How to Access** | github.com/NVIDIA/Morpheus |
| **Integration** | Hard — specialized cybersecurity framework |
| **Vendor Lock-in** | Low — open source |
| **Verdict** | **NICE TO HAVE — Overkill for early stage. Revisit when platform scales.** |

### 15. NVIDIA Merlin

| Attribute | Detail |
|---|---|
| **What's Free** | Free, open-source recommendation system framework (now largely integrated into NVIDIA Merlin on NGC) |
| **AfriMine Use** | **Investor/offtaker matching.** Match mining output with buyers. Recommend similar geological sites for expansion. Tangential use |
| **How to Access** | NGC catalog |
| **Integration** | Hard — requires significant data to train |
| **Vendor Lock-in** | Low — open source |
| **Verdict** | **NICE TO HAVE — Very tangential. Skip for MVP.** |

### 16. NVIDIA Picasso / Edify

| Attribute | Detail |
|---|---|
| **What's Free** | NOT free for commercial use. Picasso is NVIDIA's API for Edify image generation models. Available via build.nvidia.com with free credits for testing |
| **AfriMine Use** | **Synthetic mineral images for training.** Generate synthetic rock sample images to augment training dataset. Useful when you have few real mineral photos |
| **How to Access** | build.nvidia.com — FLUX models available (free credits) |
| **Integration** | Easy — API call |
| **Vendor Lock-in** | Medium |
| **Verdict** | **NICE TO HAVE — Use free credits for synthetic data generation. Budget for production.** |

### 17. NVIDIA DeepStream SDK

| Attribute | Detail |
|---|---|
| **What's Free** | Free SDK for AI-powered video analytics. Optimized for Jetson |
| **AfriMine Use** | **Video monitoring at mine site.** Detect equipment, people, safety violations. Process camera feeds with AI |
| **How to Access** | developer.nvidia.com/deepstream-sdk — download |
| **Integration** | Medium — requires Jetson or NVIDIA GPU |
| **Vendor Lock-in** | Medium |
| **Verdict** | **NICE TO HAVE — Useful for mine site monitoring if cameras deployed.** |

### 18. NVIDIA DLI (Deep Learning Institute)

| Attribute | Detail |
|---|---|
| **What's Free** | Free courses available with Developer Program. Some courses free during GTC. Certification exams have fees |
| **AfriMine Use** | **Team training.** Free courses on computer vision, deep learning fundamentals, Jetson deployment |
| **How to Access** | learn.nvidia.com |
| **Integration** | N/A — education |
| **Verdict** | **NICE TO HAVE — Free training for the team.** |

### 19. NVIDIA Academic Grants

| Attribute | Detail |
|---|---|
| **What's Free** | GPU hardware grants for qualified academic researchers. Graduate fellowships ($50K+) |
| **AfriMine Use** | If partnering with University of Nairobi or other Kenyan university for geological research |
| **How to Access** | nvidia.com/en-us/industries/higher-education-research/academic-grant-program/ |
| **Verdict** | **NICE TO HAVE — Only if academic partnership exists.** |

### 20. NVIDIA cuOpt

| Attribute | Detail |
|---|---|
| **What's Free** | Available as NIM endpoint on build.nvidia.com with free credits |
| **AfriMine Use** | **Route optimization for ore transport.** Optimize truck routes from mine site to processing facility. Logistics planning |
| **How to Access** | build.nvidia.com — cuOpt NIM endpoint |
| **Integration** | Easy — API |
| **Verdict** | **NICE TO HAVE — Useful for logistics optimization later.** |

---

## TIER 4: SKIP (Not Free or Not Applicable)

### 21. NVIDIA DGX Cloud
- ❌ **Not free** — $36,999/month per instance
- Skip entirely. Use Google Colab free GPU or buy cloud GPU time

### 22. NVIDIA AI Enterprise
- ❌ **Not free** — $4,500/GPU/year. 90-day free trial available
- Skip. Use open-source alternatives (RAPIDS, Triton, NeMo) instead

### 23. NVIDIA DRIVE (Autonomous Vehicles)
- ❌ Not applicable to mining

### 24. NVIDIA Isaac (Robotics)
- ❌ Not directly applicable (unless building autonomous mining vehicles)

### 25. NVIDIA Omniverse Cloud
- ❌ **Not free** — cloud service, pay-per-use
- Use desktop Omniverse (free via Developer Program) instead

---

## SUMMARY: AfriMine AI Recommended NVIDIA Stack

### Phase 1: Foundation (Week 1-2) — $0
1. ✅ Sign up **NVIDIA Developer Program** (free)
2. ✅ Apply for **NVIDIA Inception** (free)
3. ✅ Download **TAO Toolkit** (free) — mineral classifier
4. ✅ Get **build.nvidia.com** API key (free credits) — LLM for reports
5. ✅ Install **CUDA Toolkit** + **RAPIDS** on cloud GPU (free software)

### Phase 2: Mineral Classifier (Week 3-6) — ~$0
6. ✅ Fine-tune DINOv2/SigLip2 via **TAO** on mineral photos (need cloud GPU — use Colab free or Inception credits)
7. ✅ Export to **TensorRT** for edge deployment
8. ✅ Deploy on **Jetson Orin Nano** ($249 hardware) at mine site

### Phase 3: Geological Reports (Week 4-8) — $0
9. ✅ Use **NIM hosted API** (Llama 3.1 8B) for geological report generation
10. ✅ Build RAG pipeline with geological knowledge base

### Phase 4: Geostatistics (Week 6-10) — $0
11. ✅ Use **RAPIDS** (cuML, cuSpatial) for GPU-accelerated kriging/grade estimation
12. ✅ Process drill hole data with cuDF

### Phase 5: 3D Visualization (Month 3+) — $0
13. ✅ Use **Omniverse** for 3D block model visualization (if RTX GPU available)
14. ✅ Alternative: Use free ParaView + OpenVDB (no NVIDIA dependency)

### Phase 6: Satellite Analysis — $0
15. ⚠️ Earth-2 is NOT for satellite mineral mapping
16. ✅ Use **Google Earth Engine** (free) for Sentinel-2 processing
17. ✅ Use **TAO VisualChangeNet** for change detection on processed satellite data

---

## BUDGET SUMMARY

| Item | Cost | Notes |
|---|---|---|
| NVIDIA Developer Program | $0 | Free forever |
| NVIDIA Inception | $0 | Free for startups |
| NIM Hosted API | $0 | Free credits for dev |
| TAO Toolkit | $0 | Free download |
| CUDA/cuDNN | $0 | Free download |
| RAPIDS | $0 | Open source |
| Triton Server | $0 | Open source |
| NeMo Framework | $0 | Open source |
| JetPack SDK | $0 | Free |
| Jetson Orin Nano Super Kit | $249 | One-time hardware |
| Google Colab (free GPU) | $0 | For training |
| **TOTAL** | **$249** | Just the edge hardware |

---

## HONEST ASSESSMENT

**What's genuinely free:**
- All NVIDIA software/SDKs are free for development
- NIM hosted API has free credits (limited, but enough for prototyping)
- TAO Toolkit training is free BUT requires a GPU (use free Colab)
- RAPIDS is open source and genuinely free
- Jetson software is 100% free (hardware costs $249)

**What's "free" but requires spending:**
- Self-hosting NIM requires owning an NVIDIA GPU
- Training TAO models requires GPU compute (Colab free tier is limited)
- Omniverse needs an RTX GPU (not cheap in Kenya)
- Inception cloud credits are real but limited ($10K via AWS partner)

**What's NOT free:**
- NVIDIA AI Enterprise ($4,500/GPU/year) — avoid
- DGX Cloud ($37K/month) — avoid
- Production NIM licensing — unclear, check terms

**Biggest risk:** Vendor lock-in on CUDA. Mitigate by using ONNX export from TAO (runs on any hardware) and keeping models in standard formats.

**Biggest opportunity:** The NVIDIA Inception program + free NIM credits + TAO Toolkit combination gives a Kenyan startup access to the same AI tools as Silicon Valley companies, for effectively $249 (one Jetson kit).
