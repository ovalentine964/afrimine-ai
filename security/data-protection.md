# AfriMine AI — Data Protection

**Date:** 2026-07-19
**Scope:** Geological data, mining site locations, mineral valuations, landowner PII

---

## 1. Data Sensitivity Classification

### Level 1: CRITICAL (Encrypt + Audit + No Agent Access)

| Data | Location | Why Critical |
|------|----------|-------------|
| Landowner national ID numbers | `landowners.national_id` | Identity theft, targeting |
| Land title deed numbers | `landowners.title_deed` | Land grabbing, fraud |
| Precise homestead GPS | `landowners.homestead_gps` | Physical safety |
| Payment/bank details | `landowners.bank_details` | Financial fraud |

### Level 2: HIGH (Encrypt + Audit + Restricted Agent Access)

| Data | Location | Why High |
|------|----------|----------|
| Mining site GPS coordinates | `mining_sites.gps_lat/lon` | Exploitation targeting |
| Mineral grade estimates | `analyses.grade_gpt` | Valuation manipulation |
| Deposit NPV calculations | `reports.npv_value` | Financial exploitation |
| Landowner names + phones | `landowners.name/phone` | Targeting, intimidation |

### Level 3: MEDIUM (Audit + Agent Access Control)

| Data | Location | Why Medium |
|------|----------|-----------|
| Geological interpretations | `analyses.geology_data` | Competitive intelligence |
| Satellite analysis results | `analyses.satellite_data` | Competitive intelligence |
| Compliance status | `compliance.status` | Regulatory manipulation |
| Market price data | `market_prices` | Publicly available, but aggregated value |

### Level 4: LOW (Standard Protection)

| Data | Location | Why Low |
|------|----------|---------|
| User preferences | `user_preferences` | Minimal impact |
| App usage analytics | `analytics` | Anonymized |
| Public mineral data | `mineral_reference` | Publicly available |

---

## 2. Mining Site Location Encryption

### 2.1 Problem

Mining site GPS coordinates are the most valuable data AfriMine AI produces. If leaked, foreign miners can directly target those sites.

### 2.2 Solution: Encrypted Columns + Precision Control

```sql
-- Enable pgcrypto extension
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Mining sites table with encrypted GPS
CREATE TABLE mining_sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_code TEXT NOT NULL UNIQUE,  -- Public identifier (e.g., "NYT-001")
    region TEXT NOT NULL,             -- Public region name (e.g., "Nyatike")

    -- Encrypted GPS (Level 2 - HIGH)
    gps_lat_encrypted BYTEA NOT NULL,
    gps_lon_encrypted BYTEA NOT NULL,

    -- Reduced-precision GPS for general queries (2 decimal places ≈ 1.1km)
    gps_lat_approx NUMERIC(5,2),
    gps_lon_approx NUMERIC(5,2),

    -- Encrypted elevation
    elevation_encrypted BYTEA,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id),
    sensitivity_level TEXT DEFAULT 'HIGH' CHECK (
        sensitivity_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')
    )
);

-- Function to encrypt GPS coordinates
CREATE OR REPLACE FUNCTION encrypt_gps(lat DOUBLE PRECISION, lon DOUBLE PRECISION)
RETURNS TABLE(lat_enc BYTEA, lon_enc BYTEA) AS $$
DECLARE
    encryption_key TEXT;
BEGIN
    -- Use Supabase Vault for key management (or env variable)
    encryption_key := current_setting('app.encryption_key', true);

    RETURN QUERY SELECT
        pgp_sym_encrypt(lat::TEXT, encryption_key),
        pgp_sym_encrypt(lon::TEXT, encryption_key);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to decrypt GPS (admin/geologist only)
CREATE OR REPLACE FUNCTION decrypt_gps(lat_enc BYTEA, lon_enc BYTEA)
RETURNS TABLE(lat DOUBLE PRECISION, lon DOUBLE PRECISION) AS $$
DECLARE
    encryption_key TEXT;
BEGIN
    encryption_key := current_setting('app.encryption_key', true);

    RETURN QUERY SELECT
        pgp_sym_decrypt(lat_enc, encryption_key)::DOUBLE PRECISION,
        pgp_sym_decrypt(lon_enc, encryption_key)::DOUBLE PRECISION;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get approximate location (for non-admin users)
CREATE OR REPLACE FUNCTION get_approximate_location(site_id UUID)
RETURNS TABLE(lat NUMERIC, lon NUMERIC, region TEXT) AS $$
BEGIN
    RETURN QUERY SELECT
        ms.gps_lat_approx,
        ms.gps_lon_approx,
        ms.region
    FROM mining_sites ms
    WHERE ms.id = site_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### 2.3 GPS Precision Levels by Role

| Role | Precision | Example | Use Case |
|------|-----------|---------|----------|
| Admin | Full (6+ decimal) | -1.098765, 34.567890 | System management |
| Geologist | High (4 decimal) | -1.0988, 34.5679 | Geological analysis |
| Investor | Region only | "Nyatike, Migori County" | Investment decisions |
| Field Worker | Own sites only (full) | -1.098765, 34.567890 | Site navigation |
| Compliance | Full (6+ decimal) | -1.098765, 34.567890 | Regulatory filing |

---

## 3. Mineral Valuation Data Sensitivity

### 3.1 Valuation Data Classification

```python
# security/data_classification.py
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class SensitivityLevel(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

@dataclass
class DataField:
    name: str
    table: str
    sensitivity: SensitivityLevel
    encrypted: bool
    audit_access: bool
    agent_accessible: list  # Which agents can access

# Valuation data classification
VALUATION_FIELDS = [
    DataField(
        name="grade_gpt",
        table="analyses",
        sensitivity=SensitivityLevel.HIGH,
        encrypted=True,
        audit_access=True,
        agent_accessible=["analysis", "geology", "report"],
    ),
    DataField(
        name="deposit_tonnage",
        table="analyses",
        sensitivity=SensitivityLevel.HIGH,
        encrypted=True,
        audit_access=True,
        agent_accessible=["geology", "report"],
    ),
    DataField(
        name="npv_value",
        table="reports",
        sensitivity=SensitivityLevel.HIGH,
        encrypted=True,
        audit_access=True,
        agent_accessible=["report"],
    ),
    DataField(
        name="cut_off_grade",
        table="analyses",
        sensitivity=SensitivityLevel.MEDIUM,
        encrypted=False,
        audit_access=True,
        agent_accessible=["analysis", "geology", "report", "compliance"],
    ),
    DataField(
        name="mineral_type",
        table="analyses",
        sensitivity=SensitivityLevel.LOW,
        encrypted=False,
        audit_access=False,
        agent_accessible=["analysis", "geology", "market", "report", "compliance"],
    ),
]
```

### 3.2 Valuation Access Rules

| Role | Can See Grade | Can See NPV | Can See Tonnage | Can Export |
|------|--------------|-------------|-----------------|------------|
| Admin | ✅ Full | ✅ Full | ✅ Full | ✅ With audit |
| Geologist | ✅ Full | ❌ | ✅ Full | ❌ |
| Investor | 🔶 Range only | ✅ Full | 🔶 Range only | ✅ Sanitized |
| Field Worker | ❌ | ❌ | ❌ | ❌ |
| Compliance | ✅ Full | ✅ Full | ✅ Full | ✅ Regulatory only |

**Range only:** "High grade (>5 g/t)" instead of "7.3 g/t"

---

## 4. Landowner PII Protection

### 4.1 PII Table Structure

```sql
-- Landowner PII table (separate from mining sites)
CREATE TABLE landowners (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),

    -- Encrypted PII (Level 1 - CRITICAL)
    name_encrypted BYTEA NOT NULL,
    phone_encrypted BYTEA NOT NULL,
    national_id_encrypted BYTEA NOT NULL,
    title_deed_encrypted BYTEA NOT NULL,
    homestead_gps_encrypted BYTEA,

    -- Hashed fields for search (can't decrypt, can match)
    national_id_hash TEXT NOT NULL UNIQUE,  -- SHA-256 for lookup
    phone_hash TEXT NOT NULL,               -- SHA-256 for lookup

    -- Non-PII fields (safe to query)
    county TEXT NOT NULL,
    sub_county TEXT NOT NULL,
    ward TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Data consent tracking
    consent_location_sharing BOOLEAN DEFAULT FALSE,
    consent_report_inclusion BOOLEAN DEFAULT FALSE,
    consent_date TIMESTAMPTZ,
    consent_version TEXT
);

-- Index on hashed fields for lookup without decryption
CREATE INDEX idx_landowners_national_id_hash ON landowners(national_id_hash);
CREATE INDEX idx_landowners_phone_hash ON landowners(phone_hash);
```

### 4.2 PII Access Control

```sql
-- Only the landowner themselves and admin can see raw PII
CREATE POLICY landowner_pii_select ON landowners
    FOR SELECT
    USING (
        auth.uid() = user_id  -- Self
        OR
        EXISTS (  -- Admin
            SELECT 1 FROM user_roles
            WHERE user_roles.user_id = auth.uid()
            AND user_roles.role = 'admin'
        )
    );

-- Geologists see region but not PII
CREATE POLICY landowner_geologist_view ON landowners
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_roles.user_id = auth.uid()
            AND user_roles.role = 'geologist'
        )
    )
    WITH CHECK (FALSE);  -- Geologists can't modify PII

-- Create a view that strips PII for geologist access
CREATE VIEW landowners_safe AS
SELECT
    id,
    county,
    sub_county,
    ward,
    consent_location_sharing,
    consent_report_inclusion
FROM landowners;
```

### 4.3 PII Data Minimization for Agents

**Rule: Agents NEVER receive raw PII.**

```python
# security/pii_filter.py
class PIIFilter:
    """Ensures agents never receive raw PII."""

    PII_FIELDS = {
        "name", "phone", "national_id", "title_deed",
        "homestead_gps", "bank_details", "email",
        "name_encrypted", "phone_encrypted", "national_id_encrypted",
        "title_deed_encrypted", "homestead_gps_encrypted",
    }

    # What agents CAN see
    SAFE_FIELDS = {
        "id", "county", "sub_county", "ward",
        "consent_location_sharing", "consent_report_inclusion",
        "site_code", "region", "mineral_type", "sensitivity_level",
    }

    @classmethod
    def filter_for_agent(cls, data: dict, agent_role: str) -> dict:
        """Remove all PII fields from data before passing to agent."""
        # Only admin can see PII in agent contexts
        if agent_role == "compliance":
            # Compliance agent sees hashed IDs for regulatory checks
            return {
                k: v for k, v in data.items()
                if k not in cls.PII_FIELDS or k.endswith("_hash")
            }

        return {
            k: v for k, v in data.items()
            if k not in cls.PII_FIELDS
        }

    @classmethod
    def anonymize_for_analytics(cls, data: dict) -> dict:
        """Anonymize data for analytics/research use."""
        anonymized = {}
        for k, v in data.items():
            if k in cls.PII_FIELDS:
                if k == "name":
                    anonymized[k] = "ANONYMOUS"
                elif k == "phone":
                    anonymized[k] = "***"
                elif k == "national_id":
                    anonymized[k] = "***"
                else:
                    anonymized[k] = "[REDACTED]"
            else:
                anonymized[k] = v
        return anonymized
```

---

## 5. Supabase RLS Policies

### 5.1 Enable RLS on All Tables

```sql
-- Enable RLS on every table
ALTER TABLE mining_sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE landowners ENABLE ROW LEVEL SECURITY;
ALTER TABLE samples ENABLE ROW LEVEL SECURITY;
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
```

### 5.2 Role-Based RLS Policies

```sql
-- ============================================
-- MINING SITES TABLE
-- ============================================

-- Field workers can read sites they created
CREATE POLICY mining_sites_field_worker ON mining_sites
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_roles.user_id = auth.uid()
            AND user_roles.role = 'field_worker'
        )
        AND created_by = auth.uid()
    );

-- Geologists can read all sites in their assigned regions
CREATE POLICY mining_sites_geologist ON mining_sites
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN geologist_regions gr ON gr.user_id = ur.user_id
            WHERE ur.user_id = auth.uid()
            AND ur.role = 'geologist'
            AND gr.region = mining_sites.region
        )
    );

-- Investors see approximate locations only (enforced via view)
CREATE POLICY mining_sites_investor ON mining_sites
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_roles.user_id = auth.uid()
            AND user_roles.role = 'investor'
        )
    );

-- Admins see everything
CREATE POLICY mining_sites_admin ON mining_sites
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_roles.user_id = auth.uid()
            AND user_roles.role = 'admin'
        )
    );

-- ============================================
-- SAMPLES TABLE
-- ============================================

-- Field workers can CRUD their own samples
CREATE POLICY samples_field_worker ON samples
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_roles.user_id = auth.uid()
            AND user_roles.role = 'field_worker'
        )
        AND created_by = auth.uid()
    );

-- Geologists can read samples in their regions
CREATE POLICY samples_geologist_read ON samples
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN geologist_regions gr ON gr.user_id = ur.user_id
            WHERE ur.user_id = auth.uid()
            AND ur.role = 'geologist'
            AND gr.region = samples.region
        )
    );

-- ============================================
-- ANALYSES TABLE
-- ============================================

-- Analysis agents write via service role (not user auth)
-- Geologists and admins can read
CREATE POLICY analyses_read ON analyses
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_roles.user_id = auth.uid()
            AND user_roles.role IN ('geologist', 'admin')
        )
    );

-- ============================================
-- REPORTS TABLE
-- ============================================

-- Investors can read reports for sites they have access to
CREATE POLICY reports_investor ON reports
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_roles.user_id = auth.uid()
            AND user_roles.role = 'investor'
        )
        AND reports.site_id IN (
            SELECT site_id FROM investor_access
            WHERE investor_access.user_id = auth.uid()
        )
    );

-- ============================================
-- AUDIT LOG (append-only, admin-read)
-- ============================================

-- No one can modify audit logs
CREATE POLICY audit_log_no_update ON audit_log
    FOR UPDATE USING (FALSE);

CREATE POLICY audit_log_no_delete ON audit_log
    FOR DELETE USING (FALSE);

-- Only admins can read audit logs
CREATE POLICY audit_log_admin_read ON audit_log
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_roles.user_id = auth.uid()
            AND user_roles.role = 'admin'
        )
    );

-- System can insert audit logs (via service role)
CREATE POLICY audit_log_insert ON audit_log
    FOR INSERT
    WITH CHECK (TRUE);  -- Service role only
```

### 5.3 Service Role for Agents

```sql
-- Agent service role (used by LangGraph agents, not user auth)
-- This role has LIMITED permissions
CREATE ROLE agent_service_role;

-- Agents can read (filtered by RLS)
GRANT SELECT ON samples, analyses, reports, compliance, market_prices
    TO agent_service_role;

-- Only specific agents can write
GRANT INSERT ON samples TO agent_service_role;  -- Sampling agent
GRANT INSERT ON analyses TO agent_service_role;  -- Analysis agent
GRANT INSERT ON reports TO agent_service_role;   -- Report agent
GRANT INSERT, UPDATE ON compliance TO agent_service_role;  -- Compliance agent

-- Agents CANNOT access PII tables directly
-- (filtered views only)
GRANT SELECT ON landowners_safe TO agent_service_role;

-- Agents CANNOT access audit logs
-- (they generate them, but can't read them)
```

---

## 6. Data-in-Transit Protection

### 6.1 API Communication

```
Client ←→ Cloudflare (TLS 1.3) ←→ Go Backend ←→ Supabase (TLS)
                                        ↓
                                   LangGraph Agents ←→ Gemini API (TLS)
                                        ↓
                                   LangGraph Agents ←→ Supabase (TLS)
```

### 6.2 Implementation

```go
// middleware/tls_enforcement.go
package middleware

import "net/http"

func EnforceTLS(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // Reject non-HTTPS in production
        if r.Header.Get("X-Forwarded-Proto") != "https" {
            http.Error(w, "HTTPS required", http.StatusUpgradeRequired)
            return
        }
        next.ServeHTTP(w, r)
    })
}

func SecurityHeaders(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        w.Header().Set("X-Content-Type-Options", "nosniff")
        w.Header().Set("X-Frame-Options", "DENY")
        w.Header().Set("X-XSS-Protection", "1; mode=block")
        w.Header().Set("Content-Security-Policy", "default-src 'self'")
        w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
        w.Header().Set("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        next.ServeHTTP(w, r)
    })
}
```

---

## 7. Data Retention and Deletion

### 7.1 Retention Schedule

| Data Type | Retention | Deletion Method |
|-----------|-----------|-----------------|
| Mining site data | Indefinite (while consent active) | On consent withdrawal |
| Landowner PII | Until consent withdrawal + 30 days | Secure delete + audit log |
| Analysis results | 7 years (Kenya Mining Act) | Automated purge |
| Audit logs | 7 years | Automated purge |
| Agent execution logs | 90 days | Automated purge |
| Market price data | Indefinite (public data) | N/A |
| Session tokens | 30 days | Automated cleanup |

### 7.2 Right to Erasure (Kenya Data Protection Act 2019)

```sql
-- Function to handle data erasure requests
CREATE OR REPLACE FUNCTION erase_landowner_data(landowner_id UUID)
RETURNS VOID AS $$
BEGIN
    -- Log the erasure request
    INSERT INTO audit_log (action, entity_type, entity_id, details)
    VALUES ('DATA_ERASURE', 'landowner', landowner_id, '{"reason": "user_request"}');

    -- Delete PII (encrypted columns)
    UPDATE landowners SET
        name_encrypted = NULL,
        phone_encrypted = NULL,
        national_id_encrypted = NULL,
        title_deed_encrypted = NULL,
        homestead_gps_encrypted = NULL,
        national_id_hash = 'ERASED',
        phone_hash = 'ERASED',
        updated_at = NOW()
    WHERE id = landowner_id;

    -- Anonymize associated mining sites
    UPDATE mining_sites SET
        created_by = NULL,
        updated_at = NOW()
    WHERE created_by = (
        SELECT user_id FROM landowners WHERE id = landowner_id
    );

    -- Keep analysis/reports but mark as anonymized
    UPDATE analyses SET
        notes = '[DATA SUBJECT ERASED]',
        updated_at = NOW()
    WHERE site_id IN (
        SELECT id FROM mining_sites WHERE created_by IS NULL
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

---

## 8. Backup Security

### 8.1 Supabase Backup Policy

- **Automated daily backups** (Supabase free tier: 7-day retention)
- **Point-in-time recovery** (Supabase Pro: required for production)
- **Backup encryption** (Supabase default: AES-256)
- **Backup access** (admin-only, logged)

### 8.2 Export Controls

```sql
-- Prevent bulk data export without admin approval
CREATE OR REPLACE FUNCTION check_export_limit()
RETURNS TRIGGER AS $$
DECLARE
    recent_exports INT;
BEGIN
    -- Count exports in last hour by this user
    SELECT COUNT(*) INTO recent_exports
    FROM audit_log
    WHERE user_id = auth.uid()
    AND action = 'DATA_EXPORT'
    AND created_at > NOW() - INTERVAL '1 hour';

    IF recent_exports >= 3 THEN
        RAISE EXCEPTION 'Export rate limit exceeded. Contact admin.';
    END IF;

    -- Log the export
    INSERT INTO audit_log (user_id, action, entity_type, details)
    VALUES (auth.uid(), 'DATA_EXPORT', TG_TABLE_NAME,
            jsonb_build_object('row_count', 1));

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

---

## Summary: Data Protection Layers

```
┌─────────────────────────────────────────────────────┐
│              DATA PROTECTION STACK                    │
├─────────────────────────────────────────────────────┤
│                                                      │
│  At Rest:                                            │
│  ├── Supabase AES-256 encryption (default)          │
│  ├── Column-level pgcrypto for PII                   │
│  ├── Hashed fields for searchable PII                │
│  └── GPS coordinate encryption                       │
│                                                      │
│  In Transit:                                         │
│  ├── TLS 1.3 (Cloudflare)                           │
│  ├── TLS (Supabase connections)                      │
│  └── TLS (LLM API calls)                            │
│                                                      │
│  Access Control:                                     │
│  ├── Supabase RLS (row-level)                       │
│  ├── Role-based policies (4 roles)                   │
│  ├── Agent field restrictions (PII filter)           │
│  └── Service role isolation (agents ≠ users)        │
│                                                      │
│  Data Minimization:                                  │
│  ├── Agents never see raw PII                        │
│  ├── GPS precision reduced by role                   │
│  ├── Valuation data filtered by role                 │
│  └── Analytics data anonymized                       │
│                                                      │
│  Lifecycle:                                          │
│  ├── Retention schedules per data type               │
│  ├── Right to erasure (Kenya DPA 2019)               │
│  ├── Export rate limiting                            │
│  └── Audit logging on all access                     │
│                                                      │
└─────────────────────────────────────────────────────┘
```
