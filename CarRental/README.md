# Car Rental Mock API

Simple car rental API designed for LLM / AI-agent consumption, with a dashboard for humans to monitor the fleet and rentals.

## Quick Start

### Backend (FastAPI)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8003
```

API available at **http://localhost:8003** — interactive docs at **http://localhost:8003/docs**

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at **http://localhost:5176**

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/schema` | LLM-friendly endpoint manifest |
| GET | `/api/vehicles` | List all vehicles (filter by category, seats) |
| GET | `/api/vehicles/available?pickup_date=...&return_date=...` | Available vehicles for dates |
| GET | `/api/vehicles/{id}` | Get vehicle details |
| GET | `/api/categories` | List categories with rate ranges |
| GET | `/api/pricing?vehicle_id=...&pickup_date=...&return_date=...` | Price quote |
| POST | `/api/rentals` | Create rental |
| GET | `/api/rentals` | List rentals (filter by status) |
| GET | `/api/rentals/{id}` | Get rental details |
| DELETE | `/api/rentals/{id}` | Cancel rental |

## Vehicle Categories

| Category | Daily Rate |
|----------|-----------|
| Economy | $35-39 |
| Compact | $45-49 |
| Midsize | $59-65 |
| Fullsize | $75-79 |
| SUV | $89-99 |
| Premium | $129-139 |
| Luxury | $189-199 |

## For LLM Agents

Hit `GET /api/schema` first to get a plain-English description of all endpoints, parameters, and expected payloads. All responses are clean JSON.

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy, SQLite
- **Frontend**: React, Vite
