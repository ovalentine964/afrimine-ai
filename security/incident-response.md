# AfriMine AI — Incident Response Playbook

**Date:** 2026-07-19
**Scope:** Security incident handling for the 6-agent system

---

## 1. Incident Classification

### Severity Levels

| Level | Name | Description | Response Time | Examples |
|-------|------|-------------|---------------|----------|
| **SEV-1** | CRITICAL | Active data breach, system compromise | < 1 hour | Database dump, API keys leaked, agent takeover |
| **SEV-2** | HIGH | Significant security event, potential breach | < 4 hours | Prompt injection success, unauthorized data access, credential theft |
| **SEV-3** | MEDIUM | Security anomaly, no immediate data risk | < 24 hours | Rate limit violations, failed auth attempts, suspicious patterns |
| **SEV-4** | LOW | Minor security event, informational | < 72 hours | Configuration drift, dependency vulnerability, minor policy violation |

---

## 2. Incident Response Team

For a zero-cost startup, the "team" is likely 1-2 people. Define roles nonetheless:

| Role | Responsibility | Contact |
|------|---------------|---------|
| **Incident Commander** | Overall coordination, decisions | Primary developer |
| **Technical Lead** | Investigation, containment, remediation | Primary developer |
| **Communications** | User notification, regulatory reporting | Project lead |

---

## 3. Incident Response Phases

```
┌─────────────────────────────────────────────────────────────┐
│              INCIDENT RESPONSE LIFECYCLE                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Phase 1: DETECT (0-15 min)                                 │
│  ├── Automated alerts (Sentry, audit log monitoring)        │
│  ├── Manual detection (user reports, log review)            │
│  └── External notification (security researcher, CVE)       │
│                                                              │
│  Phase 2: ASSESS (15-60 min)                                │
│  ├── Classify severity (SEV-1 through SEV-4)                │
│  ├── Identify affected systems and data                     │
│  ├── Determine attack vector                                │
│  └── Estimate blast radius                                  │
│                                                              │
│  Phase 3: CONTAIN (1-4 hours)                               │
│  ├── Stop the bleeding (revoke keys, block IPs)             │
│  ├── Isolate compromised components                         │
│  ├── Preserve evidence (logs, snapshots)                    │
│  └── Prevent lateral movement                               │
│                                                              │
│  Phase 4: ERADICATE (4-24 hours)                            │
│  ├── Remove attacker access                                 │
│  ├── Patch vulnerabilities                                  │
│  ├── Rotate all credentials                                 │
│  └── Verify system integrity                                │
│                                                              │
│  Phase 5: RECOVER (24-72 hours)                             │
│  ├── Restore from clean backups (if needed)                 │
│  ├── Re-enable services gradually                           │
│  ├── Monitor for re-compromise                              │
│  └── Verify data integrity                                  │
│                                                              │
│  Phase 6: REVIEW (1-2 weeks)                                │
│  ├── Post-incident review                                   │
│  ├── Update threat model                                    │
│  ├── Implement preventive measures                          │
│  └── Document lessons learned                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Playbook: Prompt Injection Attack

### Trigger
- Alert: "PROMPT_INJECTION_DETECTED" in audit log
- Agent output contains unexpected data (database contents, PII)
- User reports strange agent behavior

### Immediate Actions (0-15 min)

```bash
# 1. Check audit log for injection attempts
psql $DATABASE_URL -c "
SELECT timestamp, agent_role, details, ip_address
FROM audit_log
WHERE action = 'PROMPT_INJECTION_DETECTED'
AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;
"

# 2. Check if any agent output was not filtered
psql $DATABASE_URL -c "
SELECT timestamp, agent_role, details
FROM audit_log
WHERE action = 'AGENT_COMPLETE'
AND details->>'status' = 'success'
AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;
"

# 3. Check for data exfiltration (unusual queries)
psql $DATABASE_URL -c "
SELECT user_id, action, entity_type, details
FROM audit_log
WHERE risk_level IN ('HIGH', 'CRITICAL')
AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;
"
```

### Containment (15-60 min)

```bash
# 1. If injection was successful, disable the affected agent
# Update LangGraph configuration to disable the compromised agent
# (Implementation depends on deployment setup)

# 2. Block the attacker's IP (if identified)
# Cloudflare WAF → Security → Tools → IP Access Rules

# 3. Rotate the compromised agent's API keys
python -c "
from security.key_rotation import APIKeyRotationManager
manager = APIKeyRotationManager()
manager.rotate_key('gemini_SAMPLING', 'NEW_KEY_HERE', 'incident_response')
"

# 4. Review and tighten input validation patterns
# Add new injection patterns to the detection list
```

### Eradication (1-4 hours)

```bash
# 1. Identify the exact injection vector
# Review the input that triggered the injection

# 2. Add the specific pattern to input_sanitize.go
# and input_classifier.py

# 3. Test the fix with the malicious input

# 4. Verify no data was exfiltrated
psql $DATABASE_URL -c "
SELECT COUNT(*) as suspicious_queries
FROM audit_log
WHERE action IN ('SELECT', 'EXPORT')
AND risk_level = 'CRITICAL'
AND timestamp > NOW() - INTERVAL '24 hours';
"
```

### Recovery

```bash
# 1. Re-enable the agent with updated security prompts
# 2. Monitor for 24 hours
# 3. Review all agent outputs from the compromised period
```

---

## 5. Playbook: API Key Compromise

### Trigger
- Alert: Unusual API usage patterns
- API key found in public repository
- LLM provider reports suspicious activity

### Immediate Actions (0-15 min)

```bash
# 1. Identify which key was compromised
python -c "
from security.key_rotation import APIKeyRotationManager
manager = APIKeyRotationManager()
# Check all keys for recent usage anomalies
"

# 2. IMMEDIATELY rotate the compromised key
# Go to Google AI Studio / Groq / Mistral dashboard
# Generate new key, revoke old key

# 3. Update environment variables
# (Update in Supabase dashboard or deployment config)
```

### Containment (15-60 min)

```bash
# 1. Check what the attacker did with the key
# Review LLM provider usage dashboard

# 2. Check if the key was used to access Supabase
psql $DATABASE_URL -c "
SELECT * FROM audit_log
WHERE agent_role = 'COMPROMISED_AGENT'
AND timestamp > NOW() - INTERVAL '7 days'
ORDER BY timestamp DESC;
"

# 3. Rotate ALL keys (assume lateral compromise)
python -c "
from security.key_rotation import APIKeyRotationManager
manager = APIKeyRotationManager()
manager.emergency_rotate_all('incident_response')
"
```

### Eradication

```bash
# 1. Find how the key was leaked
# - Check git history: git log -p --all -S 'API_KEY_VALUE'
# - Check .env files in repo
# - Check CI/CD logs

# 2. Remove the key from all locations
# - Git filter-branch or BFG Repo-Cleaner
# - Rotate the key (already done)

# 3. Add secret scanning to CI/CD (see vulnerability-scanning.md)
```

---

## 6. Playbook: Data Breach (Mining Site Data)

### Trigger
- Alert: Bulk data export detected
- Mining site data found on unauthorized platform
- User reports their data was accessed without permission

### Immediate Actions (0-15 min)

```bash
# 1. STOP ALL AGENT OPERATIONS
# Disable LangGraph orchestrator immediately

# 2. Preserve evidence
psql $DATABASE_URL -c "
-- Snapshot recent audit logs
CREATE TABLE audit_log_emergency_backup AS
SELECT * FROM audit_log
WHERE timestamp > NOW() - INTERVAL '7 days';
"

# 3. Identify scope of breach
psql $DATABASE_URL -c "
-- What data was accessed?
SELECT entity_type, COUNT(*) as records_accessed,
       MIN(timestamp) as first_access,
       MAX(timestamp) as last_access
FROM audit_log
WHERE action IN ('SELECT', 'EXPORT', 'READ')
AND risk_level IN ('HIGH', 'CRITICAL')
AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY entity_type;
"

# 4. Identify the attacker
psql $DATABASE_URL -c "
SELECT user_id, ip_address, COUNT(*) as actions
FROM audit_log
WHERE risk_level IN ('HIGH', 'CRITICAL')
AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY user_id, ip_address
ORDER BY actions DESC;
"
```

### Containment (15-60 min)

```bash
# 1. Revoke all sessions for compromised accounts
psql $DATABASE_URL -c "
SELECT invalidate_user_sessions(user_id)
FROM user_roles
WHERE role = 'admin';  -- or specific compromised user
"

# 2. Rotate ALL credentials (database, API keys, encryption keys)

# 3. Block attacker IP addresses at Cloudflare level

# 4. Enable enhanced logging (increase audit detail level)
```

### Notification (Kenya Data Protection Act 2019)

**Legal requirement:** Notify the Office of the Data Protection Commissioner within 72 hours of becoming aware of a breach.

```
Notification must include:
1. Nature of the breach
2. Categories and approximate number of data subjects affected
3. Likely consequences of the breach
4. Measures taken or proposed to address the breach
5. Contact details of the Data Protection Officer

Template: See Section 43 of Kenya Data Protection Act 2019
```

### Recovery

```bash
# 1. Verify data integrity
# Compare current data with pre-breach backup

# 2. Notify affected landowners
# Send SMS to affected users explaining the breach and steps taken

# 3. Re-enable services with enhanced monitoring

# 4. Conduct full security audit before returning to normal operations
```

---

## 7. Playbook: Agent Takeover

### Trigger
- Agent generating unexpected outputs
- Agent accessing data outside its permission scope
- Agent executing unauthorized tool calls

### Immediate Actions (0-15 min)

```bash
# 1. Kill the compromised agent process
# Identify the process and terminate it

# 2. Disable the agent's API key immediately

# 3. Check what the agent accessed
psql $DATABASE_URL -c "
SELECT action, entity_type, entity_id, details
FROM audit_log
WHERE agent_role = 'COMPROMISED_AGENT'
AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC;
"
```

### Containment

```bash
# 1. Isolate the agent's Supabase credentials
# Revoke the agent's service role key

# 2. Review the agent's system prompt for tampering
# Check if the prompt was modified

# 3. Check for supply chain compromise
# Verify LangGraph dependency integrity
pip show crewai
pip check
```

### Eradication

```bash
# 1. Identify the attack vector
# - Prompt injection via user input?
# - Compromised dependency?
# - Insider threat?

# 2. Patch the vulnerability
# - Update input validation
# - Update dependencies
# - Rotate credentials

# 3. Re-deploy the agent with clean configuration
```

---

## 8. Credential Rotation Procedures

### 8.1 Supabase Keys

```bash
# Rotate Supabase service key
# 1. Go to Supabase Dashboard → Settings → API
# 2. Click "Rotate" on the service role key
# 3. Update the key in all deployment environments
# 4. Verify agents can still connect
# 5. Old key is automatically invalidated
```

### 8.2 LLM API Keys

```bash
# Rotate Gemini key
# 1. Go to Google AI Studio → API Keys
# 2. Create new key for the affected agent
# 3. Update environment variable
# 4. Test the agent with new key
# 5. Delete the old key

# Rotate Groq key
# 1. Go to Groq Console → API Keys
# 2. Create new key
# 3. Update environment variable
# 4. Test
# 5. Delete old key

# Rotate Mistral key
# 1. Go to Mistral Console → API Keys
# 2. Create new key
# 3. Update environment variable
# 4. Test
# 5. Delete old key
```

### 8.3 Encryption Keys

```bash
# Rotate Supabase column encryption key
# This requires re-encrypting all encrypted columns
# PLAN CAREFULLY — this is a major operation

# 1. Generate new encryption key
NEW_KEY=$(openssl rand -hex 32)

# 2. Create migration to re-encrypt data
# (Write a migration script that decrypts with old key, encrypts with new key)

# 3. Run migration during low-traffic period

# 4. Update the encryption key in Supabase config

# 5. Verify all encrypted data is accessible
```

---

## 9. Communication Templates

### 9.1 User Notification (Data Breach)

```
Subject: Important Security Notice — AfriMine AI

Dear [Name],

We are writing to inform you of a security incident that may have affected
your data on the AfriMine AI platform.

What happened:
[Brief description of the incident]

What data was involved:
[Types of data affected — e.g., mining site locations, analysis results]

What we are doing:
[Actions taken to contain and remediate]

What you can do:
[Steps users should take — e.g., change passwords, review account activity]

We take the security of your data very seriously and sincerely apologize
for any concern this may cause. We are implementing additional security
measures to prevent future incidents.

If you have questions, please contact us at [email].

Sincerely,
The AfriMine AI Team
```

### 9.2 Regulatory Notification (Kenya ODPC)

```
To: Office of the Data Protection Commissioner, Kenya
Subject: Data Breach Notification — AfriMine AI

Pursuant to Section 43 of the Data Protection Act, 2019, we hereby
notify you of a personal data breach:

1. Nature of the breach: [Description]
2. Categories of data subjects: [Landowners, investors, field workers]
3. Approximate number of data subjects: [Number]
4. Likely consequences: [Description]
5. Measures taken: [Description]
6. Contact: [DPO contact details]

Date of breach: [Date]
Date of discovery: [Date]
Date of this notification: [Within 72 hours of discovery]
```

---

## 10. Post-Incident Review Template

```markdown
# Post-Incident Review: [Incident ID]

**Date:** [Date]
**Severity:** [SEV-1/2/3/4]
**Incident Commander:** [Name]

## Timeline
- [Time] — Incident detected
- [Time] — Assessment completed
- [Time] — Containment achieved
- [Time] — Eradication completed
- [Time] — Recovery verified
- [Time] — Incident closed

## Root Cause
[What caused the incident]

## Impact
- Data affected: [Description]
- Users affected: [Number]
- Duration: [Time]
- Financial impact: [If any]

## What Went Well
- [Thing 1]
- [Thing 2]

## What Could Be Improved
- [Thing 1]
- [Thing 2]

## Action Items
| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| [Action 1] | [Name] | [Date] | [ ] |
| [Action 2] | [Name] | [Date] | [ ] |

## Lessons Learned
[Key takeaways]

## Updates to Security Posture
[Changes made as a result of this incident]
```

---

## 11. Emergency Contacts

| Contact | When to Use | How |
|---------|-------------|-----|
| Supabase Support | Database compromise | support@supabase.io |
| Google AI Support | Gemini key abuse | AI Studio support |
| Cloudflare Support | DDoS, WAF bypass | Cloudflare dashboard |
| Kenya ODPC | Data breach notification | dpc.go.ke |
| Sentry | Error tracking issues | sentry.io |

---

## 12. Incident Response Checklist

### SEV-1 (CRITICAL) Checklist

- [ ] Incident Commander identified
- [ ] Affected systems isolated
- [ ] Evidence preserved (logs, snapshots)
- [ ] All credentials rotated
- [ ] Attack vector identified and patched
- [ ] Data breach scope determined
- [ ] Legal notification prepared (72h deadline)
- [ ] User notification prepared
- [ ] Post-incident review scheduled
- [ ] Security posture updates documented

### SEV-2 (HIGH) Checklist

- [ ] Affected component identified
- [ ] Compromised credentials rotated
- [ ] Attack vector patched
- [ ] Audit logs reviewed for lateral movement
- [ ] Monitoring enhanced for affected area
- [ ] Post-incident review scheduled

### SEV-3 (MEDIUM) Checklist

- [ ] Anomaly documented
- [ ] Root cause identified
- [ ] Preventive measure implemented
- [ ] Monitoring adjusted

### SEV-4 (LOW) Checklist

- [ ] Event logged
- [ ] Added to backlog for review
- [ ] No immediate action required
