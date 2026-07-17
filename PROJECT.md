# AfriMine AI — Project Status

## Current Phase: Architecture & Research ✅

### Completed
- [x] 8 specialized research swarms deployed and completed
- [x] NVIDIA free offerings deep dive (25+ services cataloged)
- [x] Architecture review with critical feedback
- [x] Tech stack decisions finalized
- [x] Professional repo created with all research

### Next Phase: Architecture Finalization
- [ ] Update architecture with NVIDIA findings (Jetson replaces Pi)
- [ ] Create detailed API specification
- [ ] Design database schema
- [ ] Create Flutter project structure
- [ ] Set up CI/CD pipeline

---

## Finalized Tech Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| Frontend | **Flutter (Dart)** | $0 |
| Backend | **Go (Chi router)** | $0 |
| AI Inference | **NVIDIA NIM API** (hosted) | $0 (free credits) |
| AI Training | **NVIDIA TAO Toolkit** | $0 |
| Edge Hardware | **NVIDIA Jetson Orin Nano** | $249 one-time |
| Database | **PostgreSQL + PostGIS** | $0 |
| Geostatistics | **NVIDIA RAPIDS** (cuML, cuSpatial) | $0 |
| Model Serving | **NVIDIA Triton** (self-hosted) | $0 |
| Quantum | **IBM Quantum + D-Wave** | $0 (free tiers) |
| Storage | **MinIO** | $0 |
| Maps | **MapLibre GL** | $0 |
| Satellite | **Google Earth Engine** | $0 |
| LLM Reports | **NVIDIA NIM** (Llama 3.1) | $0 (free credits) |
| CI/CD | **Gitea + Woodpecker** | $0 |
| Monitoring | **Prometheus + Grafana** | $0 |
| SMS | **Africa's Talking** | ~$50-100/mo |
| **TOTAL SOFTWARE** | | **$0** |
| **TOTAL HARDWARE** | | **$249** (one Jetson kit) |

---

## NVIDIA Stack (Detailed)

### MUST USE
1. **NVIDIA Developer Program** — Free, sign up first
2. **NVIDIA NIM** — Free hosted API at build.nvidia.com
   - Llama 3.1 8B for geological reports
   - Cosmos Reason2-8B for mineral image classification
3. **NVIDIA TAO Toolkit** — Free training
   - Fine-tune DINOv2/SigLip2 on mineral photos
   - Export to TensorRT for Jetson deployment
4. **NVIDIA RAPIDS** — Free, open-source
   - cuML for kriging/geostatistics
   - cuSpatial for spatial analysis
5. **NVIDIA Jetson Orin Nano** — $249
   - 100 TOPS AI performance
   - Replaces Raspberry Pi
   - Runs TAO-optimized models offline

### SHOULD USE
6. **NVIDIA Inception Program** — Apply for free cloud credits
7. **NVIDIA Triton** — Self-hosted model serving
8. **NVIDIA NeMo** — Fine-tune LLM on geological data

### CRITICAL CORRECTION
- **Earth-2 is NOT for satellite mineral mapping** — it's weather/climate only
- Use **Google Earth Engine** (free) for Sentinel-2 satellite analysis

---

## Repository Structure

```
afrimine-ai/
├── README.md
├── LICENSE (MIT)
├── CONTRIBUTING.md
├── PROJECT.md (this file)
├── docs/
│   ├── architecture/
│   │   └── system-architecture.md
│   └── research/
│       ├── nvidia-free-features.md ⭐ NEW
│       ├── ai-mining-tools.md
│       ├── quantum-mining.md
│       ├── drone-sensors.md
│       ├── financial-model.md
│       ├── legal-playbook.md
│       ├── implementation-roadmap.md
│       └── mineral-detection-system.md
├── src/
│   ├── backend/ (Go)
│   ├── frontend/ (Flutter)
│   ├── ai-engine/ (Python)
│   ├── edge/ (Jetson)
│   ├── satellite/ (GEE)
│   └── quantum/ (Qiskit)
├── scripts/
├── tests/
├── config/
└── .github/
```

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Chinese offer vs real value | 1M KES vs 28M+ KES (28:1 ratio) |
| Total NVIDIA software cost | $0 |
| Total edge hardware cost | $249 (one Jetson kit) |
| MVP budget | $80-120K |
| MVP timeline | 4 months |
| Team size | 5 people |
| Mineral classification accuracy target | >75% (MVP), >85% (Production) |

---

## Immediate Next Steps

1. Valentine approves revised architecture (with Jetson + NVIDIA stack)
2. Create GitHub repo (push this local repo)
3. Apply for NVIDIA Inception Program
4. Sign up for NVIDIA Developer Program
5. Begin Phase 0 legal actions (see legal playbook)
6. Recruit Flutter + Go developers
