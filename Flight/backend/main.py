from __future__ import annotations

import datetime as dt
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date, DateTime,
    ForeignKey, func,
)
from sqlalchemy.orm import (
    DeclarativeBase, Session, sessionmaker, relationship,
)

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

DATABASE_URL = "sqlite:///./flights.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

SEAT_CLASS_MULTIPLIERS = {
    "economy": 1.0,
    "business": 2.5,
    "first": 5.0,
}

AIRLINE_NAME = "SkyMock Air"


class Base(DeclarativeBase):
    pass


class FlightModel(Base):
    __tablename__ = "flights"

    id = Column(Integer, primary_key=True, index=True)
    flight_number = Column(String, unique=True, nullable=False)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    departure_date = Column(Date, nullable=False)
    departure_time = Column(String, nullable=False)
    arrival_time = Column(String, nullable=False)
    total_seats = Column(Integer, nullable=False)
    available_seats = Column(Integer, nullable=False)
    base_price = Column(Float, nullable=False)
    status = Column(String, default="scheduled")  # scheduled / cancelled / completed

    bookings = relationship("BookingModel", back_populates="flight")


class BookingModel(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    flight_id = Column(Integer, ForeignKey("flights.id"), nullable=False)
    passenger_name = Column(String, nullable=False)
    passenger_email = Column(String, nullable=False)
    num_passengers = Column(Integer, nullable=False)
    seat_class = Column(String, nullable=False)  # economy / business / first
    total_price = Column(Float, nullable=False)
    status = Column(String, default="confirmed")  # confirmed / cancelled
    created_at = Column(DateTime, server_default=func.now())

    flight = relationship("FlightModel", back_populates="bookings")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class FlightOut(BaseModel):
    id: int
    flight_number: str
    origin: str
    destination: str
    departure_date: dt.date
    departure_time: str
    arrival_time: str
    total_seats: int
    available_seats: int
    base_price: float
    status: str

    model_config = {"from_attributes": True}


class BookingCreate(BaseModel):
    flight_id: int
    passenger_name: str
    passenger_email: str
    num_passengers: int = Field(ge=1)
    seat_class: str = "economy"


class BookingOut(BaseModel):
    id: int
    flight_id: int
    flight_number: str | None = None
    origin: str | None = None
    destination: str | None = None
    departure_date: dt.date | None = None
    departure_time: str | None = None
    passenger_name: str
    passenger_email: str
    num_passengers: int
    seat_class: str
    total_price: float
    status: str
    created_at: dt.datetime | None = None

    model_config = {"from_attributes": True}


class PricingOut(BaseModel):
    flight_id: int
    flight_number: str
    origin: str
    destination: str
    departure_date: dt.date
    seat_class: str
    base_price: float
    class_multiplier: float
    price_per_passenger: float
    num_passengers: int
    total_price: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def calculate_price(base_price: float, seat_class: str, num_passengers: int):
    multiplier = SEAT_CLASS_MULTIPLIERS.get(seat_class, 1.0)
    per_passenger = round(base_price * multiplier, 2)
    return per_passenger, round(per_passenger * num_passengers, 2), multiplier


def booking_to_out(b: BookingModel) -> BookingOut:
    return BookingOut(
        id=b.id,
        flight_id=b.flight_id,
        flight_number=b.flight.flight_number,
        origin=b.flight.origin,
        destination=b.flight.destination,
        departure_date=b.flight.departure_date,
        departure_time=b.flight.departure_time,
        passenger_name=b.passenger_name,
        passenger_email=b.passenger_email,
        num_passengers=b.num_passengers,
        seat_class=b.seat_class,
        total_price=b.total_price,
        status=b.status,
        created_at=b.created_at,
    )


SEED_FLIGHTS = [
    ("SM101", "New York",    "Los Angeles", "2026-03-10", "08:00", "11:30", 180, 199.0),
    ("SM102", "Los Angeles", "New York",    "2026-03-10", "14:00", "22:15", 180, 209.0),
    ("SM201", "New York",    "Chicago",     "2026-03-11", "07:30", "09:45", 150, 129.0),
    ("SM202", "Chicago",     "New York",    "2026-03-11", "16:00", "20:10", 150, 139.0),
    ("SM301", "Chicago",     "Miami",       "2026-03-12", "09:00", "13:15", 160, 179.0),
    ("SM302", "Miami",       "Chicago",     "2026-03-12", "15:30", "19:40", 160, 169.0),
    ("SM401", "Los Angeles", "Seattle",     "2026-03-13", "06:45", "09:15", 140, 99.0),
    ("SM402", "Seattle",     "Los Angeles", "2026-03-13", "17:00", "19:30", 140, 109.0),
    ("SM501", "Miami",       "Denver",      "2026-03-14", "10:00", "13:00", 120, 189.0),
    ("SM502", "Denver",      "Miami",       "2026-03-14", "14:30", "20:30", 120, 199.0),
    ("SM601", "Seattle",     "Denver",      "2026-03-15", "08:00", "11:30", 130, 149.0),
    ("SM602", "Denver",      "Seattle",     "2026-03-15", "13:00", "15:00", 130, 139.0),
    ("SM701", "New York",    "Miami",       "2026-03-16", "06:00", "09:15", 180, 159.0),
    ("SM702", "Miami",       "New York",    "2026-03-16", "18:00", "21:15", 180, 169.0),
    ("SM801", "Los Angeles", "Denver",      "2026-03-17", "11:00", "14:00", 150, 119.0),
]


def seed_db():
    db = SessionLocal()
    if db.query(FlightModel).count() == 0:
        for fn, orig, dest, dep_date, dep_time, arr_time, seats, price in SEED_FLIGHTS:
            db.add(FlightModel(
                flight_number=fn,
                origin=orig,
                destination=dest,
                departure_date=dt.date.fromisoformat(dep_date),
                departure_time=dep_time,
                arrival_time=arr_time,
                total_seats=seats,
                available_seats=seats,
                base_price=price,
            ))
        db.commit()
    db.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_db()
    yield


app = FastAPI(
    title=f"{AIRLINE_NAME} — Flight Reservation API",
    description=(
        f"A simple flight reservation API for {AIRLINE_NAME}, designed for LLM / AI-agent consumption. "
        "Search flights, check availability, get pricing by seat class, and manage bookings."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.environ.get("API_KEY")


@app.middleware("http")
async def check_api_key(request: Request, call_next):
    if API_KEY and request.url.path.startswith("/api/"):
        key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if key != API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key. Provide via X-API-Key header or api_key query parameter."},
            )
    return await call_next(request)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "airline": AIRLINE_NAME}


@app.get("/api/schema")
def api_schema():
    """Plain-English tool manifest for LLM agents."""
    return {
        "service": f"{AIRLINE_NAME} Flight Reservation API",
        "base_url": "/api",
        "seat_classes": list(SEAT_CLASS_MULTIPLIERS.keys()),
        "seat_class_multipliers": SEAT_CLASS_MULTIPLIERS,
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/flights",
                "description": "List all flights. Optionally filter by origin, destination, or date.",
                "parameters": {
                    "origin": "string — optional, city name",
                    "destination": "string — optional, city name",
                    "date": "date (YYYY-MM-DD) — optional",
                },
            },
            {
                "method": "GET",
                "path": "/api/flights/search",
                "description": "Search for available flights with enough seats for the requested number of passengers.",
                "parameters": {
                    "origin": "string — required, departure city",
                    "destination": "string — required, arrival city",
                    "date": "date (YYYY-MM-DD) — optional, filter by departure date",
                    "passengers": "integer — optional, minimum available seats required",
                },
            },
            {
                "method": "GET",
                "path": "/api/flights/{id}",
                "description": "Get full details of a specific flight by ID, including current seat availability.",
            },
            {
                "method": "GET",
                "path": "/api/pricing",
                "description": "Get a price quote for a flight. Price depends on seat class (economy 1x, business 2.5x, first 5x).",
                "parameters": {
                    "flight_id": "integer — required",
                    "seat_class": "string — optional (economy / business / first, default: economy)",
                    "passengers": "integer — optional (default: 1)",
                },
            },
            {
                "method": "POST",
                "path": "/api/bookings",
                "description": "Create a new booking. Decrements available seats on the flight.",
                "body": {
                    "flight_id": "integer",
                    "passenger_name": "string",
                    "passenger_email": "string",
                    "num_passengers": "integer (>=1)",
                    "seat_class": "string (economy / business / first, default: economy)",
                },
            },
            {
                "method": "GET",
                "path": "/api/bookings",
                "description": "List all bookings. Optionally filter by status.",
                "parameters": {
                    "status": "string — optional (confirmed / cancelled)",
                },
            },
            {
                "method": "GET",
                "path": "/api/bookings/{id}",
                "description": "Get details of a specific booking by ID.",
            },
            {
                "method": "DELETE",
                "path": "/api/bookings/{id}",
                "description": "Cancel a booking by ID. Restores available seats on the flight.",
            },
            {
                "method": "GET",
                "path": "/api/destinations",
                "description": "List all unique cities served as origins and destinations.",
            },
        ],
    }


@app.get("/api/destinations")
def list_destinations(db: Session = Depends(get_db)):
    origins = {r[0] for r in db.query(FlightModel.origin).distinct().all()}
    destinations = {r[0] for r in db.query(FlightModel.destination).distinct().all()}
    cities = sorted(origins | destinations)
    return {"cities": cities}


@app.get("/api/flights", response_model=list[FlightOut])
def list_flights(
    origin: Optional[str] = Query(None),
    destination: Optional[str] = Query(None),
    date: Optional[dt.date] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(FlightModel)
    if origin:
        query = query.filter(FlightModel.origin.ilike(f"%{origin}%"))
    if destination:
        query = query.filter(FlightModel.destination.ilike(f"%{destination}%"))
    if date:
        query = query.filter(FlightModel.departure_date == date)
    return query.order_by(FlightModel.departure_date, FlightModel.departure_time).all()


@app.get("/api/flights/search", response_model=list[FlightOut])
def search_flights(
    origin: str = Query(...),
    destination: str = Query(...),
    date: Optional[dt.date] = Query(None),
    passengers: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    query = db.query(FlightModel).filter(
        FlightModel.origin.ilike(f"%{origin}%"),
        FlightModel.destination.ilike(f"%{destination}%"),
        FlightModel.status == "scheduled",
    )
    if date:
        query = query.filter(FlightModel.departure_date == date)
    if passengers:
        query = query.filter(FlightModel.available_seats >= passengers)
    return query.order_by(FlightModel.departure_date, FlightModel.departure_time).all()


@app.get("/api/flights/{flight_id}", response_model=FlightOut)
def get_flight(flight_id: int, db: Session = Depends(get_db)):
    flight = db.query(FlightModel).filter(FlightModel.id == flight_id).first()
    if not flight:
        raise HTTPException(404, "Flight not found")
    return flight


@app.get("/api/pricing", response_model=PricingOut)
def get_pricing(
    flight_id: int = Query(...),
    seat_class: str = Query("economy"),
    passengers: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    if seat_class not in SEAT_CLASS_MULTIPLIERS:
        raise HTTPException(400, f"Invalid seat_class. Must be one of: {', '.join(SEAT_CLASS_MULTIPLIERS)}")

    flight = db.query(FlightModel).filter(FlightModel.id == flight_id).first()
    if not flight:
        raise HTTPException(404, "Flight not found")

    per_passenger, total, multiplier = calculate_price(flight.base_price, seat_class, passengers)

    return PricingOut(
        flight_id=flight.id,
        flight_number=flight.flight_number,
        origin=flight.origin,
        destination=flight.destination,
        departure_date=flight.departure_date,
        seat_class=seat_class,
        base_price=flight.base_price,
        class_multiplier=multiplier,
        price_per_passenger=per_passenger,
        num_passengers=passengers,
        total_price=total,
    )


@app.post("/api/bookings", response_model=BookingOut, status_code=201)
def create_booking(data: BookingCreate, db: Session = Depends(get_db)):
    if data.seat_class not in SEAT_CLASS_MULTIPLIERS:
        raise HTTPException(400, f"Invalid seat_class. Must be one of: {', '.join(SEAT_CLASS_MULTIPLIERS)}")

    flight = db.query(FlightModel).filter(FlightModel.id == data.flight_id).first()
    if not flight:
        raise HTTPException(404, "Flight not found")

    if flight.status != "scheduled":
        raise HTTPException(400, f"Flight {flight.flight_number} is {flight.status}, cannot book")

    if data.num_passengers > flight.available_seats:
        raise HTTPException(
            409,
            f"Flight {flight.flight_number} only has {flight.available_seats} seats available, "
            f"but {data.num_passengers} requested",
        )

    _, total, _ = calculate_price(flight.base_price, data.seat_class, data.num_passengers)

    booking = BookingModel(
        flight_id=data.flight_id,
        passenger_name=data.passenger_name,
        passenger_email=data.passenger_email,
        num_passengers=data.num_passengers,
        seat_class=data.seat_class,
        total_price=total,
    )
    flight.available_seats -= data.num_passengers

    db.add(booking)
    db.commit()
    db.refresh(booking)

    return booking_to_out(booking)


@app.get("/api/bookings", response_model=list[BookingOut])
def list_bookings(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(BookingModel).join(FlightModel)
    if status:
        query = query.filter(BookingModel.status == status)
    return [booking_to_out(b) for b in query.order_by(BookingModel.created_at.desc()).all()]


@app.get("/api/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, db: Session = Depends(get_db)):
    b = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
    if not b:
        raise HTTPException(404, "Booking not found")
    return booking_to_out(b)


@app.delete("/api/bookings/{booking_id}", response_model=BookingOut)
def cancel_booking(booking_id: int, db: Session = Depends(get_db)):
    b = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
    if not b:
        raise HTTPException(404, "Booking not found")
    if b.status == "cancelled":
        raise HTTPException(400, "Booking is already cancelled")

    b.status = "cancelled"
    b.flight.available_seats += b.num_passengers

    db.commit()
    db.refresh(b)

    return booking_to_out(b)


if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
