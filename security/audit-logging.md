# AfriMine AI — Audit Logging

**Date:** 2026-07-19
**Updated:** 2026-07-19 — Updated for LangGraph 1.0
**Scope:** Agent action logging, data access logging, Kenya Mining Act compliance trail

---

## 1. Logging Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   AUDIT LOGGING STACK                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Sources:                                                    │
│  ├── Go Backend API requests                                │
│  ├── LangGraph Agent actions                               │
│  ├── Supabase RLS access events                             │
│  ├── User authentication events                             │
│  └── Data modification events                               │
│                                                              │
│  Storage:                                                    │
│  ├── Supabase PostgreSQL (audit_log table) — primary        │
│  ├── Application logs (stdout) — secondary                  │
│  └── Sentry (errors only) — tertiary                        │
│                                                              │
│  Retention:                                                  │
│  ├── Audit logs: 7 years (Kenya Mining Act)                 │
│  ├── Auth events: 2 years                                   │
│  ├── Agent execution logs: 90 days                          │
│  └── Error logs: 1 year                                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Audit Log Schema

```sql
-- Main audit log table (append-only)
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Who
    user_id UUID REFERENCES auth.users(id),
    agent_role TEXT,  -- If action was by an agent
    session_id TEXT,
    ip_address INET,
    user_agent TEXT,

    -- What
    action TEXT NOT NULL,  -- e.g., 'READ', 'CREATE', 'UPDATE', 'DELETE', 'EXPORT', 'LOGIN'
    entity_type TEXT NOT NULL,  -- e.g., 'sample', 'analysis', 'report', 'landowner'
    entity_id UUID,

    -- Details
    details JSONB DEFAULT '{}',
    -- Example details:
    -- {"table": "samples", "columns": ["gps_lat", "gps_lon"], "row_count": 5}
    -- {"agent": "analysis", "tool": "classify_mineral", "input_hash": "abc123"}
    -- {"old_value": {"status": "pending"}, "new_value": {"status": "approved"}}

    -- Risk scoring
    risk_level TEXT DEFAULT 'LOW' CHECK (
        risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
    ),

    -- Compliance
    compliance_relevant BOOLEAN DEFAULT FALSE,
    kenya_mining_act_section TEXT,  -- If relevant to specific section

    -- Immutability (prevent updates/deletes)
    checksum TEXT  -- SHA-256 of row contents for tamper detection
);

-- Indexes for common queries
CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_agent ON audit_log(agent_role);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_log_risk ON audit_log(risk_level) WHERE risk_level IN ('HIGH', 'CRITICAL');
CREATE INDEX idx_audit_log_compliance ON audit_log(compliance_relevant) WHERE compliance_relevant = TRUE;

-- Prevent updates and deletes on audit log
CREATE POLICY audit_log_immutable_update ON audit_log FOR UPDATE USING (FALSE);
CREATE POLICY audit_log_immutable_delete ON audit_log FOR DELETE USING (FALSE);

-- Only admins can read audit logs
CREATE POLICY audit_log_read ON audit_log FOR SELECT USING (
    EXISTS (
        SELECT 1 FROM user_roles
        WHERE user_id = auth.uid()
        AND role = 'admin'
        AND is_active = TRUE
    )
);

-- System can insert (via service role)
CREATE POLICY audit_log_insert ON audit_log FOR INSERT WITH CHECK (TRUE);
```

---

## 3. Agent Action Logging

### 3.1 What to Log

Every LangGraph agent node action must be logged:

| Action | Log Level | Details Captured |
|--------|-----------|-----------------|
| Agent invocation | INFO | Agent role, input hash, timestamp |
| Tool call | INFO | Tool name, parameters hash, result hash |
| LLM API call | INFO | Model, token count, latency |
| Data read | INFO | Table, row count, columns accessed |
| Data write | INFO | Table, row ID, fields modified |
| Error | ERROR | Error type, message, stack trace |
| Rate limit hit | WARNING | Agent role, limit type |
| Permission denied | WARNING | Agent role, tool requested |
| Prompt injection detected | CRITICAL | Input hash, patterns matched |
| Output filtered | WARNING | Redaction count, types |

### 3.2 Implementation

```python
# security/audit_logger.py
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

@dataclass
class AuditEntry:
    timestamp: datetime
    user_id: Optional[str]
    agent_role: Optional[str]
    session_id: Optional[str]
    ip_address: Optional[str]
    action: str
    entity_type: str
    entity_id: Optional[str]
    details: Dict[str, Any]
    risk_level: str = "LOW"
    compliance_relevant: bool = False
    kenya_mining_act_section: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "agent_role": self.agent_role,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "details": json.dumps(self.details),
            "risk_level": self.risk_level,
            "compliance_relevant": self.compliance_relevant,
            "kenya_mining_act_section": self.kenya_mining_act_section,
        }

    def compute_checksum(self) -> str:
        """Compute SHA-256 checksum for tamper detection."""
        data = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()


class AuditLogger:
    """Audit logger for all AfriMine AI operations."""

    def __init__(self, supabase_client):
        self.db = supabase_client
        self._buffer: list = []
        self._buffer_size = 50  # Flush every 50 entries

    async def log(self, entry: AuditEntry):
        """Log an audit entry."""
        entry_dict = entry.to_dict()
        entry_dict["checksum"] = entry.compute_checksum()

        self._buffer.append(entry_dict)

        if len(self._buffer) >= self._buffer_size:
            await self.flush()

    async def flush(self):
        """Flush buffered audit entries to database."""
        if not self._buffer:
            return

        try:
            self.db.table("audit_log").insert(self._buffer).execute()
            self._buffer.clear()
        except Exception as e:
            # Don't lose audit logs — write to stderr as fallback
            import sys
            print(f"[AUDIT] Failed to write {len(self._buffer)} entries: {e}", file=sys.stderr)
            # Keep in buffer for retry
            raise

    # ============================================
    # CONVENIENCE METHODS
    # ============================================

    async def log_agent_action(self, agent_role: str, action: str,
                                entity_type: str, entity_id: str = None,
                                details: dict = None, risk_level: str = "LOW"):
        """Log an agent action."""
        await self.log(AuditEntry(
            timestamp=datetime.now(timezone.utc),
            user_id=None,
            agent_role=agent_role,
            session_id=None,
            ip_address=None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            risk_level=risk_level,
        ))

    async def log_data_access(self, user_id: str, action: str,
                               entity_type: str, entity_id: str = None,
                               columns: list = None, row_count: int = 1):
        """Log a data access event."""
        await self.log(AuditEntry(
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            agent_role=None,
            session_id=None,
            ip_address=None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details={
                "columns": columns,
                "row_count": row_count,
            },
            risk_level="MEDIUM" if action in ("READ", "EXPORT") else "LOW",
        ))

    async def log_auth_event(self, user_id: str, action: str,
                              ip_address: str = None, details: dict = None):
        """Log an authentication event."""
        await self.log(AuditEntry(
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            agent_role=None,
            session_id=None,
            ip_address=ip_address,
            action=action,
            entity_type="auth",
            entity_id=None,
            details=details or {},
            risk_level="MEDIUM" if action in ("LOGIN_FAILED", "MFA_FAILED") else "LOW",
        ))

    async def log_security_event(self, event_type: str, details: dict,
                                  risk_level: str = "HIGH",
                                  user_id: str = None,
                                  agent_role: str = None):
        """Log a security event (prompt injection, permission denied, etc.)."""
        await self.log(AuditEntry(
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            agent_role=agent_role,
            session_id=None,
            ip_address=None,
            action=event_type,
            entity_type="security",
            entity_id=None,
            details=details,
            risk_level=risk_level,
        ))

    async def log_compliance_event(self, action: str, entity_type: str,
                                    entity_id: str = None,
                                    mining_act_section: str = None,
                                    details: dict = None):
        """Log a Kenya Mining Act compliance-relevant event."""
        await self.log(AuditEntry(
            timestamp=datetime.now(timezone.utc),
            user_id=None,
            agent_role="compliance",
            session_id=None,
            ip_address=None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            risk_level="MEDIUM",
            compliance_relevant=True,
            kenya_mining_act_section=mining_act_section,
        ))
```

### 3.3 Agent Execution Logger

```python
# security/agent_execution_logger.py
import time
import json
from typing import Any, Dict
from contextlib import asynccontextmanager

class AgentExecutionLogger:
    """Logs LangGraph agent node executions with full trace."""

    def __init__(self, audit_logger: AuditLogger):
        self.audit = audit_logger

    @asynccontextmanager
    async def trace_agent(self, agent_role: str, input_data: dict):
        """Context manager that traces an agent execution."""
        execution_id = str(uuid.uuid4())
        start_time = time.time()

        # Log start
        await self.audit.log_agent_action(
            agent_role=agent_role,
            action="AGENT_START",
            entity_type="agent_execution",
            entity_id=execution_id,
            details={
                "input_hash": hashlib.sha256(
                    json.dumps(input_data, sort_keys=True).encode()
                ).hexdigest(),
                "input_size": len(json.dumps(input_data)),
            },
        )

        try:
            yield execution_id

            # Log success
            duration = time.time() - start_time
            await self.audit.log_agent_action(
                agent_role=agent_role,
                action="AGENT_COMPLETE",
                entity_type="agent_execution",
                entity_id=execution_id,
                details={
                    "duration_seconds": round(duration, 2),
                    "status": "success",
                },
            )

        except Exception as e:
            # Log failure
            duration = time.time() - start_time
            await self.audit.log_agent_action(
                agent_role=agent_role,
                action="AGENT_ERROR",
                entity_type="agent_execution",
                entity_id=execution_id,
                details={
                    "duration_seconds": round(duration, 2),
                    "status": "error",
                    "error_type": type(e).__name__,
                    "error_message": str(e)[:500],  # Truncate long errors
                },
                risk_level="HIGH",
            )
            raise

    async def log_tool_call(self, agent_role: str, execution_id: str,
                            tool_name: str, parameters: dict,
                            result: Any = None, error: str = None):
        """Log a tool call within an agent execution."""
        await self.audit.log_agent_action(
            agent_role=agent_role,
            action="TOOL_CALL",
            entity_type="tool",
            entity_id=execution_id,
            details={
                "tool": tool_name,
                "params_hash": hashlib.sha256(
                    json.dumps(parameters, sort_keys=True).encode()
                ).hexdigest(),
                "result_hash": hashlib.sha256(
                    str(result).encode()
                ).hexdigest() if result else None,
                "error": error[:500] if error else None,
            },
            risk_level="HIGH" if error else "LOW",
        )

    async def log_llm_call(self, agent_role: str, execution_id: str,
                           model: str, token_count: int,
                           latency_ms: int):
        """Log an LLM API call."""
        await self.audit.log_agent_action(
            agent_role=agent_role,
            action="LLM_CALL",
            entity_type="llm",
            entity_id=execution_id,
            details={
                "model": model,
                "token_count": token_count,
                "latency_ms": latency_ms,
            },
        )
```

---

## 4. Data Access Logging

### 4.1 Supabase RLS Access Logging

```sql
-- Trigger to log all data modifications
CREATE OR REPLACE FUNCTION log_data_modification()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_log (
        user_id,
        action,
        entity_type,
        entity_id,
        details,
        risk_level
    ) VALUES (
        auth.uid(),
        TG_OP,  -- INSERT, UPDATE, DELETE
        TG_TABLE_NAME,
        COALESCE(NEW.id, OLD.id),
        CASE
            WHEN TG_OP = 'DELETE' THEN
                jsonb_build_object('deleted_data', to_jsonb(OLD))
            WHEN TG_OP = 'UPDATE' THEN
                jsonb_build_object(
                    'old', to_jsonb(OLD),
                    'new', to_jsonb(NEW),
                    'changed_keys', (
                        SELECT jsonb_agg(key)
                        FROM jsonb_each(to_jsonb(NEW))
                        WHERE to_jsonb(OLD) -> key IS DISTINCT FROM to_jsonb(NEW) -> key
                    )
                )
            WHEN TG_OP = 'INSERT' THEN
                jsonb_build_object('new_data', to_jsonb(NEW))
        END,
        CASE
            WHEN TG_TABLE_NAME = 'landowners' THEN 'HIGH'
            WHEN TG_TABLE_NAME = 'mining_sites' THEN 'HIGH'
            WHEN TG_TABLE_NAME = 'audit_log' THEN 'CRITICAL'
            ELSE 'MEDIUM'
        END
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Apply triggers to sensitive tables
CREATE TRIGGER audit_mining_sites
    AFTER INSERT OR UPDATE OR DELETE ON mining_sites
    FOR EACH ROW EXECUTE FUNCTION log_data_modification();

CREATE TRIGGER audit_landowners
    AFTER INSERT OR UPDATE OR DELETE ON landowners
    FOR EACH ROW EXECUTE FUNCTION log_data_modification();

CREATE TRIGGER audit_samples
    AFTER INSERT OR UPDATE OR DELETE ON samples
    FOR EACH ROW EXECUTE FUNCTION log_data_modification();

CREATE TRIGGER audit_analyses
    AFTER INSERT OR UPDATE OR DELETE ON analyses
    FOR EACH ROW EXECUTE FUNCTION log_data_modification();

CREATE TRIGGER audit_reports
    AFTER INSERT OR UPDATE OR DELETE ON reports
    FOR EACH ROW EXECUTE FUNCTION log_data_modification();

CREATE TRIGGER audit_compliance
    AFTER INSERT OR UPDATE OR DELETE ON compliance
    FOR EACH ROW EXECUTE FUNCTION log_data_modification();

CREATE TRIGGER audit_user_roles
    AFTER INSERT OR UPDATE OR DELETE ON user_roles
    FOR EACH ROW EXECUTE FUNCTION log_data_modification();
```

### 4.2 Bulk Access Detection

```sql
-- Function to detect unusual bulk data access
CREATE OR REPLACE FUNCTION detect_bulk_access()
RETURNS TRIGGER AS $$
DECLARE
    recent_reads INT;
    threshold INT := 100;  -- Alert if >100 reads in 10 minutes
BEGIN
    -- Count recent reads by this user
    SELECT COUNT(*) INTO recent_reads
    FROM audit_log
    WHERE user_id = auth.uid()
    AND action = 'SELECT'
    AND entity_type = TG_TABLE_NAME
    AND timestamp > NOW() - INTERVAL '10 minutes';

    IF recent_reads > threshold THEN
        -- Log the bulk access alert
        INSERT INTO audit_log (
            user_id, action, entity_type, details, risk_level
        ) VALUES (
            auth.uid(),
            'BULK_ACCESS_ALERT',
            TG_TABLE_NAME,
            jsonb_build_object(
                'read_count', recent_reads,
                'threshold', threshold,
                'time_window', '10 minutes'
            ),
            'CRITICAL'
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

---

## 5. Kenya Mining Act Compliance Audit Trail

### 5.1 Compliance-Relevant Events

The Kenya Mining Act 2016 requires specific records. Map audit events to sections:

```python
# compliance/mining_act_sections.py
MINING_ACT_SECTIONS = {
    "section_35": {
        "title": "Mining Licenses",
        "description": "Records of mining license applications and approvals",
        "audit_events": ["LICENSE_APPLICATION", "LICENSE_APPROVAL", "LICENSE_REJECTION"],
        "retention_years": 7,
    },
    "section_36": {
        "title": "Mineral Rights",
        "description": "Records of mineral rights grants",
        "audit_events": ["RIGHTS_GRANT", "RIGHTS_TRANSFER", "RIGHTS_REVOCATION"],
        "retention_years": 7,
    },
    "section_103": {
        "title": "Royalty Calculations",
        "description": "Records of royalty calculations and payments",
        "audit_events": ["ROYALTY_CALCULATION", "ROYALTY_PAYMENT", "ROYALTY_AUDIT"],
        "retention_years": 7,
    },
    "section_104": {
        "title": "Environmental Impact Assessment",
        "description": "EIA reports and compliance records",
        "audit_events": ["EIA_SUBMISSION", "EIA_APPROVAL", "EIA_COMPLIANCE_CHECK"],
        "retention_years": 7,
    },
    "section_108": {
        "title": "Mine Safety",
        "description": "Safety compliance records",
        "audit_events": ["SAFETY_INSPECTION", "SAFETY_VIOLATION", "SAFETY_CORRECTIVE"],
        "retention_years": 5,
    },
    "section_126": {
        "title": "Artisanal Mining",
        "description": "Artisanal mining permits and compliance",
        "audit_events": ["ARTISANAL_PERMIT", "ARTISANAL_RENEWAL", "ARTISANAL_COMPLIANCE"],
        "retention_years": 7,
    },
}
```

### 5.2 Compliance Report Generator

```python
# compliance/audit_report.py
from datetime import datetime, timedelta
from typing import Dict, List

class ComplianceAuditReport:
    """Generates compliance audit reports for Kenya Mining Act."""

    def __init__(self, supabase_client):
        self.db = supabase_client

    async def generate_section_report(self, section: str,
                                       start_date: datetime,
                                       end_date: datetime) -> Dict:
        """Generate audit report for a specific Mining Act section."""
        section_info = MINING_ACT_SECTIONS.get(section)
        if not section_info:
            raise ValueError(f"Unknown section: {section}")

        # Query audit log for compliance-relevant events
        result = self.db.table("audit_log").select("*").eq(
            "compliance_relevant", True
        ).eq(
            "kenya_mining_act_section", section
        ).gte(
            "timestamp", start_date.isoformat()
        ).lte(
            "timestamp", end_date.isoformat()
        ).order("timestamp", desc=True).execute()

        events = result.data

        return {
            "section": section,
            "title": section_info["title"],
            "description": section_info["description"],
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_events": len(events),
            "events": events,
            "compliance_status": self._assess_compliance(events, section),
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def generate_full_report(self, start_date: datetime,
                                    end_date: datetime) -> Dict:
        """Generate full compliance audit report."""
        reports = {}
        for section in MINING_ACT_SECTIONS:
            reports[section] = await self.generate_section_report(
                section, start_date, end_date
            )

        return {
            "report_type": "full_compliance_audit",
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "sections": reports,
            "summary": self._generate_summary(reports),
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _assess_compliance(self, events: list, section: str) -> str:
        """Assess compliance status based on audit events."""
        if not events:
            return "NO_ACTIVITY"

        violations = [e for e in events if "VIOLATION" in e.get("action", "")]
        if violations:
            return "NON_COMPLIANT"

        return "COMPLIANT"

    def _generate_summary(self, reports: dict) -> dict:
        """Generate summary of all compliance sections."""
        total_events = sum(r["total_events"] for r in reports.values())
        non_compliant = sum(
            1 for r in reports.values()
            if r["compliance_status"] == "NON_COMPLIANT"
        )

        return {
            "total_events": total_events,
            "sections_compliant": len(reports) - non_compliant,
            "sections_non_compliant": non_compliant,
            "overall_status": "COMPLIANT" if non_compliant == 0 else "NON_COMPLIANT",
        }
```

---

## 6. Monitoring & Alerting

### 6.1 Alert Rules

| Alert | Condition | Severity | Channel |
|-------|-----------|----------|---------|
| Failed login attempts | >5 in 10 min from same IP | HIGH | Email + Sentry |
| Prompt injection detected | Any occurrence | CRITICAL | Email + Sentry + SMS |
| Bulk data export | >100 rows in 10 min | HIGH | Email + Sentry |
| Agent rate limit exceeded | >3 times in 1 hour | MEDIUM | Sentry |
| Permission denied | >10 in 1 hour from same user | HIGH | Email + Sentry |
| API key usage anomaly | >2x normal daily usage | MEDIUM | Email |
| Compliance violation | Any occurrence | HIGH | Email + Sentry |
| Admin action | Any admin action | LOW | Log only |

### 6.2 Sentry Integration

```python
# monitoring/sentry_setup.py
import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration

def setup_sentry(dsn: str, environment: str = "production"):
    """Initialize Sentry for error tracking (free tier: 5K events/month)."""
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=0.1,  # 10% of transactions
        profiles_sample_rate=0.1,
        integrations=[
            AsyncioIntegration(),
        ],
        # Don't send PII to Sentry
        send_default_pii=False,
        # Filter out known noise
        before_send=filter_sentry_events,
    )

def filter_sentry_events(event, hint):
    """Filter out noisy events before sending to Sentry."""
    # Don't send rate limit events (too noisy)
    if event.get("exception", {}).get("type") == "RateLimitExceeded":
        return None

    # Don't send validation errors (expected)
    if event.get("exception", {}).get("type") == "ValidationError":
        return None

    return event
```

---

## 7. Log Query Examples

### 7.1 Common Audit Queries

```sql
-- All actions by a specific user in the last 24 hours
SELECT timestamp, action, entity_type, entity_id, details
FROM audit_log
WHERE user_id = 'user-uuid-here'
AND timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;

-- All prompt injection attempts
SELECT timestamp, agent_role, details, ip_address
FROM audit_log
WHERE action = 'PROMPT_INJECTION_DETECTED'
ORDER BY timestamp DESC;

-- All data access to mining_sites table
SELECT timestamp, user_id, agent_role, action, details
FROM audit_log
WHERE entity_type = 'mining_sites'
AND timestamp > NOW() - INTERVAL '7 days'
ORDER BY timestamp DESC;

-- Compliance-relevant events for Kenya Mining Act
SELECT timestamp, action, entity_type, details, kenya_mining_act_section
FROM audit_log
WHERE compliance_relevant = TRUE
AND timestamp > NOW() - INTERVAL '30 days'
ORDER BY timestamp DESC;

-- High-risk events
SELECT timestamp, user_id, agent_role, action, entity_type, details
FROM audit_log
WHERE risk_level IN ('HIGH', 'CRITICAL')
AND timestamp > NOW() - INTERVAL '7 days'
ORDER BY timestamp DESC;

-- Agent execution summary
SELECT
    agent_role,
    COUNT(*) as total_actions,
    COUNT(*) FILTER (WHERE action = 'AGENT_ERROR') as errors,
    COUNT(*) FILTER (WHERE action = 'TOOL_CALL') as tool_calls,
    COUNT(*) FILTER (WHERE action = 'LLM_CALL') as llm_calls,
    AVG((details->>'duration_seconds')::NUMERIC) as avg_duration
FROM audit_log
WHERE entity_type = 'agent_execution'
AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY agent_role;
```

---

## Summary: Audit Logging Coverage

| Category | Coverage | Retention |
|----------|----------|-----------|
| Agent actions (all 6 agents) | ✅ Complete | 90 days |
| Data access (read/write/delete) | ✅ Complete (triggers) | 7 years |
| Authentication events | ✅ Complete | 2 years |
| API key usage | ✅ Complete | 90 days |
| Permission denials | ✅ Complete | 1 year |
| Prompt injection attempts | ✅ Complete | 7 years |
| Compliance events | ✅ Complete | 7 years (Mining Act) |
| Bulk export detection | ✅ Complete | 7 years |
| Admin actions | ✅ Complete | 7 years |
