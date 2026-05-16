# vhms-backend-validation

# Vehicle Health Monitoring System (VHMS)

A backend REST API simulating a safety-critical sensor monitoring system — built to practice backend system design and functional validation testing.

## Tech Stack
- Python, FastAPI, SQLAlchemy, SQLite
- JWT Authentication (python-jose + bcrypt)
- pytest + requests (test automation)

## Features
- Sensor data ingestion (brake pressure, temperature, speed)
- Automatic alert generation on threshold breach
- Role-based access control (ADMIN / ANALYST)
- 40+ automated test cases covering happy path, negative, boundary value, security, and DB-level validation

## Quickstart
```bash
python -m venv venv
venv\Scripts\activate
pip install fastapi uvicorn sqlalchemy python-jose passlib bcrypt httpx pytest
uvicorn main:app --reload
```
API docs: `http://127.0.0.1:8000/docs`

## Running Tests
```bash
pytest tests/ -v
```

## Default Credentials
| Role | Email | Password |
|---|---|---|
| ADMIN | admin@kb.com | admin123 |
| ANALYST | analyst@kb.com | analyst123 |
