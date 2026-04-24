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
    create_engine, Column, Integer, String, Date, DateTime,
    ForeignKey, func,
)
from sqlalchemy.orm import (
    DeclarativeBase, Session, sessionmaker, relationship,
)

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

os.makedirs("data", exist_ok=True)
DATABASE_URL = "sqlite:///./data/restaurant.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

TIME_SLOTS = ["11:00", "12:30", "14:00", "18:00", "19:30", "21:00"]


class Base(DeclarativeBase):
    pass


class TableModel(Base):
    __tablename__ = "tables"

    id = Column(Integer, primary_key=True, index=True)
    table_number = Column(String, unique=True, nullable=False)
    capacity = Column(Integer, nullable=False)
    location = Column(String, nullable=False)  # indoor / outdoor / patio / bar

    reservations = relationship("ReservationModel", back_populates="table")


class ReservationModel(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=False)
    guest_name = Column(String, nullable=False)
    guest_email = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    time_slot = Column(String, nullable=False)
    party_size = Column(Integer, nullable=False)
    special_requests = Column(String, default="")
    status = Column(String, default="confirmed")  # confirmed / cancelled
    created_at = Column(DateTime, server_default=func.now())

    table = relationship("TableModel", back_populates="reservations")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TableOut(BaseModel):
    id: int
    table_number: str
    capacity: int
    location: str

    model_config = {"from_attributes": True}


class AvailableTableOut(TableOut):
    available: bool = True


class ReservationCreate(BaseModel):
    table_id: int
    guest_name: str
    guest_email: str
    date: dt.date
    time_slot: str
    party_size: int = Field(ge=1)
    special_requests: str = ""


class ReservationOut(BaseModel):
    id: int
    table_id: int
    table_number: str | None = None
    location: str | None = None
    guest_name: str
    guest_email: str
    date: dt.date
    time_slot: str
    party_size: int
    special_requests: str
    status: str
    created_at: dt.datetime | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_table_available(
    db: Session, table_id: int, date: dt.date, time_slot: str,
    exclude_reservation_id: int | None = None,
) -> bool:
    query = db.query(ReservationModel).filter(
        ReservationModel.table_id == table_id,
        ReservationModel.status == "confirmed",
        ReservationModel.date == date,
        ReservationModel.time_slot == time_slot,
    )
    if exclude_reservation_id:
        query = query.filter(ReservationModel.id != exclude_reservation_id)
    return query.count() == 0


def reservation_to_out(r: ReservationModel) -> ReservationOut:
    return ReservationOut(
        id=r.id,
        table_id=r.table_id,
        table_number=r.table.table_number,
        location=r.table.location,
        guest_name=r.guest_name,
        guest_email=r.guest_email,
        date=r.date,
        time_slot=r.time_slot,
        party_size=r.party_size,
        special_requests=r.special_requests,
        status=r.status,
        created_at=r.created_at,
    )


SEED_TABLES = [
    ("T1", 2, "indoor"),
    ("T2", 2, "indoor"),
    ("T3", 4, "indoor"),
    ("T4", 4, "indoor"),
    ("T5", 6, "indoor"),
    ("T6", 2, "bar"),
    ("T7", 2, "bar"),
    ("T8", 4, "patio"),
    ("T9", 4, "patio"),
    ("T10", 6, "patio"),
    ("T11", 4, "outdoor"),
    ("T12", 8, "outdoor"),
]


def seed_db():
    db = SessionLocal()
    if db.query(TableModel).count() == 0:
        for number, cap, loc in SEED_TABLES:
            db.add(TableModel(table_number=number, capacity=cap, location=loc))
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
    title="Restaurant Reservation API",
    description=(
        "A simple restaurant reservation API designed for LLM / AI-agent consumption. "
        "Query table availability by date and time slot, manage reservations."
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
        "service": "Restaurant Reservation API",
        "base_url": "/api",
        "time_slots": TIME_SLOTS,
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/tables",
                "description": "List all restaurant tables with their number, seating capacity, and location (indoor, outdoor, patio, bar).",
            },
            {
                "method": "GET",
                "path": "/api/tables/available",
                "description": "Find tables available for a specific date and time slot, optionally filtered by minimum party size.",
                "parameters": {
                    "date": "date (YYYY-MM-DD) — required",
                    "time_slot": "string (HH:MM, e.g. '19:00') — required, must be one of the valid time slots",
                    "party_size": "integer — optional, filter tables with enough capacity",
                },
            },
            {
                "method": "GET",
                "path": "/api/time-slots",
                "description": "List all valid time slots for reservations. Returns lunch and dinner slots.",
            },
            {
                "method": "POST",
                "path": "/api/reservations",
                "description": "Create a new reservation for a specific table, date, and time slot.",
                "body": {
                    "table_id": "integer",
                    "guest_name": "string",
                    "guest_email": "string",
                    "date": "date (YYYY-MM-DD)",
                    "time_slot": "string (HH:MM)",
                    "party_size": "integer (>=1)",
                    "special_requests": "string (optional)",
                },
            },
            {
                "method": "GET",
                "path": "/api/reservations",
                "description": "List all reservations. Optionally filter by date and/or status.",
                "parameters": {
                    "date": "date (YYYY-MM-DD) — optional",
                    "status": "string — optional (confirmed / cancelled)",
                },
            },
            {
                "method": "GET",
                "path": "/api/reservations/{id}",
                "description": "Get details of a specific reservation by ID.",
            },
            {
                "method": "DELETE",
                "path": "/api/reservations/{id}",
                "description": "Cancel a reservation by ID. Sets status to 'cancelled'.",
            },
        ],
    }


@app.get("/api/time-slots")
def list_time_slots():
    return {
        "time_slots": TIME_SLOTS,
        "note": "Each slot is a 1.5-hour dining window.",
    }


@app.get("/api/tables", response_model=list[TableOut])
def list_tables(db: Session = Depends(get_db)):
    return db.query(TableModel).order_by(TableModel.table_number).all()


@app.get("/api/tables/available", response_model=list[AvailableTableOut])
def available_tables(
    date: dt.date = Query(...),
    time_slot: str = Query(...),
    party_size: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    if time_slot not in TIME_SLOTS:
        raise HTTPException(400, f"Invalid time_slot. Must be one of: {', '.join(TIME_SLOTS)}")

    tables = db.query(TableModel)
    if party_size:
        tables = tables.filter(TableModel.capacity >= party_size)

    result = []
    for table in tables.order_by(TableModel.table_number).all():
        if is_table_available(db, table.id, date, time_slot):
            result.append(table)
    return result


@app.post("/api/reservations", response_model=ReservationOut, status_code=201)
def create_reservation(data: ReservationCreate, db: Session = Depends(get_db)):
    if data.time_slot not in TIME_SLOTS:
        raise HTTPException(400, f"Invalid time_slot. Must be one of: {', '.join(TIME_SLOTS)}")

    table = db.query(TableModel).filter(TableModel.id == data.table_id).first()
    if not table:
        raise HTTPException(404, "Table not found")

    if data.party_size > table.capacity:
        raise HTTPException(
            400,
            f"Table {table.table_number} has a max capacity of {table.capacity} guests",
        )

    if not is_table_available(db, table.id, data.date, data.time_slot):
        raise HTTPException(
            409,
            f"Table {table.table_number} is already reserved for {data.date} at {data.time_slot}",
        )

    reservation = ReservationModel(
        table_id=data.table_id,
        guest_name=data.guest_name,
        guest_email=data.guest_email,
        date=data.date,
        time_slot=data.time_slot,
        party_size=data.party_size,
        special_requests=data.special_requests,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    return reservation_to_out(reservation)


@app.get("/api/reservations", response_model=list[ReservationOut])
def list_reservations(
    date: Optional[dt.date] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(ReservationModel).join(TableModel)
    if date:
        query = query.filter(ReservationModel.date == date)
    if status:
        query = query.filter(ReservationModel.status == status)

    return [reservation_to_out(r) for r in query.order_by(ReservationModel.created_at.desc()).all()]


@app.get("/api/reservations/{reservation_id}", response_model=ReservationOut)
def get_reservation(reservation_id: int, db: Session = Depends(get_db)):
    r = db.query(ReservationModel).filter(ReservationModel.id == reservation_id).first()
    if not r:
        raise HTTPException(404, "Reservation not found")
    return reservation_to_out(r)


@app.delete("/api/reservations/{reservation_id}", response_model=ReservationOut)
def cancel_reservation(reservation_id: int, db: Session = Depends(get_db)):
    r = db.query(ReservationModel).filter(ReservationModel.id == reservation_id).first()
    if not r:
        raise HTTPException(404, "Reservation not found")
    if r.status == "cancelled":
        raise HTTPException(400, "Reservation is already cancelled")

    r.status = "cancelled"
    db.commit()
    db.refresh(r)

    return reservation_to_out(r)


if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
