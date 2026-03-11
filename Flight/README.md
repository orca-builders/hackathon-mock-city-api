# SkyMock Air — Flight Reservation Mock API

Simple single-airline flight reservation API designed for LLM / AI-agent consumption, with a dashboard for humans to monitor bookings.

## Quick Start

### Backend (FastAPI)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

API available at **http://localhost:8002** — interactive docs at **http://localhost:8002/docs**

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at **http://localhost:5175**

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/schema` | LLM-friendly endpoint manifest |
| GET | `/api/flights` | List all flights (filter by origin, destination, date) |
| GET | `/api/flights/search?origin=...&destination=...` | Search available flights |
| GET | `/api/flights/{id}` | Get flight details |
| GET | `/api/pricing?flight_id=...&seat_class=...&passengers=...` | Price quote by class |
| GET | `/api/destinations` | List all served cities |
| POST | `/api/bookings` | Create booking |
| GET | `/api/bookings` | List bookings (filter by status) |
| GET | `/api/bookings/{id}` | Get booking details |
| DELETE | `/api/bookings/{id}` | Cancel booking (restores seats) |

## Seat Classes & Pricing

| Class | Multiplier | Example ($199 base) |
|-------|-----------|---------------------|
| Economy | 1.0x | $199.00 |
| Business | 2.5x | $497.50 |
| First | 5.0x | $995.00 |

## For LLM Agents

Hit `GET /api/schema` first to get a plain-English description of all endpoints, parameters, expected payloads, and seat class pricing multipliers. All responses are clean JSON.

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy, SQLite
- **Frontend**: React, Vite
