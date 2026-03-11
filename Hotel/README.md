# Hotel Reservation Mock API

Simple hotel reservation API designed for LLM / AI-agent consumption, with a dashboard for humans to monitor bookings.

## Quick Start

### Backend (FastAPI)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API available at **http://localhost:8000** — interactive docs at **http://localhost:8000/docs**

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at **http://localhost:5173**

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/schema` | LLM-friendly endpoint manifest |
| GET | `/api/rooms` | List all rooms |
| GET | `/api/rooms/available?check_in=...&check_out=...&guests=...` | Available rooms for dates |
| GET | `/api/pricing?room_id=...&check_in=...&check_out=...` | Price quote with breakdown |
| POST | `/api/reservations` | Create reservation |
| GET | `/api/reservations` | List reservations |
| GET | `/api/reservations/{id}` | Get reservation details |
| DELETE | `/api/reservations/{id}` | Cancel reservation |

## For LLM Agents

Hit `GET /api/schema` first to get a plain-English description of all endpoints, parameters, and expected payloads. All responses are clean JSON.

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy, SQLite
- **Frontend**: React, Vite
