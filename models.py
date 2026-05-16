from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base
import uuid
from datetime import datetime

def gen_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id       = Column(String, primary_key=True, default=gen_uuid)
    email    = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)       # stored as bcrypt hash
    role     = Column(String, default="ANALYST")    # "ADMIN" or "ANALYST"


class Vehicle(Base):
    __tablename__ = "vehicles"

    id            = Column(String, primary_key=True)   # e.g. "VH-001"
    name          = Column(String, nullable=False)
    registered_at = Column(DateTime, default=datetime.utcnow)

    readings = relationship("SensorReading", back_populates="vehicle")


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id          = Column(String, primary_key=True, default=gen_uuid)
    vehicle_id  = Column(String, ForeignKey("vehicles.id"), nullable=False)
    sensor_type = Column(String, nullable=False)  # "brake_pressure", "temperature", "speed"
    value       = Column(Float, nullable=False)
    unit        = Column(String)
    timestamp   = Column(DateTime, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    vehicle = relationship("Vehicle", back_populates="readings")
    alert   = relationship("Alert", back_populates="reading", uselist=False)


class Alert(Base):
    __tablename__ = "alerts"

    id         = Column(String, primary_key=True, default=gen_uuid)
    reading_id = Column(String, ForeignKey("sensor_readings.id"))
    severity   = Column(String, nullable=False)   # "CRITICAL", "WARNING", "INFO"
    message    = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    reading = relationship("SensorReading", back_populates="alert")


class ThresholdConfig(Base):
    __tablename__ = "threshold_configs"

    sensor_type = Column(String, primary_key=True)
    min_value   = Column(Float)
    max_value   = Column(Float)
    unit        = Column(String)