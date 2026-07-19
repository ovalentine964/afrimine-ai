# AfriMine AI — Authentication Architecture

**Date:** 2026-07-19
**Scope:** Supabase Auth, RBAC, API key management, token rotation

---

## 1. Authentication Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 AUTHENTICATION FLOW                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  User Types:                                                 │
│  ├── Field Worker → Phone OTP (SMS)                         │
│  ├── Geologist → Email + Password + MFA                     │
│  ├── Investor → Email + Password + MFA                      │
│  └── Admin → Email + Password + MFA + Hardware Key          │
│                                                              │
│  Token Flow:                                                 │
│  ├── Supabase Auth issues JWT (15 min expiry)               │
│  ├── Refresh token rotation (7 day max)                     │
│  ├── JWT contains user_id + role claims                     │
│  └── RLS policies read JWT for access decisions             │
│                                                              │
│  Agent Authentication:                                       │
│  ├── Each agent has its own Supabase service key            │
│  ├── Agent keys scoped to specific tables                   │
│  ├── Agent keys rotated every 30 days                       │
│  └── Agent keys stored in environment variables only        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Supabase Auth Configuration

### 2.1 User Roles Table

```sql
-- User roles table (extends Supabase auth.users)
CREATE TABLE user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (
        role IN ('field_worker', 'geologist', 'investor', 'admin')
    ),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id),
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, role)
);

-- Index for fast role lookups
CREATE INDEX idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX idx_user_roles_role ON user_roles(role);

-- RLS: Users can read their own roles
CREATE POLICY user_roles_select ON user_roles
    FOR SELECT USING (auth.uid() = user_id);

-- Only admins can modify roles
CREATE POLICY user_roles_admin ON user_roles
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM user_roles
            WHERE user_id = auth.uid()
            AND role = 'admin'
            AND is_active = TRUE
        )
    );
```

### 2.2 Geologist Region Assignments

```sql
-- Geologists are assigned to specific regions
CREATE TABLE geologist_regions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    region TEXT NOT NULL,  -- e.g., "Nyatike", "Migori"
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_by UUID REFERENCES auth.users(id),
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, region)
);

CREATE INDEX idx_geologist_regions_user ON geologist_regions(user_id);
CREATE INDEX idx_geologist_regions_region ON geologist_regions(region);
```

### 2.3 Investor Site Access

```sql
-- Investors are granted access to specific mining sites
CREATE TABLE investor_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES mining_sites(id) ON DELETE CASCADE,
    access_level TEXT DEFAULT 'read' CHECK (
        access_level IN ('read', 'read_write')
    ),
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    granted_by UUID REFERENCES auth.users(id),
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, site_id)
);

CREATE INDEX idx_investor_access_user ON investor_access(user_id);
CREATE INDEX idx_investor_access_site ON investor_access(site_id);
```

---

## 3. Role-Based Access Control (RBAC)

### 3.1 Role Permissions Matrix

| Permission | Field Worker | Geologist | Investor | Admin |
|-----------|-------------|-----------|----------|-------|
| **Samples** | | | | |
| Create samples | ✅ Own region | ❌ | ❌ | ✅ |
| Read samples | ✅ Own samples | ✅ Assigned region | 🔶 Sanitized | ✅ All |
| Update samples | ✅ Own samples | ❌ | ❌ | ✅ All |
| Delete samples | ❌ | ❌ | ❌ | ✅ |
| **Analyses** | | | | |
| Read analyses | ✅ Own samples | ✅ Assigned region | 🔶 Summary | ✅ All |
| Create analyses | ❌ (agent only) | ❌ (agent only) | ❌ | ✅ |
| **Mining Sites** | | | | |
| Read locations | ✅ Own sites | ✅ Assigned region | 🔶 Region only | ✅ All |
| **Landowners** | | | | |
| Read PII | ✅ Own data | ❌ | ❌ | ✅ All |
| Update PII | ✅ Own data | ❌ | ❌ | ✅ All |
| **Reports** | | | | |
| Read reports | ✅ Own samples | ✅ Assigned region | ✅ Granted sites | ✅ All |
| Generate reports | ❌ (agent only) | ❌ (agent only) | ❌ | ✅ |
| **Compliance** | | | | |
| Read compliance | ❌ | ✅ Assigned region | ❌ | ✅ All |
| Update compliance | ❌ | ❌ | ❌ | ✅ |
| **System** | | | | |
| View audit logs | ❌ | ❌ | ❌ | ✅ |
| Manage users | ❌ | ❌ | ❌ | ✅ |
| Manage API keys | ❌ | ❌ | ❌ | ✅ |
| Export data | ❌ | ❌ | ✅ Sanitized | ✅ Full |

### 3.2 JWT Claims

```sql
-- Function to add role claims to JWT
CREATE OR REPLACE FUNCTION get_user_claims(user_id UUID)
RETURNS JSONB AS $$
DECLARE
    user_roles TEXT[];
    claims JSONB;
BEGIN
    -- Get all active roles
    SELECT ARRAY_AGG(role) INTO user_roles
    FROM user_roles
    WHERE user_roles.user_id = get_user_claims.user_id
    AND is_active = TRUE;

    -- Build claims
    claims := jsonb_build_object(
        'roles', COALESCE(user_roles, ARRAY[]::TEXT[]),
        'is_admin', 'admin' = ANY(user_roles),
        'is_geologist', 'geologist' = ANY(user_roles),
        'is_field_worker', 'field_worker' = ANY(user_roles),
        'is_investor', 'investor' = ANY(user_roles)
    );

    RETURN claims;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### 3.3 Auth Middleware (Go Backend)

```go
// middleware/auth.go
package middleware

import (
    "context"
    "net/http"
    "strings"

    "github.com/golang-jwt/jwt/v5"
)

type contextKey string

const (
    UserIDKey   contextKey = "user_id"
    UserRoleKey contextKey = "user_role"
)

func AuthMiddleware(jwtSecret string) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            // Extract token from Authorization header
            authHeader := r.Header.Get("Authorization")
            if authHeader == "" {
                http.Error(w, "Missing authorization header", http.StatusUnauthorized)
                return
            }

            tokenString := strings.TrimPrefix(authHeader, "Bearer ")
            if tokenString == authHeader {
                http.Error(w, "Invalid authorization format", http.StatusUnauthorized)
                return
            }

            // Validate JWT
            token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
                return []byte(jwtSecret), nil
            })

            if err != nil || !token.Valid {
                http.Error(w, "Invalid token", http.StatusUnauthorized)
                return
            }

            claims, ok := token.Claims.(jwt.MapClaims)
            if !ok {
                http.Error(w, "Invalid token claims", http.StatusUnauthorized)
                return
            }

            // Extract user ID and role
            userID, ok := claims["sub"].(string)
            if !ok {
                http.Error(w, "Invalid user ID in token", http.StatusUnauthorized)
                return
            }

            // Get roles from custom claims
            roles, _ := claims["roles"].([]interface{})
            role := "field_worker" // default
            if len(roles) > 0 {
                role, _ = roles[0].(string)
            }

            // Add to context
            ctx := context.WithValue(r.Context(), UserIDKey, userID)
            ctx = context.WithValue(ctx, UserRoleKey, role)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}

// RoleGuard returns middleware that requires specific roles
func RoleGuard(allowedRoles ...string) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            role, ok := r.Context().Value(UserRoleKey).(string)
            if !ok {
                http.Error(w, "Unauthorized", http.StatusUnauthorized)
                return
            }

            allowed := false
            for _, allowedRole := range allowedRoles {
                if role == allowedRole {
                    allowed = true
                    break
                }
            }

            if !allowed {
                http.Error(w, "Forbidden: insufficient permissions", http.StatusForbidden)
                return
            }

            next.ServeHTTP(w, r)
        })
    }
}
```

---

## 4. Field Worker Authentication (Phone OTP)

### 4.1 Why Phone OTP

- Mining community members may not have email addresses
- Phone numbers are already collected for contact purposes
- SMS is familiar and trusted in rural Kenya
- Supabase Auth supports phone OTP natively

### 4.2 Implementation

```dart
// flutter/lib/services/auth_service.dart
import 'package:supabase_flutter/supabase_flutter.dart';

class AuthService {
  final SupabaseClient _supabase = Supabase.instance.client;

  // Send OTP to phone number
  Future<void> sendPhoneOTP(String phoneNumber) async {
    await _supabase.auth.signInWithOtp(
      phone: phoneNumber,
      // Kenya phone format: +254XXXXXXXXX
    );
  }

  // Verify OTP and sign in
  Future<AuthResponse> verifyPhoneOTP(String phoneNumber, String token) async {
    final response = await _supabase.auth.verifyOTP(
      phone: phoneNumber,
      token: token,
      type: OtpType.sms,
    );
    return response;
  }

  // Check if user has a role assigned
  Future<String?> getUserRole() async {
    final user = _supabase.auth.currentUser;
    if (user == null) return null;

    final response = await _supabase
        .from('user_roles')
        .select('role')
        .eq('user_id', user.id)
        .eq('is_active', true)
        .limit(1)
        .single();

    return response['role'] as String?;
  }

  // Sign out
  Future<void> signOut() async {
    await _supabase.auth.signOut();
  }
}
```

### 4.3 Phone Number Validation

```go
// middleware/phone_validation.go
package middleware

import (
    "regexp"
    "strings"
)

// Kenya phone number patterns
var kenyaPhoneRegex = regexp.MustCompile(`^\+254[17]\d{8}$`)

func ValidateKenyaPhone(phone string) (string, bool) {
    // Normalize: remove spaces, dashes
    phone = strings.ReplaceAll(phone, " ", "")
    phone = strings.ReplaceAll(phone, "-", "")

    // Convert 07XXXXXXXX to +2547XXXXXXXX
    if strings.HasPrefix(phone, "07") || strings.HasPrefix(phone, "01") {
        phone = "+254" + phone[1:]
    }

    // Validate format
    if !kenyaPhoneRegex.MatchString(phone) {
        return "", false
    }

    return phone, true
}
```

---

## 5. API Key Management for LLM Providers

### 5.1 Key Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  API KEY ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Each agent gets its own API key per provider:               │
│                                                              │
│  ┌─────────────┬────────────────┬───────────────┐           │
│  │ Agent       │ Gemini Key     │ Other Keys    │           │
│  ├─────────────┼────────────────┼───────────────┤           │
│  │ Sampling    │ GEMINI_KEY_SAM │ —             │           │
│  │ Analysis    │ GEMINI_KEY_ANA │ GROQ_KEY_ANA  │           │
│  │ Geology     │ GEMINI_KEY_GEO │ —             │           │
│  │ Market      │ —              │ — (no LLM)    │           │
│  │ Report      │ GEMINI_KEY_REP │ MISTRAL_KEY   │           │
│  │ Compliance  │ GEMINI_KEY_COM │ —             │           │
│  └─────────────┴────────────────┴───────────────┘           │
│                                                              │
│  Benefits:                                                   │
│  ├── If one key leaks, only one agent is affected           │
│  ├── Per-agent rate limiting is possible                    │
│  ├── Usage tracking per agent                               │
│  └── Key rotation doesn't affect other agents               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Key Storage

```bash
# .env.example (NEVER commit actual keys)
# Agent-specific Gemini keys
GEMINI_KEY_SAMPLING=your_key_here
GEMINI_KEY_ANALYSIS=your_key_here
GEMINI_KEY_GEOLOGY=your_key_here
GEMINI_KEY_REPORT=your_key_here
GEMINI_KEY_COMPLIANCE=your_key_here

# Backup LLM keys
GROQ_KEY_ANALYSIS=your_key_here
MISTRAL_KEY_REPORT=your_key_here

# Database
SUPABASE_URL=your_project_url
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_key

# Encryption
APP_ENCRYPTION_KEY=your_256_bit_key
```

### 5.3 Key Rotation Strategy

```python
# security/key_rotation.py
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List

class APIKeyRotationManager:
    """Manages API key rotation for all agents."""

    ROTATION_INTERVAL_DAYS = 30
    WARNING_DAYS_BEFORE = 7

    KEY_REGISTRY = {
        "gemini_sampling": {"provider": "google", "agent": "sampling"},
        "gemini_analysis": {"provider": "google", "agent": "analysis"},
        "gemini_geology": {"provider": "google", "agent": "geology"},
        "gemini_report": {"provider": "google", "agent": "report"},
        "gemini_compliance": {"provider": "google", "agent": "compliance"},
        "groq_analysis": {"provider": "groq", "agent": "analysis"},
        "mistral_report": {"provider": "mistral", "agent": "report"},
    }

    def __init__(self, rotation_log_path: str = ".key_rotation_log.json"):
        self.log_path = rotation_log_path
        self._load_log()

    def _load_log(self):
        """Load rotation log from file."""
        try:
            with open(self.log_path, 'r') as f:
                self.rotation_log = json.load(f)
        except FileNotFoundError:
            self.rotation_log = {}

    def _save_log(self):
        """Save rotation log to file."""
        with open(self.log_path, 'w') as f:
            json.dump(self.rotation_log, f, indent=2, default=str)

    def record_rotation(self, key_name: str, rotated_by: str):
        """Record that a key was rotated."""
        self.rotation_log[key_name] = {
            "last_rotated": datetime.utcnow().isoformat(),
            "rotated_by": rotated_by,
            "next_rotation": (
                datetime.utcnow() + timedelta(days=self.ROTATION_INTERVAL_DAYS)
            ).isoformat(),
        }
        self._save_log()

    def get_keys_needing_rotation(self) -> List[Dict]:
        """Get list of keys that need rotation soon."""
        needs_rotation = []
        now = datetime.utcnow()
        warning_date = now + timedelta(days=self.WARNING_DAYS_BEFORE)

        for key_name, info in self.KEY_REGISTRY.items():
            log_entry = self.rotation_log.get(key_name)
            if not log_entry:
                needs_rotation.append({
                    "key": key_name,
                    "reason": "never_rotated",
                    "agent": info["agent"],
                })
                continue

            next_rotation = datetime.fromisoformat(log_entry["next_rotation"])
            if next_rotation <= warning_date:
                needs_rotation.append({
                    "key": key_name,
                    "reason": "due_soon" if next_rotation > now else "overdue",
                    "next_rotation": log_entry["next_rotation"],
                    "agent": info["agent"],
                })

        return needs_rotation

    def rotate_key(self, key_name: str, new_key_value: str, rotated_by: str):
        """Rotate an API key."""
        if key_name not in self.KEY_REGISTRY:
            raise ValueError(f"Unknown key: {key_name}")

        # Update environment variable
        env_var = key_name.upper()
        os.environ[env_var] = new_key_value

        # Log rotation
        self.record_rotation(key_name, rotated_by)

        print(f"[SECURITY] Rotated key '{key_name}' by '{rotated_by}'")

    def emergency_rotate_all(self, rotated_by: str):
        """Emergency rotation of ALL keys (used during incident response)."""
        print("[SECURITY] EMERGENCY: Rotating ALL API keys")
        for key_name in self.KEY_REGISTRY:
            # Generate placeholder - actual key generation happens externally
            self.record_rotation(key_name, rotated_by)
        print("[SECURITY] All keys marked for rotation. Update environment variables.")
```

### 5.4 Key Rotation Cron Job

```python
# scripts/check_key_rotation.py
"""Run weekly to check if any API keys need rotation."""
from security.key_rotation import APIKeyRotationManager

def main():
    manager = APIKeyRotationManager()
    needs_rotation = manager.get_keys_needing_rotation()

    if not needs_rotation:
        print("All API keys are current.")
        return

    print(f"\n⚠️  {len(needs_rotation)} API key(s) need rotation:\n")
    for key_info in needs_rotation:
        status = "🔴 OVERDUE" if key_info["reason"] == "overdue" else "🟡 DUE SOON"
        print(f"  {status}: {key_info['key']} (agent: {key_info['agent']})")

    print("\nRun rotation with:")
    print("  python -c \"from security.key_rotation import APIKeyRotationManager; ...\"")

if __name__ == "__main__":
    main()
```

---

## 6. Multi-Factor Authentication (MFA)

### 6.1 MFA Requirements by Role

| Role | MFA Required | Method |
|------|-------------|--------|
| Field Worker | No (phone OTP is single factor) | SMS OTP |
| Geologist | Yes | TOTP (Google Authenticator) |
| Investor | Yes | TOTP |
| Admin | Yes | TOTP + Hardware key (FIDO2) |

### 6.2 TOTP Setup for Geologists/Investors

```dart
// flutter/lib/services/mfa_service.dart
import 'package:supabase_flutter/supabase_flutter.dart';

class MFAService {
  final SupabaseClient _supabase = Supabase.instance.client;

  // Enroll in TOTP MFA
  Future<AuthMFAEnrollResponse> enrollTOTP() async {
    final response = await _supabase.auth.mfa.enroll();
    return response;
  }

  // Verify TOTP code
  Future<AuthMFAVerifyResponse> verifyTOTP(String code) async {
    final response = await _supabase.auth.mfa.challengeAndVerify(
      factorId: 'totp',
      code: code,
    );
    return response;
  }

  // Check if MFA is required for this session
  Future<bool> isMFARequired() async {
    final response = await _supabase.auth.mfa.getAuthenticatorAssuranceLevel();
    return response.currentLevel == 'aal1' &&
           response.nextLevel == 'aal2';
  }
}
```

---

## 7. Session Management

### 7.1 Token Configuration

```typescript
// supabase/config.toml (Supabase local config)
[auth]
# JWT expiry: 15 minutes
jwt_expiry = 900

# Refresh token expiry: 7 days
refresh_token_expiry = 604800

# Enable refresh token rotation
enable_refresh_token_rotation = true

# Reuse interval: 10 seconds (prevent rapid refresh attacks)
refresh_token_reuse_interval = 10

# Rate limit: 30 OTP requests per hour per phone
rate_limit_otp = 30

# Rate limit: 100 token refreshes per hour
rate_limit_token_refresh = 100
```

### 7.2 Session Invalidation

```sql
-- Function to invalidate all sessions for a user
-- Used during incident response or when a user is deactivated
CREATE OR REPLACE FUNCTION invalidate_user_sessions(target_user_id UUID)
RETURNS VOID AS $$
BEGIN
    -- Log the invalidation
    INSERT INTO audit_log (user_id, action, entity_type, entity_id, details)
    VALUES (
        auth.uid(),
        'SESSION_INVALIDATION',
        'user',
        target_user_id,
        jsonb_build_object('reason', 'admin_action', 'timestamp', NOW())
    );

    -- Supabase handles session invalidation via auth.users
    -- Update the user's session metadata
    UPDATE auth.users SET
        updated_at = NOW()
    WHERE id = target_user_id;

    -- Note: Supabase JWT tokens are stateless
    -- To force invalidation, update the JWT secret (nuclear option)
    -- Or use short expiry + refresh token rotation
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

---

## 8. Supabase Auth Security Checklist

- [ ] RLS enabled on ALL tables
- [ ] JWT expiry set to 15 minutes
- [ ] Refresh token rotation enabled
- [ ] Rate limiting on OTP endpoints
- [ ] MFA enforced for geologist/investor/admin roles
- [ ] Phone validation for Kenya numbers (+254)
- [ ] Email verification required for email-based accounts
- [ ] Password policy: minimum 12 characters, complexity requirements
- [ ] Account lockout after 5 failed attempts
- [ ] Audit logging on all auth events
- [ ] API keys stored in environment variables only
- [ ] API keys rotated every 30 days
- [ ] Service role key never exposed to frontend
- [ ] Anonymous key has minimal permissions (RLS enforced)
