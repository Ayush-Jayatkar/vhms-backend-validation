# VHMS Requirements Checklist
# ================================
# This is your TEST ORACLE.
# Every test case must trace back to a line here.
# Check off (✓) as you validate each requirement.

## FUNCTIONAL REQUIREMENTS

### Auth
[ ] FR-A01 — POST /auth/login with valid credentials returns 200 + JWT
[ ] FR-A02 — JWT contains role (ADMIN/ANALYST) and expires in 1 hour
[ ] FR-A03 — Wrong credentials return 401 INVALID_CREDENTIALS
[ ] FR-A04 — All protected endpoints require valid JWT (return 401 if missing)
[ ] FR-A05 — Tampered JWT is rejected with 401

### Sensor Readings
[ ] FR-R01 — POST /readings with valid payload returns 201 + reading object
[ ] FR-R02 — Required fields: vehicle_id, sensor_type, value, timestamp
[ ] FR-R03 — Missing any required field → 422 with field-level error
[ ] FR-R04 — sensor_type must be one of: brake_pressure, temperature, speed
[ ] FR-R05 — vehicle_id must reference an existing vehicle → 404 if not found
[ ] FR-R06 — Duplicate reading (same vehicle+sensor+timestamp) → 409 DUPLICATE
[ ] FR-R07 — Brake pressure cannot be negative → 422
[ ] FR-R08 — GET /readings returns paginated list sorted by timestamp desc
[ ] FR-R09 — GET /readings supports filter by vehicle_id and sensor_type
[ ] FR-R10 — Pagination: page starts at 1, page_size max 100

### Alert Engine (Business Logic)
[ ] FR-AL01 — brake_pressure < 2.0 bar → CRITICAL alert created
[ ] FR-AL02 — brake_pressure = 2.0 exactly → NO alert (threshold is exclusive)
[ ] FR-AL03 — brake_pressure 1.9999 → alert triggered (just below threshold)
[ ] FR-AL04 — Response includes alert_triggered: true/false
[ ] FR-AL05 — Alert is queryable via GET /alerts
[ ] FR-AL06 — Alert has: id, reading_id, severity, message, created_at

### Thresholds (ADMIN only)
[ ] FR-T01 — GET /thresholds returns all threshold configs
[ ] FR-T02 — PUT /thresholds/{sensor_type} with ADMIN token → 200, threshold updated
[ ] FR-T03 — PUT /thresholds with ANALYST token → 403 FORBIDDEN (not 401)

### Vehicles
[ ] FR-V01 — POST /vehicles (ADMIN only) creates a vehicle → 201
[ ] FR-V02 — Duplicate vehicle_id → 409 CONFLICT
[ ] FR-V03 — GET /vehicles returns all vehicles (all authenticated roles)

## NON-FUNCTIONAL REQUIREMENTS

[ ] NFR-01 — POST /readings responds in < 300ms under normal conditions
[ ] NFR-02 — GET /readings responds in < 200ms for up to 1000 records
[ ] NFR-03 — API error responses never expose stack traces or raw DB errors
[ ] NFR-04 — Passwords are never returned in any API response
[ ] NFR-05 — System handles 100 concurrent requests without error rate > 1%

## HOW TO USE THIS FILE
# 1. Before starting: read every requirement here
# 2. For each test you write in test_suite.py, note which FR it covers
#    (see comments in test_suite.py — every test references an FR)
# 3. After running tests: mark ✓ for each passing requirement
# 4. If a test fails: it tells you exactly which requirement is broken
# 5. Any unmarked item = a gap in your test coverage

## TRACEABILITY MAP
# test_admin_login_success         → FR-A01, FR-A02
# test_wrong_password_returns_401  → FR-A03
# test_tampered_token_rejected     → FR-A05
# test_no_token_returns_401        → FR-A04
# test_valid_reading_returns_201   → FR-R01, FR-R02
# test_missing_vehicle_id...       → FR-R03
# test_invalid_sensor_type...      → FR-R04
# test_nonexistent_vehicle...      → FR-R05
# test_duplicate_reading...        → FR-R06
# test_negative_brake_pressure...  → FR-R07
# test_get_readings_success        → FR-R08
# test_filter_by_vehicle_id        → FR-R09
# test_brake_pressure_at_exactly_threshold_no_alert    → FR-AL02 ← CRITICAL BVA
# test_brake_pressure_just_below_threshold_triggers... → FR-AL03 ← CRITICAL BVA
# test_critically_low_pressure...                      → FR-AL01
# test_admin_can_update_threshold  → FR-T02
# test_analyst_cannot_update...    → FR-T03