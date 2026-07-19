# AfriMine AI — Threat Model

**Date:** 2026-07-19
**Scope:** Complete 6-agent system (LangGraph + Go backend + Flutter + Supabase)

---

## System Under Analysis

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Flutter App  │────▶│ Go Backend  │────▶│ LangGraph      │
│ (field web)  │     │ (Chi API)   │     │ Orchestrator│
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┼──────────────────┐
                    │              │            │           │      │
               ┌────▼───┐  ┌─────▼──┐  ┌──────▼──┐  ┌────▼───┐  │
               │Sampling │  │Analysis│  │Geology  │  │Market  │  │
               │Agent    │  │Agent   │  │Agent    │  │Agent   │  │
               └────┬───┘  └─────┬──┘  └──────┬──┘  └────┬───┘  │
                    │            │            │           │      │
                    └────────────┴─────┬──────┴───────────┘      │
                                      │                          │
                                 ┌────▼────┐  ┌──────────┐      │
                                 │Report   │  │Compliance│      │
                                 │Agent    │  │Agent     │      │
                                 └─────────┘  └──────────┘      │
                                                                 │
                    External: Supabase │ Gemini │ Groq │ Mistral │
```

---

## Asset Classification

### A1: Mining Site Location Data (CRITICAL)
- GPS coordinates of mineral deposits
- Satellite imagery analysis results
- Geological survey data
- **Value:** Knowing where gold/copper is = direct financial exploitation
- **Impact if leaked:** Chinese miners or competitors can target specific landowners

### A2: Mineral Valuation Data (CRITICAL)
- Deposit grade estimates (g/t gold, % copper)
- NPV calculations, cut-off grades
- Block model data
- **Value:** 28:1 exploitation ratio — valuations directly enable negotiation exploitation
- **Impact if leaked:** Landowners lose negotiating leverage (the core problem AfriMine AI solves)

### A3: Landowner PII (HIGH)
- Full names, phone numbers, national ID numbers
- Land title numbers, GPS of homesteads
- Family information
- **Value:** Enables direct targeting and intimidation of landowners
- **Impact if leaked:** Physical safety risk to mining community members

### A4: Investor Data (HIGH)
- Contact information, investment amounts
- Due diligence reports, financial models
- **Value:** Competitive intelligence for rival platforms
- **Impact if leaked:** Investor confidence loss, legal liability

### A5: AI Model Credentials (HIGH)
- Gemini API keys, Groq API keys, Mistral API keys
- Supabase service keys, Cloudflare tokens
- **Value:** API abuse, data exfiltration, cost overruns
- **Impact if leaked:** Full system compromise

### A6: Agent System Internals (MEDIUM)
- LangGraph agent prompts and configurations
- Geological knowledge base (deposit models)
- ML model weights and training data
- **Value:** Competitive intelligence, prompt injection vectors
- **Impact if leaked:** System manipulation, competitive advantage loss

### A7: Compliance Data (MEDIUM)
- Kenya Mining Act filings
- EIA reports, license applications
- Royalty calculations
- **Value:** Regulatory manipulation, competitive intelligence
- **Impact if leaked:** Legal liability, regulatory penalties

---

## Threat Actors

### T1: Foreign Mining Companies (HIGH LIKELIHOOD)
- **Motivation:** Maintain information asymmetry for land exploitation
- **Capability:** Moderate — can hire technical talent, social engineering
- **Attack vectors:** Data scraping, API abuse, social engineering of field workers
- **Target:** A1 (locations), A2 (valuations), A3 (landowner contacts)

### T2: Competing Platforms (MEDIUM LIKELIHOOD)
- **Motivation:** Steal geological models, market intelligence
- **Capability:** High — technical teams, reverse engineering
- **Attack vectors:** API abuse, prompt injection, credential theft
- **Target:** A6 (agent internals), A2 (valuations)

### T3: Malicious Insiders (MEDIUM LIKELIHOOD)
- **Motivation:** Financial gain from selling data to foreign miners
- **Capability:** High — direct database access, knowledge of systems
- **Attack vectors:** Data exfiltration, privilege escalation
- **Target:** All assets

### T4: Nation-State Actors (LOW LIKELIHOOD, HIGH IMPACT)
- **Motivation:** Strategic mineral intelligence
- **Capability:** Very high — zero-days, supply chain attacks
- **Attack vectors:** Supply chain compromise, sophisticated phishing
- **Target:** A1, A2, A4

### T5: Opportunistic Attackers (HIGH LIKELIHOOD)
- **Motivation:** Financial (ransomware, crypto mining)
- **Capability:** Low-moderate — automated tools, known exploits
- **Attack vectors:** SQL injection, XSS, credential stuffing, DDoS
- **Target:** A5 (credentials for crypto mining), A4 (ransomware)

### T6: Prompt Injection via Field Input (HIGH LIKELIHOOD)
- **Motivation:** Manipulate agent outputs for financial gain
- **Capability:** Low — can craft malicious text/photo labels
- **Attack vectors:** Malicious voice notes, photo labels, sample descriptions
- **Target:** Agent system (all 6 agents via chained injection)

---

## Threat Matrix

| Threat | Actor | Asset | Likelihood | Impact | Risk |
|--------|-------|-------|------------|--------|------|
| Prompt injection via field input | T6 | Agent system | HIGH | HIGH | **CRITICAL** |
| Mining site data exfiltration | T1 | A1, A2 | HIGH | CRITICAL | **CRITICAL** |
| Landowner PII exposure | T1, T3 | A3 | HIGH | HIGH | **CRITICAL** |
| API key compromise | T2, T5 | A5 | MEDIUM | CRITICAL | **CRITICAL** |
| Agent credential sharing | T3 | All | HIGH | HIGH | **HIGH** |
| SQL injection | T5 | All | MEDIUM | CRITICAL | **HIGH** |
| LLM output manipulation | T6 | Reports | HIGH | MEDIUM | **HIGH** |
| Insider data exfiltration | T3 | All | MEDIUM | HIGH | **HIGH** |
| Supply chain compromise | T4 | All | LOW | CRITICAL | **MEDIUM** |
| DDoS against API | T5 | Availability | MEDIUM | MEDIUM | **MEDIUM** |
| Model poisoning | T2 | A6 | LOW | HIGH | **MEDIUM** |
| Compliance data manipulation | T1, T3 | A7 | LOW | HIGH | **MEDIUM** |

---

## Critical Attack Chains

### Chain 1: Prompt Injection → Data Exfiltration
```
Field worker submits malicious voice note
  → Transcribed text contains prompt injection
    → Sampling Agent executes injected instructions
      → Agent queries Supabase for all mining sites in region
        → Data exfiltrated via agent output
          → Foreign miner now knows exact gold locations
```
**Mitigation:** Input sanitization, agent output filtering, per-query RLS

### Chain 2: Credential Compromise → Full System Access
```
Leaked Gemini API key found in GitHub commit
  → Attacker uses key to impersonate Analysis Agent
    → Queries Supabase with stolen service key
      → Full database dump including landowner PII
        → Landowners targeted by foreign miners
```
**Mitigation:** Secret scanning, per-agent credential isolation, key rotation

### Chain 3: Agent Chain Escalation
```
Malicious input to Sampling Agent
  → Sampling Agent passes contaminated data to Analysis Agent
    → Analysis Agent includes contamination in its output
      → Geology Agent trusts Analysis Agent's output
        → Report Agent generates false valuation
          → Landowner receives manipulated report
```
**Mitigation:** Context window isolation, output validation, cross-agent trust boundaries

### Chain 4: Insider → Bulk Data Export
```
Compromised admin account
  → Exports all mining site locations
    → Sells data to foreign mining company
      → Targeted exploitation of 100+ landowners
```
**Mitigation:** Bulk export alerts, query rate limiting, admin action audit trail

---

## Attack Surface Map

| Surface | Entry Point | Exposure | Controls Needed |
|---------|------------|----------|-----------------|
| Flutter App | User input (photo, voice, text) | HIGH | Input validation, sanitization |
| Go API | HTTP endpoints | HIGH | Auth, rate limiting, WAF |
| LangGraph Agents | Tool calls, LLM prompts | HIGH | Agent isolation, output filtering |
| Supabase | SQL queries, RLS policies | MEDIUM | RLS hardening, query monitoring |
| Gemini/Groq/Mistral APIs | Prompt content | HIGH | Data minimization, no PII in prompts |
| Cloudflare Workers | Edge code execution | LOW | Standard hardening |
| GitHub Repository | Code/secret exposure | MEDIUM | Secret scanning, .gitignore |
| SMS/OTP | Social engineering | MEDIUM | Rate limiting, fraud detection |

---

## Security Requirements Derived

| ID | Requirement | Source | Priority |
|----|------------|--------|----------|
| SR-01 | Agent-scoped credentials (no shared keys) | Chain 2 | CRITICAL |
| SR-02 | Prompt injection detection and filtering | Chain 1, 3 | CRITICAL |
| SR-03 | Context window separation between agents | Chain 3 | CRITICAL |
| SR-04 | RLS policies on every Supabase table | Chain 1, 4 | CRITICAL |
| SR-05 | Column-level encryption for PII | T1, T3 | CRITICAL |
| SR-06 | API key rotation every 30 days | Chain 2 | HIGH |
| SR-07 | Agent output sanitization (strip PII) | Chain 1 | HIGH |
| SR-08 | Rate limiting per agent and per user | T5 | HIGH |
| SR-09 | Audit logging for all data access | Chain 4 | HIGH |
| SR-10 | Secret scanning in CI/CD | Chain 2 | HIGH |
| SR-11 | Bulk export detection and alerting | Chain 4 | HIGH |
| SR-12 | No PII in LLM prompts | Chain 1 | HIGH |
| SR-13 | Agent output validation before user display | Chain 3 | MEDIUM |
| SR-14 | Dependency vulnerability scanning | T4 | MEDIUM |
| SR-15 | Incident response playbook | All | HIGH |

---

## Residual Risk Acceptance

| Risk | Accepted? | Rationale |
|------|-----------|-----------|
| Nation-state supply chain attack | Yes | Beyond zero-cost budget; mitigate with dependency pinning |
| Model poisoning via fine-tuning | Yes | Not fine-tuning models; using pre-trained APIs |
| Physical device theft | Partially | Phone encryption + remote wipe (Supabase Auth revocation) |

---

## Review Schedule

- **Weekly:** Review new threat intelligence, update attack surface
- **Monthly:** Review access logs, rotate credentials
- **Quarterly:** Full threat model review, penetration testing
- **After any incident:** Immediate threat model update
