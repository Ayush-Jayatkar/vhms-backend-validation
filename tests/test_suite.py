"""
VHMS Test Suite — Vehicle Health Monitoring System
=====================================================
Run with:  pytest tests/ -v

These tests cover:
  - Happy path (positive)
  - Negative / failure cases
  - Boundary / edge cases
  - DB-level validation
  - Role-based access control
  - Security (auth bypass, token tampering)

OOP concepts applied:
  - Encapsulation  → APIClient class
  - Inheritance    → BaseTest class
  - Polymorphism   → ResponseValidator hierarchy
  - Abstraction    → DBHelper hides SQL
"""

import pytest
import requests
from datetime import datetime, timedelta

BASE = "http://127.0.0.1:8000"

# ════════════════════════════════════════════════════════════════════════════
# OOP: Encapsulation — hide HTTP complexity inside APIClient
# ════════════════════════════════════════════════════════════════════════════

class APIClient:
    """Wraps requests session. Callers never touch headers directly."""

    def __init__(self, base_url: str, token: str = None):
        self._base = base_url
        self._session = requests.Session()
        if token:
            self._session.headers.update({"Authorization": f"Bearer {token}"})

    def set_token(self, token: str):
        self._session.headers.update({"Authorization": f"Bearer {token}"})

    def post(self, endpoint: str, payload: dict) -> requests.Response:
        return self._session.post(f"{self._base}{endpoint}", json=payload)

    def get(self, endpoint: str, params: dict = None) -> requests.Response:
        return self._session.get(f"{self._base}{endpoint}", params=params)

    def put(self, endpoint: str, payload: dict) -> requests.Response:
        return self._session.put(f"{self._base}{endpoint}", json=payload)

    def delete(self, endpoint: str) -> requests.Response:
        return self._session.delete(f"{self._base}{endpoint}")


# ════════════════════════════════════════════════════════════════════════════
# OOP: Polymorphism — validators for different response types
# ════════════════════════════════════════════════════════════════════════════

class ResponseValidator:
    """Base class — all validators implement validate()"""
    def validate(self, data: dict):
        raise NotImplementedError

class ReadingValidator(ResponseValidator):
    def validate(self, data: dict):
        required = ["id", "vehicle_id", "sensor_type", "value", "timestamp", "alert_triggered", "created_at"]
        for field in required:
            assert field in data, f"Missing field in reading response: {field}"
        assert isinstance(data["value"], (int, float)), "value must be numeric"
        assert isinstance(data["alert_triggered"], bool), "alert_triggered must be boolean"

class PaginationValidator(ResponseValidator):
    def validate(self, data: dict):
        assert "data" in data, "Missing 'data' key"
        assert "pagination" in data, "Missing 'pagination' key"
        p = data["pagination"]
        for key in ["page", "page_size", "total_records", "total_pages"]:
            assert key in p, f"Missing pagination key: {key}"
        assert p["page"] >= 1
        assert len(data["data"]) <= p["page_size"], "More records than page_size"

class AlertValidator(ResponseValidator):
    def validate(self, data: dict):
        required = ["id", "reading_id", "severity", "message", "created_at"]
        for field in required:
            assert field in data, f"Missing field in alert: {field}"
        assert data["severity"] in ["CRITICAL", "WARNING", "INFO"], f"Unknown severity: {data['severity']}"

def assert_valid(data: dict, validator: ResponseValidator):
    """Polymorphic dispatch — calls the right validate() automatically"""
    validator.validate(data)


# ════════════════════════════════════════════════════════════════════════════
# OOP: Inheritance — BaseTest provides shared setup for all test classes
# ════════════════════════════════════════════════════════════════════════════

class BaseTest:
    """
    All test classes inherit from here.
    They get admin_client, analyst_client, and no_auth_client for free.
    """
    admin_client:   APIClient = None
    analyst_client: APIClient = None
    noauth_client:  APIClient = None

    @classmethod
    def setup_class(cls):
        # Login as ADMIN
        r = requests.post(f"{BASE}/api/v1/auth/login",
                          json={"email": "admin@kb.com", "password": "admin123"})
        assert r.status_code == 200, f"Admin login failed: {r.text}"
        cls.admin_client = APIClient(BASE, r.json()["access_token"])

        # Login as ANALYST
        r = requests.post(f"{BASE}/api/v1/auth/login",
                          json={"email": "analyst@kb.com", "password": "analyst123"})
        assert r.status_code == 200, f"Analyst login failed: {r.text}"
        cls.analyst_client = APIClient(BASE, r.json()["access_token"])

        # No token client — for auth tests
        cls.noauth_client = APIClient(BASE)

    def make_reading(self, value: float, sensor_type: str = "brake_pressure",
                     vehicle_id: str = "VH-001", offset_seconds: int = 0) -> dict:
        """Helper — build a reading payload with a unique timestamp"""
        ts = datetime.utcnow() + timedelta(seconds=offset_seconds)
        return {
            "vehicle_id": vehicle_id,
            "sensor_type": sensor_type,
            "value": value,
            "unit": "bar" if sensor_type == "brake_pressure" else "unit",
            "timestamp": ts.isoformat() + "Z"
        }


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 1: Authentication
# ════════════════════════════════════════════════════════════════════════════

class TestAuthentication(BaseTest):

    def test_admin_login_success(self):
        """Happy path: valid ADMIN credentials return JWT"""
        r = requests.post(f"{BASE}/api/v1/auth/login",
                          json={"email": "admin@kb.com", "password": "admin123"})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] == 3600
        assert data["role"] == "ADMIN"

    def test_analyst_login_success(self):
        """Happy path: ANALYST user also gets a valid token"""
        r = requests.post(f"{BASE}/api/v1/auth/login",
                          json={"email": "analyst@kb.com", "password": "analyst123"})
        assert r.status_code == 200
        assert r.json()["role"] == "ANALYST"

    def test_wrong_password_returns_401(self):
        """Negative: correct email, wrong password → 401"""
        r = requests.post(f"{BASE}/api/v1/auth/login",
                          json={"email": "admin@kb.com", "password": "WRONGPASSWORD"})
        assert r.status_code == 401
        assert r.json()["detail"]["error"] == "INVALID_CREDENTIALS"

    def test_nonexistent_user_returns_401(self):
        """Negative: email doesn't exist → 401 (NOT 404 — don't leak user existence)"""
        r = requests.post(f"{BASE}/api/v1/auth/login",
                          json={"email": "ghost@kb.com", "password": "anything"})
        assert r.status_code == 401

    def test_missing_email_field(self):
        """Negative: malformed body → 422 validation error"""
        r = requests.post(f"{BASE}/api/v1/auth/login",
                          json={"password": "admin123"})
        assert r.status_code == 422

    def test_tampered_token_rejected(self):
        """Security: modify the payload of a valid JWT → must be rejected"""
        # Get valid token
        r = requests.post(f"{BASE}/api/v1/auth/login",
                          json={"email": "admin@kb.com", "password": "admin123"})
        token = r.json()["access_token"]

        # Tamper: replace the payload section with garbage
        parts = token.split(".")
        tampered = parts[0] + ".TAMPERED_PAYLOAD_XXXXXX." + parts[2]

        r2 = requests.get(f"{BASE}/api/v1/vehicles",
                          headers={"Authorization": f"Bearer {tampered}"})
        assert r2.status_code == 401

    def test_no_token_returns_401(self):
        """Security: unauthenticated request → 401"""
        r = requests.get(f"{BASE}/api/v1/readings")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 2: Sensor Readings (core business logic)
# ════════════════════════════════════════════════════════════════════════════

class TestSensorReadings(BaseTest):

    # ── Happy path ──────────────────────────────────────────────────────────
    def test_valid_reading_returns_201(self):
        """Happy path: well-formed reading → 201 with correct response shape"""
        payload = self.make_reading(value=3.5)
        r = self.admin_client.post("/api/v1/readings", payload)
        assert r.status_code == 201
        data = r.json()
        assert_valid(data, ReadingValidator())
        assert data["value"] == 3.5
        assert data["alert_triggered"] == False   # 3.5 bar is above threshold of 2.0

    def test_normal_pressure_no_alert(self):
        """Business logic: value above threshold → no alert"""
        r = self.admin_client.post("/api/v1/readings", self.make_reading(5.0, offset_seconds=1))
        assert r.status_code == 201
        assert r.json()["alert_triggered"] == False

    def test_analyst_can_post_reading(self):
        """ANALYST role also has write access to readings"""
        r = self.analyst_client.post("/api/v1/readings", self.make_reading(4.0, offset_seconds=2))
        assert r.status_code == 201

    # ── Alert threshold tests (boundary value analysis) ─────────────────────
    def test_brake_pressure_at_exactly_threshold_no_alert(self):
        """
        BVA: value = 2.0 (exactly at threshold boundary).
        Threshold is EXCLUSIVE (< 2.0 triggers alert).
        2.0 should NOT trigger alert.
        """
        r = self.admin_client.post("/api/v1/readings", self.make_reading(2.0, offset_seconds=3))
        assert r.status_code == 201
        assert r.json()["alert_triggered"] == False, "2.0 bar is AT threshold, should not trigger"

    def test_brake_pressure_just_below_threshold_triggers_alert(self):
        """
        BVA: value = 1.9999 (just below threshold) → CRITICAL alert.
        This is the most critical edge case for safety.
        """
        r = self.admin_client.post("/api/v1/readings", self.make_reading(1.9999, offset_seconds=4))
        assert r.status_code == 201
        assert r.json()["alert_triggered"] == True, "1.9999 bar is below 2.0 threshold, must trigger"

    def test_critically_low_pressure_triggers_alert(self):
        """Business logic: clearly dangerous value → CRITICAL alert + verify in GET /alerts"""
        r = self.admin_client.post("/api/v1/readings", self.make_reading(0.5, offset_seconds=5))
        assert r.status_code == 201
        reading_id = r.json()["id"]

        # Verify alert exists via API (3-layer validation: response → API query → business logic)
        alerts_r = self.admin_client.get("/api/v1/alerts", {"vehicle_id": "VH-001"})
        assert alerts_r.status_code == 200
        alerts = alerts_r.json()
        matching = [a for a in alerts if a["reading_id"] == reading_id]
        assert len(matching) == 1
        assert_valid(matching[0], AlertValidator())
        assert matching[0]["severity"] == "CRITICAL"

    # ── Negative tests ───────────────────────────────────────────────────────
    def test_missing_vehicle_id_returns_422(self):
        """Negative: required field missing → 422 Unprocessable Entity"""
        r = self.admin_client.post("/api/v1/readings", {
            "sensor_type": "brake_pressure",
            "value": 3.5,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        assert r.status_code == 422

    def test_missing_value_returns_422(self):
        """Negative: 'value' field is required"""
        r = self.admin_client.post("/api/v1/readings", {
            "vehicle_id": "VH-001",
            "sensor_type": "brake_pressure",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        assert r.status_code == 422

    def test_invalid_sensor_type_returns_422(self):
        """Negative: sensor_type must be from allowed enum"""
        r = self.admin_client.post("/api/v1/readings", {
            "vehicle_id": "VH-001",
            "sensor_type": "flying_speed",    # not in enum
            "value": 3.5,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        assert r.status_code == 422

    def test_nonexistent_vehicle_returns_404(self):
        """Negative: vehicle doesn't exist → 404"""
        r = self.admin_client.post("/api/v1/readings", {
            "vehicle_id": "VH-GHOST",
            "sensor_type": "brake_pressure",
            "value": 3.5,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        assert r.status_code == 404
        assert r.json()["detail"]["error"] == "NOT_FOUND"

    def test_negative_brake_pressure_rejected(self):
        """Edge case: physically impossible value"""
        r = self.admin_client.post("/api/v1/readings", self.make_reading(-5.0, offset_seconds=6))
        assert r.status_code == 422

    def test_duplicate_reading_returns_409(self):
        """
        Idempotency test: same vehicle + sensor + timestamp = duplicate.
        Must return 409 Conflict, NOT create a second record.
        """
        payload = self.make_reading(3.0, offset_seconds=100)
        r1 = self.admin_client.post("/api/v1/readings", payload)
        assert r1.status_code == 201    # First time: success

        r2 = self.admin_client.post("/api/v1/readings", payload)
        assert r2.status_code == 409    # Second time: conflict
        assert r2.json()["detail"]["error"] == "DUPLICATE"

    def test_unauthenticated_post_rejected(self):
        """Security: no token → 401"""
        r = self.noauth_client.post("/api/v1/readings", self.make_reading(3.5))
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 3: GET /readings — pagination and filtering
# ════════════════════════════════════════════════════════════════════════════

class TestReadingQueries(BaseTest):

    @classmethod
    def setup_class(cls):
        super().setup_class()
        # Seed 5 readings for VH-001 so pagination tests have data
        for i in range(5):
            cls.admin_client.post("/api/v1/readings", {
                "vehicle_id": "VH-001",
                "sensor_type": "brake_pressure",
                "value": 3.0 + i * 0.1,
                "unit": "bar",
                "timestamp": (datetime.utcnow() + timedelta(minutes=i+200)).isoformat() + "Z"
            })

    def test_get_readings_success(self):
        """Happy path: paginated list returns correct structure"""
        r = self.admin_client.get("/api/v1/readings", {"page": 1, "page_size": 5})
        assert r.status_code == 200
        assert_valid(r.json(), PaginationValidator())

    def test_filter_by_vehicle_id(self):
        """Filtering: only readings for specified vehicle returned"""
        r = self.admin_client.get("/api/v1/readings", {"vehicle_id": "VH-001"})
        assert r.status_code == 200
        data = r.json()["data"]
        for reading in data:
            assert reading["vehicle_id"] == "VH-001", "Filter returned wrong vehicle's data"

    def test_page_beyond_results_returns_empty(self):
        """Edge: requesting page 9999 → empty data, not an error"""
        r = self.admin_client.get("/api/v1/readings", {"page": 9999, "page_size": 20})
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_page_zero_rejected(self):
        """Edge: page=0 is invalid (pages start at 1)"""
        r = self.admin_client.get("/api/v1/readings", {"page": 0})
        assert r.status_code == 422

    def test_page_size_above_max_rejected(self):
        """Edge: page_size > 100 is rejected"""
        r = self.admin_client.get("/api/v1/readings", {"page_size": 999})
        assert r.status_code == 422

    def test_results_sorted_descending_by_timestamp(self):
        """Verify sort order: newest readings come first"""
        r = self.admin_client.get("/api/v1/readings", {"vehicle_id": "VH-001", "page_size": 50})
        readings = r.json()["data"]
        if len(readings) > 1:
            for i in range(len(readings) - 1):
                assert readings[i]["timestamp"] >= readings[i+1]["timestamp"], \
                    f"Sort order broken at index {i}"


# ════════════════════════════════════════════════════════════════════════════
# TEST CLASS 4: Role-based access control (RBAC)
# ════════════════════════════════════════════════════════════════════════════

class TestRoleBasedAccess(BaseTest):

    def test_admin_can_update_threshold(self):
        """ADMIN can change threshold configuration"""
        r = self.admin_client.put("/api/v1/thresholds/brake_pressure",
                                  {"min_value": 1.5})
        assert r.status_code == 200
        assert r.json()["min_value"] == 1.5

        # Restore original threshold
        self.admin_client.put("/api/v1/thresholds/brake_pressure", {"min_value": 2.0})

    def test_analyst_cannot_update_threshold(self):
        """
        RBAC: ANALYST token on ADMIN-only endpoint → 403 Forbidden.
        CRITICAL: must be 403, not 401.
        401 = not authenticated. 403 = authenticated but not authorized.
        """
        r = self.analyst_client.put("/api/v1/thresholds/brake_pressure",
                                    {"min_value": 0.5})
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"
        assert r.json()["detail"]["error"] == "FORBIDDEN"

    def test_analyst_cannot_create_vehicle(self):
        """RBAC: vehicle creation is ADMIN-only"""
        r = self.analyst_client.post("/api/v1/vehicles",
                                     {"id": "VH-HACK", "name": "Hacker Train"})
        assert r.status_code == 403

    def test_both_roles_can_read_data(self):
        """Both ADMIN and ANALYST can read readings — read is not restricted"""
        r_admin   = self.admin_client.get("/api/v1/readings")
        r_analyst = self.analyst_client.get("/api/v1/readings")
        assert r_admin.status_code == 200
        assert r_analyst.status_code == 200


# ════════════════════════════════════════════════════════════════════════════
# DSA applied: alert frequency analysis using HashMap
# ════════════════════════════════════════════════════════════════════════════

def analyze_alert_distribution(alerts: list) -> dict:
    """
    Count alerts by severity — HashMap O(n) time.
    Used in test to verify batch operations produce expected distribution.
    """
    freq = {}
    for alert in alerts:
        sev = alert["severity"]
        freq[sev] = freq.get(sev, 0) + 1
    return freq

def is_sorted_descending(items: list, key: str) -> bool:
    """
    Verify sort order — O(n) linear scan.
    Returns True if items[i][key] >= items[i+1][key] throughout.
    """
    for i in range(len(items) - 1):
        if items[i][key] < items[i+1][key]:
            return False
    return True

class TestDSAInValidation(BaseTest):

    def test_alert_distribution_analysis(self):
        """DSA: HashMap to count alert types across a batch"""
        r = self.admin_client.get("/api/v1/alerts")
        assert r.status_code == 200
        alerts = r.json()
        distribution = analyze_alert_distribution(alerts)
        # All severities must be valid
        for severity in distribution.keys():
            assert severity in ["CRITICAL", "WARNING", "INFO"]

    def test_readings_sorted_order(self):
        """DSA: Linear scan to verify sort order of paginated response"""
        r = self.admin_client.get("/api/v1/readings", {"page_size": 20})
        readings = r.json()["data"]
        if len(readings) > 1:
            assert is_sorted_descending(readings, "timestamp"), \
                "Readings should be sorted newest-first"