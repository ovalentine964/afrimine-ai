# AfriMine AI — Mining Intelligence Platform

> **Democratizing mining intelligence for African communities.**
> AI-powered mineral detection, geological estimation, and operational decision-making — previously available only to major foreign mining corporations.

---

## The Problem

Chinese miners pay Kenyan families **1M KES (~$7,700)** for land containing **28M+ KES** in gold. That's a **28:1 extraction ratio** — they take 96.5% of the value while leaving the land destroyed.

**The root cause: Information asymmetry.** Foreign miners have geological survey data, portable XRF analyzers, and professional labs. Local families have none of that.

## The Solution

AfriMine AI gives mining communities the same technological capabilities as major foreign operations:

- 📷 **AI Mineral Detection** — Photograph a rock sample → get mineral ID, grade estimate, confidence score
- 🛰️ **Satellite Analysis** — Free Sentinel-2 imagery → alteration maps showing where gold/copper likely exists
- 📊 **Investor-Grade Reports** — One-click PDF reports that banks and investors take seriously
- 📱 **Works Offline** — Full functionality without internet. Syncs when connected.
- ⚛️ **Quantum-Enhanced** — Quantum computing for geochemical classification and pit optimization

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                                │
│                                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────────────┐ │
│  │ Flutter App  │  │ Flutter Web │  │ Flutter Desktop       │ │
│  │ (Field)      │  │ (Investor)  │  │ (Admin)               │ │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬───────────┘ │
│         └────────────────┼─────────────────────┘              │
└──────────────────────────┼────────────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────────────┐
│                  BACKEND (Go + Chi Router)                      │
│  Geology │ Samples │ Market │ Reports │ Auth │ Sync │ Quantum │
└───────┬──────────┬──────────┬──────────┬──────────────────────┘
        │          │          │          │
┌───────▼────┐ ┌──▼────────┐ ┌──────────▼────────┐
│ PostgreSQL │ │ MinIO     │ │ NVIDIA APIs       │
│ + PostGIS  │ │ Storage   │ │ NIM │ TAO │ Earth │
└────────────┘ └───────────┘ └───────────────────┘
```

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | **Flutter (Dart)** | One codebase → Android + iOS + Web |
| Backend | **Go (Chi)** | Single binary, edge-deployable, low memory |
| AI/ML | **NVIDIA NIM API** + TFLite fallback | Cloud inference with offline safety net |
| Database | **PostgreSQL + PostGIS** | Best spatial DB, free, battle-tested |
| Edge | **Raspberry Pi 5** | Offline-first, $300, solar-compatible |
| Quantum | **IBM Quantum + D-Wave** | Free tiers, real hardware |
| Storage | **MinIO** | S3-compatible, self-hosted, free |

## Cost Tiers

| Tier | Cost | What You Get |
|------|------|-------------|
| **Free** | $0 | Satellite analysis + AI mineral ID + report generator |
| **Basic** | $300 | + field test kits + lab validation |
| **Pro** | $2,500 | + XRF rental + drone mapping |
| **Full** | $10,000 | + professional equipment + quantum optimization |

## Research

All research documents are in [`docs/research/`](docs/research/):

- [NVIDIA Free Features Inventory](docs/research/nvidia-free-features.md)
- [AI Mining Tools Inventory](docs/research/ai-mining-tools.md)
- [Quantum Computing for Mining](docs/research/quantum-mining.md)
- [Drone & Sensor Systems](docs/research/drone-sensors.md)
- [Financial Model](docs/research/financial-model.md)
- [Legal Playbook](docs/research/legal-playbook.md)
- [Implementation Roadmap](docs/research/implementation-roadmap.md)

## Quick Start

```bash
# Clone
git clone https://github.com/afrimine/afrimine-ai.git
cd afrimine-ai

# Backend
cd src/backend
go mod download
go run main.go

# Frontend
cd src/frontend
flutter pub get
flutter run

# AI Engine
cd src/ai-engine
pip install -r requirements.txt
python main.py
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE)

## Acknowledgments

Built for Valentine Cohusdex and the mining communities of Nyatike, Migori County, Kenya.

---

**AfriMine AI** — Know Your Ground. 💰🌍
