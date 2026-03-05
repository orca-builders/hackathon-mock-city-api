# Hackathon Mock APIs

A collection of mock booking/reservation APIs designed for LLM and AI-agent consumption, each with a React dashboard for human verification.

## Services

| Service | Description | Source |
|---------|-------------|--------|
| **Hotel** | Room reservations, date-range pricing, capacity | `Hotel/` |
| **Restaurant** | Table reservations, time slots, party size | `Resturant/` |
| **Flight** | Flight bookings, seat classes, routes (SkyMock Air) | `Flight/` |
| **Car Rental** | Vehicle rentals by category (economy to luxury) | `CarRental/` |
| **Tour Guide** | Tour bookings by category, difficulty, group size | `TourGuide/` |
| **Museum** | Timed-entry tickets, visitor capacity per slot | `Museum/` |

## Quick Start (Docker)

```bash
docker compose up --build
```

Everything starts on **one port**: [http://localhost:8080](http://localhost:8080)

A landing page at `/` lists all service instances with links.

## Service Instances

Each service can have multiple independent instances (own container, own database):

| Path | API | Dashboard |
|------|-----|-----------|
| `/hotel-1/` | `/hotel-1/api/...` | `/hotel-1/` |
| `/hotel-2/` | `/hotel-2/api/...` | `/hotel-2/` |
| `/restaurant-1/` | `/restaurant-1/api/...` | `/restaurant-1/` |
| `/restaurant-2/` | `/restaurant-2/api/...` | `/restaurant-2/` |
| `/restaurant-3/` | `/restaurant-3/api/...` | `/restaurant-3/` |
| `/flight-1/` | `/flight-1/api/...` | `/flight-1/` |
| `/car-rental-1/` | `/car-rental-1/api/...` | `/car-rental-1/` |
| `/tour-guide-1/` | `/tour-guide-1/api/...` | `/tour-guide-1/` |
| `/museum-1/` | `/museum-1/api/...` | `/museum-1/` |

## API Key Authentication

Every instance is protected by its own API key, set via the `API_KEY` environment variable in `docker-compose.yml`.

**Default keys** (change these for production):

| Instance | API Key |
|----------|---------|
| hotel-1 | `hotel-1-key-abc123` |
| hotel-2 | `hotel-2-key-def456` |
| restaurant-1 | `restaurant-1-key-ghi789` |
| restaurant-2 | `restaurant-2-key-jkl012` |
| restaurant-3 | `restaurant-3-key-mno345` |
| flight-1 | `flight-1-key-pqr678` |
| car-rental-1 | `car-rental-1-key-stu901` |
| tour-guide-1 | `tour-guide-1-key-vwx234` |
| museum-1 | `museum-1-key-yza567` |

**Two ways to pass the key:**

```bash
# Header (recommended for LLM agents)
curl -H "X-API-Key: hotel-1-key-abc123" http://localhost:8080/hotel-1/api/rooms

# Query parameter
curl http://localhost:8080/hotel-1/api/rooms?api_key=hotel-1-key-abc123
```

**Dashboard access** — append the key to the URL:

```
http://localhost:8080/hotel-1/?api_key=hotel-1-key-abc123
```

Without a valid key, all `/api/*` endpoints return `401`. The dashboard pages themselves load without a key but need it to fetch data.

To disable auth for an instance, remove its `API_KEY` line from `docker-compose.yml`.

## For LLM / AI Agents

Each instance exposes a self-describing schema endpoint:

```
GET /<service>/api/schema
```

This returns a plain-English JSON manifest with all available endpoints, parameters, expected payloads, and domain-specific values (ticket types, seat classes, vehicle categories, etc.). Hit this first to understand what the API offers.

All API calls require the `X-API-Key` header:

```bash
curl -H "X-API-Key: hotel-1-key-abc123" http://localhost:8080/hotel-1/api/schema
curl -H "X-API-Key: restaurant-2-key-jkl012" http://localhost:8080/restaurant-2/api/schema
```

## Adding More Instances

To add a 3rd hotel or 4th restaurant:

1. **`docker-compose.yml`** — copy a service block and bump the number:

```yaml
  hotel-3:
    build:
      context: ./Hotel
      args:
        BASE_PATH: /hotel-3/
    restart: unless-stopped
```

2. **`gateway/nginx.conf`** — add a matching location:

```nginx
    location /hotel-3/ {
        proxy_pass http://hotel-3:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
```

3. Add the new service to `gateway`'s `depends_on` list.

4. Rebuild: `docker compose up --build`

## Running a Single Service (without Docker)

Each service can also run standalone for development:

```bash
# Backend
cd Hotel/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd Hotel/frontend
npm install
npm run dev
```

See each service's own `README.md` for specific ports and API details.

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy, SQLite
- **Frontend**: React, Vite
- **Gateway**: nginx (path-based reverse proxy)
- **Containers**: Docker, Docker Compose

## Architecture

```
                         :8080
                      ┌─────────┐
                      │  nginx  │
                      │ gateway │
                      └────┬────┘
           ┌───────┬───────┼───────┬──────┬──────┐
           │       │       │       │      │      │
        hotel-N  rest-N  flight  car    tour   museum
         :8000    :8000   :8000  :8000  :8000  :8000
        ┌──┴──┐  ┌─┴─┐
        │     │  │   │
       h-1   h-2 r-1 r-2 r-3  ...
```

Each container runs FastAPI serving both the API (`/api/*`) and the built React dashboard as static files.
