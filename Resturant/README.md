# Restaurant Reservation Mock API

Simple restaurant reservation API designed for LLM / AI-agent consumption, with a dashboard for humans to monitor bookings.

## Quick Start

### Backend (FastAPI)

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8001
```

If first time, create the venv first:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

API available at **http://localhost:8001** — interactive docs at **http://localhost:8001/docs**

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at **http://localhost:5174**

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/schema` | LLM-friendly endpoint manifest |
| GET | `/api/tables` | List all tables |
| GET | `/api/tables/available?date=...&time_slot=...&party_size=...` | Available tables for a date/time |
| GET | `/api/time-slots` | List valid time slots |
| POST | `/api/reservations` | Create reservation |
| GET | `/api/reservations` | List reservations (filter by date, status) |
| GET | `/api/reservations/{id}` | Get reservation details |
| DELETE | `/api/reservations/{id}` | Cancel reservation |

## Time Slots

Six fixed 1.5-hour windows: `11:00`, `12:30`, `14:00`, `18:00`, `19:30`, `21:00`

## For LLM Agents

Hit `GET /api/schema` first to get a plain-English description of all endpoints, parameters, and expected payloads. All responses are clean JSON.

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy, SQLite
- **Frontend**: React, Vite
