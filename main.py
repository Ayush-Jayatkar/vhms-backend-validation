from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
import models, schemas, auth
from database import engine, get_db, Base

# ── Create all tables on startup ─────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Vehicle Health Monitoring System",
    description="Backend API for sensor data ingestion and validation",
    version="1.0.0"
)

# ── Seed data on startup ──────────────────────────────────────────────────────
@app.on_event("startup")
def seed_data():
    db = next(get_db())
    
    # Create default users if they don't exist
    if not db.query(models.User).filter_by(email="admin@kb.com").first():
        db.add(models.User(
            email="admin@kb.com",
            password=auth.hash_password("admin123"),
            role="ADMIN"
        ))
    if not db.query(models.User).filter_by(email="analyst@kb.com").first():
        db.add(models.User(
            email="analyst@kb.com",
            password=auth.hash_password("analyst123"),
            role="ANALYST"
        ))
    
    # Create default vehicles
    for vid, name in [("VH-001", "Train Alpha"), ("VH-002", "Train Beta")]:
        if not db.query(models.Vehicle).filter_by(id=vid).first():
            db.add(models.Vehicle(id=vid, name=name))
    
    # Default thresholds
    defaults = [
        ("brake_pressure", 2.0, 10.0, "bar"),
        ("temperature",    -10.0, 80.0, "celsius"),
        ("speed",          0.0, 200.0, "kmh"),
    ]
    for st, mn, mx, unit in defaults:
        if not db.query(models.ThresholdConfig).filter_by(sensor_type=st).first():
            db.add(models.ThresholdConfig(sensor_type=st, min_value=mn, max_value=mx, unit=unit))
    
    db.commit()
    db.close()

# ════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/auth/login", response_model=schemas.LoginResponse, tags=["Auth"])
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not auth.verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=401,
            detail={"error": "INVALID_CREDENTIALS", "message": "Email or password is incorrect"}
        )
    token = auth.create_token({"sub": user.email, "role": user.role})
    return {"access_token": token, "token_type": "Bearer", "expires_in": 3600, "role": user.role}

# ════════════════════════════════════════════════════════════════════════════
# VEHICLE ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/vehicles", response_model=schemas.VehicleResponse, tags=["Vehicles"])
def create_vehicle(
    payload: schemas.VehicleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin)
):
    if db.query(models.Vehicle).filter_by(id=payload.id).first():
        raise HTTPException(status_code=409, detail={"error": "CONFLICT", "message": "Vehicle already exists"})
    vehicle = models.Vehicle(id=payload.id, name=payload.name)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle

@app.get("/api/v1/vehicles", response_model=list[schemas.VehicleResponse], tags=["Vehicles"])
def list_vehicles(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return db.query(models.Vehicle).all()

# ════════════════════════════════════════════════════════════════════════════
# SENSOR READINGS ROUTES    
# ════════════════════════════════════════════════════════════════════════════

def check_thresholds(sensor_type: str, value: float, db: Session) -> Optional[models.Alert]:
    """Core business logic: compare value against configured thresholds"""
    config = db.query(models.ThresholdConfig).filter_by(sensor_type=sensor_type).first()
    if not config:
        return None
    
    if config.min_value is not None and value < config.min_value:
        severity = "CRITICAL" if (config.min_value - value) > 0.5 else "WARNING"
        msg = f"{sensor_type} value {value} is below minimum threshold {config.min_value}"
        return severity, msg
    
    if config.max_value is not None and value > config.max_value:
        severity = "WARNING"
        msg = f"{sensor_type} value {value} exceeds maximum threshold {config.max_value}"
        return severity, msg
    
    return None

@app.post("/api/v1/readings", response_model=schemas.ReadingResponse, status_code=201, tags=["Readings"])
def create_reading(
    payload: schemas.ReadingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Validate vehicle exists
    vehicle = db.query(models.Vehicle).filter_by(id=payload.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": f"Vehicle {payload.vehicle_id} not found"})
    
    # Check for duplicate (same vehicle, sensor, timestamp)
    existing = db.query(models.SensorReading).filter_by(
        vehicle_id=payload.vehicle_id,
        sensor_type=payload.sensor_type,
        timestamp=payload.timestamp
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail={"error": "DUPLICATE", "message": "Reading with this timestamp already exists"})
    
    # Validate brake_pressure must be > 0
    if payload.sensor_type == "brake_pressure" and payload.value < 0:
        raise HTTPException(status_code=422, detail={"error": "INVALID_VALUE", "message": "Brake pressure cannot be negative"})
    
    # Create reading
    reading = models.SensorReading(
        vehicle_id=payload.vehicle_id,
        sensor_type=payload.sensor_type.value,
        value=payload.value,
        unit=payload.unit,
        timestamp=payload.timestamp
    )
    db.add(reading)
    db.flush()  # get the ID without committing
    
    # Threshold check → create alert if needed
    alert_triggered = False
    result = check_thresholds(payload.sensor_type.value, payload.value, db)
    if result:
        severity, msg = result
        alert = models.Alert(reading_id=reading.id, severity=severity, message=msg)
        db.add(alert)
        alert_triggered = True
    
    db.commit()
    db.refresh(reading)
    
    return {
        "id": reading.id,
        "vehicle_id": reading.vehicle_id,
        "sensor_type": reading.sensor_type,
        "value": reading.value,
        "unit": reading.unit,
        "timestamp": reading.timestamp,
        "alert_triggered": alert_triggered,
        "created_at": reading.created_at
    }

@app.get("/api/v1/readings", response_model=schemas.PaginatedReadings, tags=["Readings"])
def get_readings(
    vehicle_id:  Optional[str] = Query(None),
    sensor_type: Optional[str] = Query(None),
    page:        int = Query(1, ge=1, description="Page number, starts at 1"),
    page_size:   int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    query = db.query(models.SensorReading)
    if vehicle_id:
        query = query.filter(models.SensorReading.vehicle_id == vehicle_id)
    if sensor_type:
        query = query.filter(models.SensorReading.sensor_type == sensor_type)
    
    total = query.count()
    readings = query.order_by(models.SensorReading.timestamp.desc()) \
                    .offset((page - 1) * page_size) \
                    .limit(page_size) \
                    .all()
    
    import math
    return {
        "data": [
            {**r.__dict__, "alert_triggered": r.alert is not None}
            for r in readings
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_records": total,
            "total_pages": max(1, math.ceil(total / page_size))
        }
    }

@app.get("/api/v1/readings/{reading_id}", tags=["Readings"])
def get_reading(
    reading_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    r = db.query(models.SensorReading).filter_by(id=reading_id).first()
    if not r:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Reading not found"})
    return {**r.__dict__, "alert_triggered": r.alert is not None}

# ════════════════════════════════════════════════════════════════════════════
# ALERTS ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/alerts", response_model=list[schemas.AlertResponse], tags=["Alerts"])
def get_alerts(
    vehicle_id: Optional[str] = Query(None),
    severity:   Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    query = db.query(models.Alert).join(models.SensorReading)
    if vehicle_id:
        query = query.filter(models.SensorReading.vehicle_id == vehicle_id)
    if severity:
        query = query.filter(models.Alert.severity == severity)
    return query.order_by(models.Alert.created_at.desc()).all()

# ════════════════════════════════════════════════════════════════════════════
# THRESHOLD CONFIG ROUTES (ADMIN ONLY)
# ════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/thresholds", tags=["Thresholds"])
def get_thresholds(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return db.query(models.ThresholdConfig).all()

@app.put("/api/v1/thresholds/{sensor_type}", tags=["Thresholds"])
def update_threshold(
    sensor_type: str,
    payload: schemas.ThresholdUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(auth.require_admin)   # ADMIN ONLY
):
    config = db.query(models.ThresholdConfig).filter_by(sensor_type=sensor_type).first()
    if not config:
        raise HTTPException(status_code=404, detail="Sensor type not found")
    if payload.min_value is not None:
        config.min_value = payload.min_value
    if payload.max_value is not None:
        config.max_value = payload.max_value
    if payload.unit is not None:
        config.unit = payload.unit
    db.commit()
    return {"message": "Threshold updated", "sensor_type": sensor_type,
            "min_value": config.min_value, "max_value": config.max_value}

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "VHMS", "version": "1.0.0"}