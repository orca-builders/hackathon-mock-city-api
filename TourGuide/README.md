# Tour Guide Mock API

Simple tour guide booking API designed for LLM / AI-agent consumption, with a React dashboard for humans to monitor tours and bookings.

## Quick Start

### Backend (FastAPI)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8004
```

API available at **http://localhost:8004** — interactive docs at **http://localhost:8004/docs**

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at **http://localhost:5177**

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/schema` | LLM-friendly endpoint manifest |
| GET | `/api/tours` | List tours (filter by category, difficulty, max_price, location) |
| GET | `/api/tours/{id}` | Get tour details |
| GET | `/api/tours/available?tour_id=...&date=...&guests=...` | Check availability + remaining spots |
| GET | `/api/categories` | List tour categories |
| GET | `/api/pricing?tour_id=...&guests=...` | Price quote |
| POST | `/api/bookings` | Create booking |
| GET | `/api/bookings` | List bookings (filter by status, date) |
| GET | `/api/bookings/{id}` | Get booking details |
| DELETE | `/api/bookings/{id}` | Cancel booking |

## Tour Categories

cultural, adventure, food, nature, nightlife, historical

## Difficulty Levels

easy, moderate, challenging

## For LLM Agents

Hit `GET /api/schema` first to get a plain-English description of all endpoints, parameters, expected payloads, categories, and difficulty levels. All responses are clean JSON.

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy, SQLite
- **Frontend**: React, Vite
