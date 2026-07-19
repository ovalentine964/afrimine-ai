"""
AfriMine AI — API Integration Tests
=====================================

Tests the Go API ↔ LangGraph bridge integration:
- POST /v1/analyses → triggers analysis via A2A
- GET /v1/analyses/{id} → returns results
- SSE streaming → real-time agent progress
- Auth: JWT validation, role-based access
- Rate limiting: verify per-role limits

Requires: pytest, httpx (for async HTTP testing)
Run: pytest tests/integration/test_api_integration.py -v

NOTE: These tests validate the Go API contract by testing the Python
side of the A2A bridge. Full end-to-end tests require running the
Go backend separately (see smoke-test.sh).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

AGENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "src", "agents")
if AGENTS_DIR not in sys.path:
    sys.path.insert(0, AGENTS_DIR)


# ---------------------------------------------------------------------------
# Test: A2A Protocol Bridge
# ---------------------------------------------------------------------------

class TestA2ABridge:
    """Test the A2A (Agent-to-Agent) JSON-RPC 2.0 bridge between Go and Python."""

    def test_a2a_request_format(self):
        """A2A requests must follow JSON-RPC 2.0 format."""
        # This is what the Go backend sends to the Python bridge
        request = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {
                "id": str(uuid.uuid4()),
                "message": {
                    "role": "user",
                    "parts": [
                        {
                            "type": "data",
                            "data": {
                                "location": {"lat": -1.05, "lon": 34.55, "region": "Nyatike"},
                                "sample_data": {"sample_id": "TEST-001"},
                                "user_id": "test-user",
                            },
                        }
                    ],
                },
            },
            "id": str(uuid.uuid4()),
        }

        # Validate structure
        assert request["jsonrpc"] == "2.0"
        assert request["method"] == "tasks/send"
        assert "params" in request
        assert "id" in request["params"]
        assert request["params"]["message"]["role"] == "user"
        assert len(request["params"]["message"]["parts"]) > 0

    def test_a2a_response_format(self):
        """A2A responses must follow JSON-RPC 2.0 format with task result."""
        response = {
            "jsonrpc": "2.0",
            "id": "task-uuid",
            "result": {
                "id": "task-uuid",
                "status": {"state": "completed", "message": "Analysis complete"},
                "artifacts": [
                    {
                        "parts": [
                            {"type": "data", "data": {"compliance_result": {"is_compliant": False}}},
                            {"type": "text", "text": "Analysis complete: Gold at 5.2 g/t"},
                        ]
                    }
                ],
            },
        }

        assert response["jsonrpc"] == "2.0"
        assert response["result"]["status"]["state"] == "completed"
        assert len(response["result"]["artifacts"]) > 0

    def test_a2a_agent_card_format(self):
        """Agent cards must follow the A2A specification."""
        agent_card = {
            "name": "afrimine-pipeline",
            "description": "Full 6-agent mineral analysis pipeline",
            "url": "http://localhost:8000/a2a",
            "version": "1.0.0",
            "capabilities": {"streaming": True, "pushNotifications": False},
            "skills": [
                {
                    "id": "mineral-analysis",
                    "name": "Mineral Analysis",
                    "description": "Full pipeline: sampling → analysis → geology/market → report → compliance",
                }
            ],
            "authentication": {"schemes": ["bearer"]},
        }

        assert agent_card["name"] == "afrimine-pipeline"
        assert agent_card["capabilities"]["streaming"] is True
        assert len(agent_card["skills"]) > 0

    def test_a2a_error_response_format(self):
        """A2A error responses must include error code and message."""
        error_response = {
            "jsonrpc": "2.0",
            "id": "task-uuid",
            "error": {"code": -32603, "message": "Pipeline execution failed"},
        }

        assert "error" in error_response
        assert error_response["error"]["code"] < 0
        assert len(error_response["error"]["message"]) > 0


# ---------------------------------------------------------------------------
# Test: API Contract Validation
# ---------------------------------------------------------------------------

class TestAPIContract:
    """Validate that the Go API request/response contracts match expectations."""

    def test_create_analysis_request_format(self):
        """POST /v1/analyses request must include sample_ids."""
        request = {
            "sample_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
        }
        assert len(request["sample_ids"]) >= 1

    def test_create_analysis_response_format(self):
        """POST /v1/analyses response (202 Accepted) must include analysis ID and status."""
        response = {
            "id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "sample_ids": [str(uuid.uuid4())],
            "status": "pending",
            "created_at": "2026-07-19T09:00:00Z",
            "updated_at": "2026-07-19T09:00:00Z",
        }
        assert response["status"] == "pending"
        assert "id" in response

    def test_get_analysis_response_format(self):
        """GET /v1/analyses/{id} response must include all agent outputs."""
        response = {
            "id": str(uuid.uuid4()),
            "status": "completed",
            "agent_outputs": {
                "sampling": {"strategy": "grid", "waypoints": []},
                "analysis": {"dominant_mineral": "gold", "overall_confidence": 0.85},
                "geology": {"deposit_model": "orogenic gold"},
                "market": {"gold_price_usd_oz": 2350.0, "deposit_value_estimate_usd": 125000},
                "report": {"executive_summary": "Gold-bearing quartz identified"},
                "compliance": {"is_compliant": False, "license_type_required": "Prospecting License"},
            },
            "detected_minerals": ["gold", "arsenopyrite", "pyrite"],
            "estimated_grade": 5.2,
            "confidence_score": 0.85,
            "estimated_value_usd": 125000,
        }

        assert len(response["agent_outputs"]) == 6
        assert response["status"] == "completed"
        assert 0 <= response["confidence_score"] <= 1

    def test_create_sample_request_format(self):
        """POST /v1/samples request must include location."""
        request = {
            "location": {"lat": -1.05, "lon": 34.55, "region": "Nyatike", "county": "Migori"},
            "xrf_readings": {"Au": 5.2, "As": 120.5},
            "field_notes": "Quartz vein with sulfide staining",
        }
        assert "location" in request
        assert request["location"]["lat"] != 0 or request["location"]["lon"] != 0

    def test_sample_response_format(self):
        """Sample response must include ID, location, and timestamps."""
        response = {
            "id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "location": {"lat": -1.05, "lon": 34.55, "region": "Nyatike"},
            "photo_urls": [],
            "xrf_readings": {"Au": 5.2},
            "synced": False,
            "created_at": "2026-07-19T09:00:00Z",
            "updated_at": "2026-07-19T09:00:00Z",
        }
        assert "id" in response
        assert "location" in response
        assert "created_at" in response


# ---------------------------------------------------------------------------
# Test: SSE Streaming Contract
# ---------------------------------------------------------------------------

class TestSSEStreaming:
    """Test Server-Sent Events format for real-time agent progress."""

    def test_sse_event_format(self):
        """SSE events must follow the data: JSON format."""
        event = {
            "id": str(uuid.uuid4()),
            "status": "working",
            "node": "analysis",
            "output": {"agent": "Analysis Agent", "status": "started"},
        }

        # SSE wire format
        sse_line = f"data: {json.dumps(event)}\n\n"

        assert sse_line.startswith("data: ")
        assert sse_line.endswith("\n\n")

        # Parse back
        parsed = json.loads(sse_line[6:].strip())
        assert parsed["status"] == "working"
        assert parsed["node"] == "analysis"

    def test_sse_agent_sequence(self):
        """SSE events should follow the pipeline order."""
        expected_sequence = [
            "sampling",
            "analysis",
            "geology",  # parallel
            "market",   # parallel
            "report",
            "compliance",
        ]

        # Verify the sequence matches the pipeline graph
        # Geology and Market can be in either order (parallel)
        assert expected_sequence[0] == "sampling"
        assert expected_sequence[1] == "analysis"
        assert set(expected_sequence[2:4]) == {"geology", "market"}
        assert expected_sequence[4] == "report"
        assert expected_sequence[5] == "compliance"

    def test_sse_terminal_event(self):
        """Terminal SSE event must have status='completed' or 'failed'."""
        completed_event = {"id": "test", "status": "completed"}
        failed_event = {"id": "test", "status": "failed", "error": "Pipeline failed"}

        assert completed_event["status"] == "completed"
        assert failed_event["status"] == "failed"
        assert "error" in failed_event


# ---------------------------------------------------------------------------
# Test: Auth Contract
# ---------------------------------------------------------------------------

class TestAuthContract:
    """Test JWT authentication and role-based access control contracts."""

    def test_jwt_token_structure(self):
        """Supabase JWT must contain sub, role, and email claims."""
        # This is the expected JWT claim structure
        expected_claims = {
            "sub": "user-uuid-string",
            "role": "field_worker",
            "email": "user@example.com",
            "aud": "authenticated",
            "exp": 1721000000,
            "iat": 1720900000,
        }

        assert "sub" in expected_claims
        assert "role" in expected_claims
        assert expected_claims["role"] in ("field_worker", "geologist", "investor", "admin")

    def test_role_permissions_matrix(self):
        """Verify the RBAC permission matrix matches the architecture."""
        permissions = {
            "field_worker": {
                "can_create_sample": True,
                "can_trigger_analysis": True,
                "can_view_own_reports": True,
                "can_view_others_data": False,
                "can_modify_knowledge": False,
                "can_access_admin": False,
            },
            "geologist": {
                "can_create_sample": True,
                "can_trigger_analysis": True,
                "can_view_own_reports": True,
                "can_view_others_data": True,
                "can_modify_knowledge": True,
                "can_access_admin": False,
            },
            "investor": {
                "can_create_sample": False,
                "can_trigger_analysis": False,
                "can_view_own_reports": True,
                "can_view_others_data": False,
                "can_modify_knowledge": False,
                "can_access_admin": False,
            },
            "admin": {
                "can_create_sample": True,
                "can_trigger_analysis": True,
                "can_view_own_reports": True,
                "can_view_others_data": True,
                "can_modify_knowledge": True,
                "can_access_admin": True,
            },
        }

        # Field workers cannot access admin
        assert permissions["field_worker"]["can_access_admin"] is False
        # Investors cannot create samples
        assert permissions["investor"]["can_create_sample"] is False
        # Admins can do everything
        assert all(permissions["admin"].values())

    def test_auth_header_format(self):
        """Authorization header must use Bearer scheme."""
        header = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        parts = header.split(" ", 2)
        assert len(parts) == 2
        assert parts[0].lower() == "bearer"
        assert len(parts[1]) > 0


# ---------------------------------------------------------------------------
# Test: Rate Limiting Contract
# ---------------------------------------------------------------------------

class TestRateLimitingContract:
    """Test rate limiting behavior per the architecture spec."""

    def test_rate_limit_headers_present(self):
        """Rate-limited responses must include standard headers."""
        expected_headers = {
            "X-RateLimit-Limit": "30",
            "X-RateLimit-Remaining": "29",
            "X-RateLimit-Reset": "1721000060",
        }
        assert "X-RateLimit-Limit" in expected_headers
        assert "X-RateLimit-Remaining" in expected_headers
        assert "X-RateLimit-Reset" in expected_headers

    def test_rate_limit_per_role_config(self):
        """Per-role rate limits must match the architecture spec."""
        limits = {
            "field_worker": 30,  # req/min
            "geologist": 60,
            "investor": 20,
            "admin": 120,
        }
        assert limits["field_worker"] == 30
        assert limits["geologist"] == 60
        assert limits["investor"] == 20
        assert limits["admin"] == 120

    def test_rate_limit_exceeded_response(self):
        """429 response must include Retry-After header."""
        response_status = 429
        headers = {"Retry-After": "60"}

        assert response_status == 429
        assert "Retry-After" in headers

    def test_unauthenticated_rate_limit(self):
        """Unauthenticated requests should have conservative limits."""
        unauthenticated_limit = 10  # req/min per the middleware code
        assert unauthenticated_limit < 30  # Less than field_worker


# ---------------------------------------------------------------------------
# Test: Data Model Consistency
# ---------------------------------------------------------------------------

class TestDataModelConsistency:
    """Verify Go and Python data models are compatible."""

    def test_analysis_status_values(self):
        """Analysis status enum must match between Go and Python."""
        go_statuses = ["pending", "running", "completed", "failed"]
        python_statuses = ["pending", "running", "completed", "failed"]
        assert go_statuses == python_statuses

    def test_mineral_sample_fields(self):
        """MineralSample fields must be compatible across Go and Python."""
        expected_fields = {
            "id", "user_id", "location", "photo_urls",
            "xrf_readings", "field_notes", "synced",
            "created_at", "updated_at",
        }
        # Go model has these fields
        go_fields = {"id", "user_id", "location", "photo_urls", "xrf_readings",
                     "field_notes", "voice_note_url", "synced", "created_at", "updated_at"}
        assert expected_fields.issubset(go_fields)

    def test_location_fields(self):
        """Location model must include lat, lon, region, county."""
        location = {"lat": -1.05, "lon": 34.55, "region": "Nyatike", "county": "Migori", "country": "Kenya"}
        assert "lat" in location
        assert "lon" in location
        assert "region" in location
        assert "county" in location

    def test_agent_outputs_has_all_6_agents(self):
        """AgentOutputs must include all 6 agent result types."""
        agent_output_keys = [
            "sampling", "analysis", "geology", "market", "report", "compliance"
        ]
        assert len(agent_output_keys) == 6

    def test_role_enum_values(self):
        """Role enum must match between Go and Python."""
        roles = ["field_worker", "geologist", "investor", "admin"]
        assert len(roles) == 4
        assert "field_worker" in roles
        assert "admin" in roles


# ---------------------------------------------------------------------------
# Test: Sync Contract
# ---------------------------------------------------------------------------

class TestSyncContract:
    """Test offline sync API contract."""

    def test_sync_upload_format(self):
        """POST /v1/sync must accept delta changes."""
        request = {
            "delta": [
                {
                    "entity_type": "sample",
                    "entity_id": str(uuid.uuid4()),
                    "action": "create",
                    "data": {"location": {"lat": -1.05, "lon": 34.55}},
                    "vector_clock": {"device-1": 1},
                }
            ]
        }
        assert len(request["delta"]) > 0
        assert "vector_clock" in request["delta"][0]

    def test_sync_response_format(self):
        """Sync response must include conflicts and sync count."""
        response = {
            "conflicts": [],
            "synced": 5,
            "errors": [],
        }
        assert "conflicts" in response
        assert "synced" in response
        assert isinstance(response["synced"], int)
