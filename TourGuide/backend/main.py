from __future__ import annotations

import datetime as dt
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
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

DATABASE_URL = "sqlite:///./tourguide.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

TOUR_CATEGORIES = ["cultural", "adventure", "food", "nature", "nightlife", "historical"]
DIFFICULTIES = ["easy", "moderate", "challenging"]


class Base(DeclarativeBase):
    pass


class TourModel(Base):
    __tablename__ = "tours"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    category = Column(String, nullable=False)
    difficulty = Column(String, nullable=False)
    duration_hours = Column(Float, nullable=False)
    max_group_size = Column(Integer, nullable=False)
    price_per_person = Column(Float, nullable=False)
    location = Column(String, nullable=False)
    status = Column(String, default="active")  # active / inactive

    bookings = relationship("TourBookingModel", back_populates="tour")


class TourBookingModel(Base):
    __tablename__ = "tour_bookings"

    id = Column(Integer, primary_key=True, index=True)
    tour_id = Column(Integer, ForeignKey("tours.id"), nullable=False)
    tour_date = Column(Date, nullable=False)
    guest_name = Column(String, nullable=False)
    guest_email = Column(String, nullable=False)
    num_guests = Column(Integer, nullable=False)
    total_price = Column(Float, nullable=False)
    status = Column(String, default="confirmed")  # confirmed / cancelled
    created_at = Column(DateTime, server_default=func.now())

    tour = relationship("TourModel", back_populates="bookings")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TourOut(BaseModel):
    id: int
    name: str
    description: str
    category: str
    difficulty: str
    duration_hours: float
    max_group_size: int
    price_per_person: float
    location: str
    status: str

    model_config = {"from_attributes": True}


class BookingCreate(BaseModel):
    tour_id: int
    tour_date: dt.date
    guest_name: str
    guest_email: str
    num_guests: int = Field(ge=1)


class BookingOut(BaseModel):
    id: int
    tour_id: int
    tour_name: str | None = None
    tour_category: str | None = None
    tour_date: dt.date
    guest_name: str
    guest_email: str
    num_guests: int
    total_price: float
    status: str
    created_at: dt.datetime | None = None

    model_config = {"from_attributes": True}


class PricingOut(BaseModel):
    tour_id: int
    tour_name: str
    category: str
    price_per_person: float
    num_guests: int
    total_price: float


class AvailabilityOut(BaseModel):
    tour_id: int
    tour_name: str
    date: dt.date
    max_group_size: int
    booked_spots: int
    remaining_spots: int
    available: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_booked_spots(db: Session, tour_id: int, tour_date: dt.date) -> int:
    result = db.query(func.coalesce(func.sum(TourBookingModel.num_guests), 0)).filter(
        TourBookingModel.tour_id == tour_id,
        TourBookingModel.tour_date == tour_date,
        TourBookingModel.status == "confirmed",
    ).scalar()
    return int(result)


def booking_to_out(b: TourBookingModel) -> BookingOut:
    return BookingOut(
        id=b.id,
        tour_id=b.tour_id,
        tour_name=b.tour.name,
        tour_category=b.tour.category,
        tour_date=b.tour_date,
        guest_name=b.guest_name,
        guest_email=b.guest_email,
        num_guests=b.num_guests,
        total_price=b.total_price,
        status=b.status,
        created_at=b.created_at,
    )


SEED_TOURS = [
    ("Old City Walking Tour", "Explore centuries-old streets, markets, and hidden courtyards with a local historian.", "cultural", "easy", 3.0, 20, 45.0, "Old Town"),
    ("Art Gallery Crawl", "Visit five contemporary art galleries with an art critic as your guide.", "cultural", "easy", 2.5, 15, 65.0, "Arts District"),
    ("Mountain Hiking Trail", "A full-day hike through alpine trails with breathtaking summit views.", "adventure", "challenging", 6.0, 12, 89.0, "Mountain Range"),
    ("Kayaking River Tour", "Paddle through scenic river canyons and spot local wildlife.", "adventure", "moderate", 4.0, 10, 75.0, "River Valley"),
    ("Street Food Tasting", "Sample 10+ local street food dishes across the city's best food stalls.", "food", "easy", 3.0, 15, 55.0, "Market Quarter"),
    ("Wine & Cheese Tour", "Exclusive tasting at three boutique wineries paired with artisan cheeses.", "food", "easy", 2.5, 12, 95.0, "Wine Country"),
    ("Sunset Safari Drive", "An evening game drive to see wildlife during the golden hour.", "nature", "easy", 5.0, 8, 120.0, "National Park"),
    ("Botanical Garden Walk", "A relaxing guided walk through rare plant collections and greenhouses.", "nature", "easy", 2.0, 20, 35.0, "City Gardens"),
    ("Rooftop Bar Hopping", "Hit the city's best rooftop bars with VIP access and welcome drinks.", "nightlife", "easy", 4.0, 16, 70.0, "Downtown"),
    ("Live Jazz Night", "An evening of live jazz at three intimate clubs with a drinks package.", "nightlife", "easy", 3.0, 14, 60.0, "Jazz Quarter"),
    ("Ancient Ruins Expedition", "A deep dive into archaeological sites with an expert archaeologist.", "historical", "moderate", 5.0, 15, 85.0, "Ancient Site"),
    ("War Memorial Tour", "A moving tour through wartime landmarks and memorial sites.", "historical", "easy", 2.5, 20, 40.0, "Memorial District"),
]


def seed_db():
    db = SessionLocal()
    if db.query(TourModel).count() == 0:
        for name, desc, cat, diff, dur, grp, price, loc in SEED_TOURS:
            db.add(TourModel(
                name=name, description=desc, category=cat, difficulty=diff,
                duration_hours=dur, max_group_size=grp,
                price_per_person=price, location=loc,
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
    title="Tour Guide API",
    description=(
        "A simple tour guide booking API designed for LLM / AI-agent consumption. "
        "Browse tours by category, difficulty, and price. Check availability and book tours."
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/schema")
def api_schema():
    """Plain-English tool manifest for LLM agents."""
    return {
        "service": "Tour Guide Booking API",
        "base_url": "/api",
        "tour_categories": TOUR_CATEGORIES,
        "difficulty_levels": DIFFICULTIES,
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/tours",
                "description": "List all tours. Optionally filter by category, difficulty, max price, or location.",
                "parameters": {
                    "category": f"string — optional, one of: {', '.join(TOUR_CATEGORIES)}",
                    "difficulty": f"string — optional, one of: {', '.join(DIFFICULTIES)}",
                    "max_price": "number — optional, maximum price per person",
                    "location": "string — optional, partial match on location",
                },
            },
            {
                "method": "GET",
                "path": "/api/tours/{id}",
                "description": "Get full details of a specific tour by ID.",
            },
            {
                "method": "GET",
                "path": "/api/tours/available",
                "description": "Check availability for a tour on a specific date. Returns remaining spots.",
                "parameters": {
                    "tour_id": "integer — required",
                    "date": "date (YYYY-MM-DD) — required",
                    "guests": "integer — optional, check if this many spots are available",
                },
            },
            {
                "method": "GET",
                "path": "/api/categories",
                "description": "List all tour categories with the number of tours in each.",
            },
            {
                "method": "GET",
                "path": "/api/pricing",
                "description": "Get a price quote for a tour. Returns price per person and total for the requested party size.",
                "parameters": {
                    "tour_id": "integer — required",
                    "guests": "integer — optional (default: 1)",
                },
            },
            {
                "method": "POST",
                "path": "/api/bookings",
                "description": "Create a new booking for a tour on a specific date.",
                "body": {
                    "tour_id": "integer",
                    "tour_date": "date (YYYY-MM-DD)",
                    "guest_name": "string",
                    "guest_email": "string",
                    "num_guests": "integer (>=1)",
                },
            },
            {
                "method": "GET",
                "path": "/api/bookings",
                "description": "List all bookings. Optionally filter by status or date.",
                "parameters": {
                    "status": "string — optional (confirmed / cancelled)",
                    "date": "date (YYYY-MM-DD) — optional",
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
                "description": "Cancel a booking by ID. Sets status to 'cancelled'.",
            },
        ],
    }


@app.get("/api/categories")
def list_categories(db: Session = Depends(get_db)):
    result = []
    for cat in TOUR_CATEGORIES:
        count = db.query(TourModel).filter(
            TourModel.category == cat, TourModel.status == "active"
        ).count()
        if count > 0:
            result.append({"category": cat, "tour_count": count})
    return result


@app.get("/api/tours", response_model=list[TourOut])
def list_tours(
    category: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    max_price: Optional[float] = Query(None),
    location: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(TourModel)
    if category:
        if category not in TOUR_CATEGORIES:
            raise HTTPException(400, f"Invalid category. Must be one of: {', '.join(TOUR_CATEGORIES)}")
        query = query.filter(TourModel.category == category)
    if difficulty:
        if difficulty not in DIFFICULTIES:
            raise HTTPException(400, f"Invalid difficulty. Must be one of: {', '.join(DIFFICULTIES)}")
        query = query.filter(TourModel.difficulty == difficulty)
    if max_price:
        query = query.filter(TourModel.price_per_person <= max_price)
    if location:
        query = query.filter(TourModel.location.ilike(f"%{location}%"))
    return query.order_by(TourModel.category, TourModel.name).all()


@app.get("/api/tours/available", response_model=AvailabilityOut)
def check_availability(
    tour_id: int = Query(...),
    date: dt.date = Query(...),
    guests: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    tour = db.query(TourModel).filter(TourModel.id == tour_id).first()
    if not tour:
        raise HTTPException(404, "Tour not found")

    booked = get_booked_spots(db, tour.id, date)
    remaining = tour.max_group_size - booked
    is_available = remaining >= (guests or 1)

    return AvailabilityOut(
        tour_id=tour.id,
        tour_name=tour.name,
        date=date,
        max_group_size=tour.max_group_size,
        booked_spots=booked,
        remaining_spots=remaining,
        available=is_available,
    )


@app.get("/api/tours/{tour_id}", response_model=TourOut)
def get_tour(tour_id: int, db: Session = Depends(get_db)):
    tour = db.query(TourModel).filter(TourModel.id == tour_id).first()
    if not tour:
        raise HTTPException(404, "Tour not found")
    return tour


@app.get("/api/pricing", response_model=PricingOut)
def get_pricing(
    tour_id: int = Query(...),
    guests: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    tour = db.query(TourModel).filter(TourModel.id == tour_id).first()
    if not tour:
        raise HTTPException(404, "Tour not found")

    total = round(tour.price_per_person * guests, 2)

    return PricingOut(
        tour_id=tour.id,
        tour_name=tour.name,
        category=tour.category,
        price_per_person=tour.price_per_person,
        num_guests=guests,
        total_price=total,
    )


@app.post("/api/bookings", response_model=BookingOut, status_code=201)
def create_booking(data: BookingCreate, db: Session = Depends(get_db)):
    tour = db.query(TourModel).filter(TourModel.id == data.tour_id).first()
    if not tour:
        raise HTTPException(404, "Tour not found")

    if tour.status != "active":
        raise HTTPException(400, f"Tour '{tour.name}' is currently {tour.status}")

    booked = get_booked_spots(db, tour.id, data.tour_date)
    remaining = tour.max_group_size - booked
    if data.num_guests > remaining:
        raise HTTPException(
            409,
            f"Tour '{tour.name}' on {data.tour_date} only has {remaining} spots remaining "
            f"(max {tour.max_group_size}), but {data.num_guests} requested",
        )

    total = round(tour.price_per_person * data.num_guests, 2)

    booking = TourBookingModel(
        tour_id=data.tour_id,
        tour_date=data.tour_date,
        guest_name=data.guest_name,
        guest_email=data.guest_email,
        num_guests=data.num_guests,
        total_price=total,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return booking_to_out(booking)


@app.get("/api/bookings", response_model=list[BookingOut])
def list_bookings(
    status: Optional[str] = Query(None),
    date: Optional[dt.date] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(TourBookingModel).join(TourModel)
    if status:
        query = query.filter(TourBookingModel.status == status)
    if date:
        query = query.filter(TourBookingModel.tour_date == date)
    return [booking_to_out(b) for b in query.order_by(TourBookingModel.created_at.desc()).all()]


@app.get("/api/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, db: Session = Depends(get_db)):
    b = db.query(TourBookingModel).filter(TourBookingModel.id == booking_id).first()
    if not b:
        raise HTTPException(404, "Booking not found")
    return booking_to_out(b)


@app.delete("/api/bookings/{booking_id}", response_model=BookingOut)
def cancel_booking(booking_id: int, db: Session = Depends(get_db)):
    b = db.query(TourBookingModel).filter(TourBookingModel.id == booking_id).first()
    if not b:
        raise HTTPException(404, "Booking not found")
    if b.status == "cancelled":
        raise HTTPException(400, "Booking is already cancelled")

    b.status = "cancelled"
    db.commit()
    db.refresh(b)

    return booking_to_out(b)


if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
