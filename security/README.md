# AfriMine AI — Security Hardening Plan

**Date:** 2026-07-19
**Status:** Pre-Production Security Architecture
**Priority:** CRITICAL — Must implement before production deployment

---

## Why This Exists

54% of enterprises have already had AI agent security incidents in 2026 ([VentureBeat](https://venturebeat.com/ai/the-agent-security-gap-54-of-enterprises-have-already-had-an-ai-agent-incident-and-most-still-let-agents-share-credentials)). AfriMine AI handles:

- **Mining site GPS coordinates** — knowing where gold is = knowing where to steal it
- **Mineral valuations** — 28:1 exploitation ratios mean data = money
- **Landowner PII** — names, phone numbers, land titles, national IDs
- **Investor financial data** — deposit valuations, NPV calculations
- **Kenya Mining Act compliance data** — licenses, EIA reports, royalty calculations

A breach doesn't just expose data — it enables the exact exploitation AfriMine AI exists to prevent.

---

## Security Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 1: PERIMETER (Cloudflare)                                 │
│  ├── DDoS protection (free tier)                                │
│  ├── WAF rules (bot blocking, SQL injection)                    │
│  ├── Rate limiting (100 req/min per IP)                         │
│  └── TLS 1.3 everywhere                                         │
│                                                                  │
│  Layer 2: AUTHENTICATION (Supabase Auth)                         │
│  ├── Phone OTP for field workers (SMS)                          │
│  ├── Email/password for investors and admins                    │
│  ├── JWT tokens with short expiry (15 min)                      │
│  └── Refresh token rotation                                      │
│                                                                  │
│  Layer 3: AUTHORIZATION (Supabase RLS)                           │
│  ├── Role-based access: field_worker, geologist, investor, admin│
│  ├── Row-level security on every table                          │
│  ├── Column-level encryption for PII                            │
│  └── Agent-scoped credentials (each agent = own identity)       │
│                                                                  │
│  Layer 4: AGENT ISOLATION (LangGraph)                          │
│  ├── Per-agent API keys (Gemini/Groq/Mistral)                  │
│  ├── Per-agent rate limits                                       │
│  ├── Context window separation (no cross-contamination)         │
│  ├── Output sanitization (strip PII from agent outputs)         │
│  └── Sandbox execution for Report agent                         │
│                                                                  │
│  Layer 5: DATA PROTECTION                                        │
│  ├── AES-256 encryption at rest (Supabase default)              │
│  ├── TLS 1.3 in transit                                          │
│  ├── Column-level encryption for sensitive fields               │
│  ├── Data sensitivity classification (4 levels)                 │
│  └── PII field hashing for analytics                            │
│                                                                  │
│  Layer 6: MONITORING & AUDIT                                     │
│  ├── Agent action logging (every tool call)                     │
│  ├── Data access logging (who read what, when)                  │
│  ├── Error tracking (Sentry free tier)                          │
│  ├── Uptime monitoring (Uptime Robot free tier)                 │
│  └── Kenya Mining Act compliance audit trail                    │
│                                                                  │
│  Layer 7: INCIDENT RESPONSE                                      │
│  ├── Agent containment playbook                                  │
│  ├── Credential rotation procedures                              │
│  ├── Data breach notification (72h per Kenya Data Protection Act)│
│  └── Post-incident review process                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Security Documents

| Document | Purpose | Priority |
|----------|---------|----------|
| [threat-model.md](threat-model.md) | Complete threat model for 6-agent system | CRITICAL |
| [agent-security-hardening.md](agent-security-hardening.md) | Agent isolation, prompt injection defense, tool boundaries | CRITICAL |
| [data-protection.md](data-protection.md) | Geological data encryption, PII protection, RLS policies | CRITICAL |
| [authentication.md](authentication.md) | Supabase Auth, RBAC, API key management | CRITICAL |
| [audit-logging.md](audit-logging.md) | Agent action logging, compliance audit trail | HIGH |
| [incident-response.md](incident-response.md) | Security incident playbook | HIGH |
| [vulnerability-scanning.md](vulnerability-scanning.md) | Automated security scanning (VulnHunter + CI/CD) | HIGH |

---

## Design Principles

1. **Zero-cost security** — Use Supabase RLS, Cloudflare free tier, open-source tools only
2. **Defense in depth** — 7 layers, each independently effective
3. **Least privilege** — Every agent, user, and service gets minimum required access
4. **Assume breach** — Design for containment, not just prevention
5. **Audit everything** — Every data access and agent action is logged
6. **Kenya compliance** — Kenya Data Protection Act 2019 + Mining Act 2016

---

## Implementation Timeline

| Phase | Timeframe | Actions |
|-------|-----------|---------|
| **Phase 1: Foundation** | Week 1-2 | Supabase RLS policies, auth setup, agent credential isolation |
| **Phase 2: Agent Hardening** | Week 3-4 | Prompt injection defense, output sanitization, rate limiting |
| **Phase 3: Data Protection** | Week 5-6 | Column-level encryption, PII hashing, sensitivity classification |
| **Phase 4: Monitoring** | Week 7-8 | Audit logging, Sentry integration, compliance audit trail |
| **Phase 5: Incident Response** | Week 9-10 | Playbooks, credential rotation automation, breach notification |
| **Phase 6: Scanning** | Week 11-12 | VulnHunter CI/CD integration, penetration testing |

---

## Cost Impact: $0

Every security measure in this plan uses:
- Supabase free tier (RLS, Auth, column encryption)
- Cloudflare free tier (WAF, DDoS, rate limiting)
- Open-source tools (VulnHunter, Sentry free tier, Uptime Robot)
- Built-in Go/Flutter security features

Security does not add cost. It adds trust.
