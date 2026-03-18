# Museum Ticket Mock API

Simple museum ticket booking API designed for LLM / AI-agent consumption, with a dashboard for humans to monitor availability and tickets.

## Quick Start

### Backend (FastAPI)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8005
```

API available at **http://localhost:8005** — interactive docs at **http://localhost:8005/docs**

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at **http://localhost:5178**

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/schema` | LLM-friendly endpoint manifest |
| GET | `/api/time-slots` | List time slots with capacity |
| GET | `/api/availability?date=...` | Availability for all slots on a date |
| GET | `/api/availability?date=...&time_slot_id=...&visitors=...` | Check specific slot |
| GET | `/api/ticket-types` | List ticket types and prices |
| GET | `/api/pricing?ticket_type=...&visitors=...` | Price quote |
| POST | `/api/tickets` | Book tickets |
| GET | `/api/tickets` | List tickets (filter by date, status) |
| GET | `/api/tickets/{id}` | Get ticket details |
| DELETE | `/api/tickets/{id}` | Cancel ticket |

## Time Slots

| Slot | Capacity |
|------|----------|
| 09:00-11:00 | 50 visitors |
| 11:00-13:00 | 50 visitors |
| 13:00-15:00 | 50 visitors |
| 15:00-17:00 | 50 visitors |

## Ticket Prices

| Type | Price |
|------|-------|
| Adult | $25 |
| Child | $12 |
| Senior | $18 |
| Student | $15 |

## For LLM Agents

Hit `GET /api/schema` first to get a plain-English description of all endpoints, parameters, expected payloads, ticket types, and prices. All responses are clean JSON.

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy, SQLite
- **Frontend**: React, Vite
