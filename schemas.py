from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List
from enum import Enum

# ── Enums ──────────────────────────────────────────────────────────────────
class SensorType(str, Enum):
    brake_pressure = "brake_pressure"
    temperature    = "temperature"
    speed          = "speed"

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING  = "WARNING"
    INFO     = "INFO"

class Role(str, Enum):
    ADMIN   = "ADMIN"
    ANALYST = "ANALYST"

# ── Auth ────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email:    str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type:   str = "Bearer"
    expires_in:   int = 3600
    role:         str

# ── Sensor Reading ──────────────────────────────────────────────────────────
class ReadingCreate(BaseModel):
    vehicle_id:  str         = Field(..., example="VH-001")
    sensor_type: SensorType
    value:       float       = Field(..., gt=-1000, description="Sensor reading value")
    unit:        Optional[str] = None
    timestamp:   datetime

    @field_validator("value")
    @classmethod
    def value_must_be_physical(cls, v, info):
        # Brake pressure cannot be negative
        return v

class ReadingResponse(BaseModel):
    id:              str
    vehicle_id:      str
    sensor_type:     str
    value:           float
    unit:            Optional[str]
    timestamp:       datetime
    alert_triggered: bool
    created_at:      datetime

    class Config:
        from_attributes = True

class PaginatedReadings(BaseModel):
    data: List[ReadingResponse]
    pagination: dict

# ── Alert ───────────────────────────────────────────────────────────────────
class AlertResponse(BaseModel):
    id:         str
    reading_id: str
    severity:   str
    message:    str
    created_at: datetime

    class Config:
        from_attributes = True

# ── Threshold ───────────────────────────────────────────────────────────────
class ThresholdUpdate(BaseModel):
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    unit:      Optional[str]   = None

# ── Vehicle ─────────────────────────────────────────────────────────────────
class VehicleCreate(BaseModel):
    id:   str = Field(..., example="VH-001")
    name: str

class VehicleResponse(BaseModel):
    id:            str
    name:          str
    registered_at: datetime

    class Config:
        from_attributes = True