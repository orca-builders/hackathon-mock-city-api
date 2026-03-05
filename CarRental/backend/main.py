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

DATABASE_URL = "sqlite:///./carrental.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

CATEGORIES = ["economy", "compact", "midsize", "fullsize", "suv", "premium", "luxury"]


class Base(DeclarativeBase):
    pass


class VehicleModel(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, unique=True, nullable=False)
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    category = Column(String, nullable=False)
    seats = Column(Integer, nullable=False)
    daily_rate = Column(Float, nullable=False)
    status = Column(String, default="available")  # available / maintenance

    rentals = relationship("RentalModel", back_populates="vehicle")


class RentalModel(Base):
    __tablename__ = "rentals"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    customer_name = Column(String, nullable=False)
    customer_email = Column(String, nullable=False)
    pickup_date = Column(Date, nullable=False)
    return_date = Column(Date, nullable=False)
    total_price = Column(Float, nullable=False)
    status = Column(String, default="confirmed")  # confirmed / cancelled / completed
    created_at = Column(DateTime, server_default=func.now())

    vehicle = relationship("VehicleModel", back_populates="rentals")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class VehicleOut(BaseModel):
    id: int
    plate_number: str
    make: str
    model: str
    year: int
    category: str
    seats: int
    daily_rate: float
    status: str

    model_config = {"from_attributes": True}


class AvailableVehicleOut(VehicleOut):
    available: bool = True


class RentalCreate(BaseModel):
    vehicle_id: int
    customer_name: str
    customer_email: str
    pickup_date: dt.date
    return_date: dt.date


class RentalOut(BaseModel):
    id: int
    vehicle_id: int
    plate_number: str | None = None
    make: str | None = None
    model: str | None = None
    category: str | None = None
    customer_name: str
    customer_email: str
    pickup_date: dt.date
    return_date: dt.date
    total_price: float
    status: str
    created_at: dt.datetime | None = None

    model_config = {"from_attributes": True}


class PricingOut(BaseModel):
    vehicle_id: int
    plate_number: str
    make: str
    model: str
    category: str
    daily_rate: float
    pickup_date: dt.date
    return_date: dt.date
    num_days: int
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


def is_vehicle_available(
    db: Session, vehicle_id: int, pickup_date: dt.date, return_date: dt.date,
    exclude_rental_id: int | None = None,
) -> bool:
    query = db.query(RentalModel).filter(
        RentalModel.vehicle_id == vehicle_id,
        RentalModel.status == "confirmed",
        RentalModel.pickup_date < return_date,
        RentalModel.return_date > pickup_date,
    )
    if exclude_rental_id:
        query = query.filter(RentalModel.id != exclude_rental_id)
    return query.count() == 0


def rental_to_out(r: RentalModel) -> RentalOut:
    return RentalOut(
        id=r.id,
        vehicle_id=r.vehicle_id,
        plate_number=r.vehicle.plate_number,
        make=r.vehicle.make,
        model=r.vehicle.model,
        category=r.vehicle.category,
        customer_name=r.customer_name,
        customer_email=r.customer_email,
        pickup_date=r.pickup_date,
        return_date=r.return_date,
        total_price=r.total_price,
        status=r.status,
        created_at=r.created_at,
    )


SEED_VEHICLES = [
    ("ECO-001", "Toyota",    "Yaris",       2024, "economy",  5, 35.0),
    ("ECO-002", "Nissan",    "Versa",       2024, "economy",  5, 39.0),
    ("CMP-001", "Honda",     "Civic",       2025, "compact",  5, 45.0),
    ("CMP-002", "Toyota",    "Corolla",     2025, "compact",  5, 49.0),
    ("MID-001", "Honda",     "Accord",      2025, "midsize",  5, 59.0),
    ("MID-002", "Toyota",    "Camry",       2025, "midsize",  5, 65.0),
    ("FUL-001", "Chevrolet", "Impala",      2024, "fullsize", 5, 75.0),
    ("FUL-002", "Ford",      "Taurus",      2024, "fullsize", 5, 79.0),
    ("SUV-001", "Toyota",    "RAV4",        2025, "suv",      5, 89.0),
    ("SUV-002", "Ford",      "Explorer",    2025, "suv",      7, 99.0),
    ("SUV-003", "Jeep",      "Grand Cherokee", 2024, "suv",   5, 95.0),
    ("PRE-001", "BMW",       "3 Series",    2025, "premium",  5, 129.0),
    ("PRE-002", "Audi",      "A4",          2025, "premium",  5, 139.0),
    ("PRE-003", "Mercedes",  "C-Class",     2025, "premium",  5, 135.0),
    ("LUX-001", "Mercedes",  "S-Class",     2025, "luxury",   5, 199.0),
    ("LUX-002", "BMW",       "7 Series",    2025, "luxury",   5, 189.0),
]


def seed_db():
    db = SessionLocal()
    if db.query(VehicleModel).count() == 0:
        for plate, make, model, year, cat, seats, rate in SEED_VEHICLES:
            db.add(VehicleModel(
                plate_number=plate, make=make, model=model, year=year,
                category=cat, seats=seats, daily_rate=rate,
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
    title="Car Rental API",
    description=(
        "A simple car rental API designed for LLM / AI-agent consumption. "
        "Browse the fleet by category, check availability, get pricing, and manage rentals."
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
    return {"status": "ok"}


@app.get("/api/schema")
def api_schema():
    """Plain-English tool manifest for LLM agents."""
    return {
        "service": "Car Rental API",
        "base_url": "/api",
        "vehicle_categories": CATEGORIES,
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/vehicles",
                "description": "List all vehicles in the fleet. Optionally filter by category or minimum seats.",
                "parameters": {
                    "category": "string — optional, one of: " + ", ".join(CATEGORIES),
                    "seats": "integer — optional, minimum number of seats",
                },
            },
            {
                "method": "GET",
                "path": "/api/vehicles/available",
                "description": "Find vehicles available for a given date range. Optionally filter by category or minimum seats.",
                "parameters": {
                    "pickup_date": "date (YYYY-MM-DD) — required",
                    "return_date": "date (YYYY-MM-DD) — required",
                    "category": "string — optional",
                    "seats": "integer — optional, minimum number of seats",
                },
            },
            {
                "method": "GET",
                "path": "/api/vehicles/{id}",
                "description": "Get details of a specific vehicle by ID.",
            },
            {
                "method": "GET",
                "path": "/api/categories",
                "description": "List all vehicle categories with their typical daily rate ranges.",
            },
            {
                "method": "GET",
                "path": "/api/pricing",
                "description": "Get a price quote for a specific vehicle and date range. Returns daily rate, number of days, and total price.",
                "parameters": {
                    "vehicle_id": "integer — required",
                    "pickup_date": "date (YYYY-MM-DD) — required",
                    "return_date": "date (YYYY-MM-DD) — required",
                },
            },
            {
                "method": "POST",
                "path": "/api/rentals",
                "description": "Create a new rental reservation.",
                "body": {
                    "vehicle_id": "integer",
                    "customer_name": "string",
                    "customer_email": "string",
                    "pickup_date": "date (YYYY-MM-DD)",
                    "return_date": "date (YYYY-MM-DD)",
                },
            },
            {
                "method": "GET",
                "path": "/api/rentals",
                "description": "List all rentals. Optionally filter by status.",
                "parameters": {
                    "status": "string — optional (confirmed / cancelled / completed)",
                },
            },
            {
                "method": "GET",
                "path": "/api/rentals/{id}",
                "description": "Get details of a specific rental by ID.",
            },
            {
                "method": "DELETE",
                "path": "/api/rentals/{id}",
                "description": "Cancel a rental by ID. Sets status to 'cancelled'.",
            },
        ],
    }


@app.get("/api/categories")
def list_categories(db: Session = Depends(get_db)):
    result = []
    for cat in CATEGORIES:
        vehicles = db.query(VehicleModel).filter(VehicleModel.category == cat).all()
        if vehicles:
            rates = [v.daily_rate for v in vehicles]
            result.append({
                "category": cat,
                "vehicle_count": len(vehicles),
                "min_daily_rate": min(rates),
                "max_daily_rate": max(rates),
            })
    return result


@app.get("/api/vehicles", response_model=list[VehicleOut])
def list_vehicles(
    category: Optional[str] = Query(None),
    seats: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    query = db.query(VehicleModel)
    if category:
        if category not in CATEGORIES:
            raise HTTPException(400, f"Invalid category. Must be one of: {', '.join(CATEGORIES)}")
        query = query.filter(VehicleModel.category == category)
    if seats:
        query = query.filter(VehicleModel.seats >= seats)
    return query.order_by(VehicleModel.category, VehicleModel.plate_number).all()


@app.get("/api/vehicles/available", response_model=list[AvailableVehicleOut])
def available_vehicles(
    pickup_date: dt.date = Query(...),
    return_date: dt.date = Query(...),
    category: Optional[str] = Query(None),
    seats: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    if return_date <= pickup_date:
        raise HTTPException(400, "return_date must be after pickup_date")

    query = db.query(VehicleModel).filter(VehicleModel.status == "available")
    if category:
        if category not in CATEGORIES:
            raise HTTPException(400, f"Invalid category. Must be one of: {', '.join(CATEGORIES)}")
        query = query.filter(VehicleModel.category == category)
    if seats:
        query = query.filter(VehicleModel.seats >= seats)

    result = []
    for v in query.order_by(VehicleModel.category, VehicleModel.plate_number).all():
        if is_vehicle_available(db, v.id, pickup_date, return_date):
            result.append(v)
    return result


@app.get("/api/vehicles/{vehicle_id}", response_model=VehicleOut)
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    v = db.query(VehicleModel).filter(VehicleModel.id == vehicle_id).first()
    if not v:
        raise HTTPException(404, "Vehicle not found")
    return v


@app.get("/api/pricing", response_model=PricingOut)
def get_pricing(
    vehicle_id: int = Query(...),
    pickup_date: dt.date = Query(...),
    return_date: dt.date = Query(...),
    db: Session = Depends(get_db),
):
    if return_date <= pickup_date:
        raise HTTPException(400, "return_date must be after pickup_date")

    v = db.query(VehicleModel).filter(VehicleModel.id == vehicle_id).first()
    if not v:
        raise HTTPException(404, "Vehicle not found")

    num_days = (return_date - pickup_date).days
    total = round(v.daily_rate * num_days, 2)

    return PricingOut(
        vehicle_id=v.id,
        plate_number=v.plate_number,
        make=v.make,
        model=v.model,
        category=v.category,
        daily_rate=v.daily_rate,
        pickup_date=pickup_date,
        return_date=return_date,
        num_days=num_days,
        total_price=total,
    )


@app.post("/api/rentals", response_model=RentalOut, status_code=201)
def create_rental(data: RentalCreate, db: Session = Depends(get_db)):
    if data.return_date <= data.pickup_date:
        raise HTTPException(400, "return_date must be after pickup_date")

    v = db.query(VehicleModel).filter(VehicleModel.id == data.vehicle_id).first()
    if not v:
        raise HTTPException(404, "Vehicle not found")

    if v.status != "available":
        raise HTTPException(400, f"Vehicle {v.plate_number} is currently under {v.status}")

    if not is_vehicle_available(db, v.id, data.pickup_date, data.return_date):
        raise HTTPException(
            409,
            f"Vehicle {v.plate_number} ({v.make} {v.model}) is not available for the requested dates",
        )

    num_days = (data.return_date - data.pickup_date).days
    total = round(v.daily_rate * num_days, 2)

    rental = RentalModel(
        vehicle_id=data.vehicle_id,
        customer_name=data.customer_name,
        customer_email=data.customer_email,
        pickup_date=data.pickup_date,
        return_date=data.return_date,
        total_price=total,
    )
    db.add(rental)
    db.commit()
    db.refresh(rental)

    return rental_to_out(rental)


@app.get("/api/rentals", response_model=list[RentalOut])
def list_rentals(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(RentalModel).join(VehicleModel)
    if status:
        query = query.filter(RentalModel.status == status)
    return [rental_to_out(r) for r in query.order_by(RentalModel.created_at.desc()).all()]


@app.get("/api/rentals/{rental_id}", response_model=RentalOut)
def get_rental(rental_id: int, db: Session = Depends(get_db)):
    r = db.query(RentalModel).filter(RentalModel.id == rental_id).first()
    if not r:
        raise HTTPException(404, "Rental not found")
    return rental_to_out(r)


@app.delete("/api/rentals/{rental_id}", response_model=RentalOut)
def cancel_rental(rental_id: int, db: Session = Depends(get_db)):
    r = db.query(RentalModel).filter(RentalModel.id == rental_id).first()
    if not r:
        raise HTTPException(404, "Rental not found")
    if r.status == "cancelled":
        raise HTTPException(400, "Rental is already cancelled")

    r.status = "cancelled"
    db.commit()
    db.refresh(r)

    return rental_to_out(r)


if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
