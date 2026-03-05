from __future__ import annotations

import datetime as dt
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
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

DATABASE_URL = "sqlite:///./hotel.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class RoomModel(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String, unique=True, nullable=False)
    room_type = Column(String, nullable=False)  # single / double / suite
    capacity = Column(Integer, nullable=False)
    base_price_per_night = Column(Float, nullable=False)

    reservations = relationship("ReservationModel", back_populates="room")


class ReservationModel(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    guest_name = Column(String, nullable=False)
    guest_email = Column(String, nullable=False)
    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)
    num_guests = Column(Integer, nullable=False)
    total_price = Column(Float, nullable=False)
    status = Column(String, default="confirmed")  # confirmed / cancelled
    created_at = Column(DateTime, server_default=func.now())

    room = relationship("RoomModel", back_populates="reservations")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class RoomOut(BaseModel):
    id: int
    room_number: str
    room_type: str
    capacity: int
    base_price_per_night: float

    model_config = {"from_attributes": True}


class ReservationCreate(BaseModel):
    room_id: int
    guest_name: str
    guest_email: str
    check_in: dt.date
    check_out: dt.date
    num_guests: int = Field(ge=1)


class ReservationOut(BaseModel):
    id: int
    room_id: int
    room_number: str | None = None
    guest_name: str
    guest_email: str
    check_in: dt.date
    check_out: dt.date
    num_guests: int
    total_price: float
    status: str
    created_at: dt.datetime | None = None

    model_config = {"from_attributes": True}


class PricingOut(BaseModel):
    room_id: int
    room_number: str
    room_type: str
    check_in: dt.date
    check_out: dt.date
    num_nights: int
    base_price_per_night: float
    total_price: float
    breakdown: list[dict]


class AvailableRoomOut(RoomOut):
    available: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def calculate_price(base_price: float, check_in: dt.date, check_out: dt.date):
    """Return (total, breakdown) with 1.2x weekend surcharge for Fri/Sat nights."""
    total = 0.0
    breakdown: list[dict] = []
    current = check_in
    while current < check_out:
        multiplier = 1.2 if current.weekday() in (4, 5) else 1.0
        night_price = round(base_price * multiplier, 2)
        breakdown.append({
            "date": current.isoformat(),
            "day": current.strftime("%A"),
            "price": night_price,
            "surcharge": multiplier > 1,
        })
        total += night_price
        current += dt.timedelta(days=1)
    return round(total, 2), breakdown


def is_room_available(
    db: Session, room_id: int, check_in: dt.date, check_out: dt.date,
    exclude_reservation_id: int | None = None,
) -> bool:
    query = db.query(ReservationModel).filter(
        ReservationModel.room_id == room_id,
        ReservationModel.status == "confirmed",
        ReservationModel.check_in < check_out,
        ReservationModel.check_out > check_in,
    )
    if exclude_reservation_id:
        query = query.filter(ReservationModel.id != exclude_reservation_id)
    return query.count() == 0


SEED_ROOMS = [
    ("101", "single", 1, 89.0),
    ("102", "single", 1, 89.0),
    ("201", "double", 2, 129.0),
    ("202", "double", 2, 129.0),
    ("203", "double", 3, 149.0),
    ("301", "double", 2, 139.0),
    ("302", "double", 4, 169.0),
    ("401", "suite", 4, 249.0),
    ("402", "suite", 3, 229.0),
    ("501", "suite", 6, 349.0),
]


def seed_db():
    db = SessionLocal()
    if db.query(RoomModel).count() == 0:
        for number, rtype, cap, price in SEED_ROOMS:
            db.add(RoomModel(
                room_number=number, room_type=rtype,
                capacity=cap, base_price_per_night=price,
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
    title="Hotel Reservation API",
    description=(
        "A simple hotel reservation API designed for LLM / AI-agent consumption. "
        "Query room availability, get pricing, and manage reservations."
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
        "service": "Hotel Reservation API",
        "base_url": "/api",
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/rooms",
                "description": "List all hotel rooms with their type, capacity, and base price per night.",
            },
            {
                "method": "GET",
                "path": "/api/rooms/available",
                "description": "Find rooms available for a given date range and party size.",
                "parameters": {
                    "check_in": "date (YYYY-MM-DD) — required",
                    "check_out": "date (YYYY-MM-DD) — required",
                    "guests": "integer — optional, filter rooms with enough capacity",
                },
            },
            {
                "method": "GET",
                "path": "/api/pricing",
                "description": "Get a detailed price quote for a specific room and date range. Includes per-night breakdown with weekend surcharges.",
                "parameters": {
                    "room_id": "integer — required",
                    "check_in": "date (YYYY-MM-DD) — required",
                    "check_out": "date (YYYY-MM-DD) — required",
                },
            },
            {
                "method": "POST",
                "path": "/api/reservations",
                "description": "Create a new reservation.",
                "body": {
                    "room_id": "integer",
                    "guest_name": "string",
                    "guest_email": "string",
                    "check_in": "date (YYYY-MM-DD)",
                    "check_out": "date (YYYY-MM-DD)",
                    "num_guests": "integer (>=1)",
                },
            },
            {
                "method": "GET",
                "path": "/api/reservations",
                "description": "List all reservations. Optionally filter by status.",
                "parameters": {
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


@app.get("/api/rooms", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db)):
    return db.query(RoomModel).order_by(RoomModel.room_number).all()


@app.get("/api/rooms/available", response_model=list[AvailableRoomOut])
def available_rooms(
    check_in: dt.date = Query(...),
    check_out: dt.date = Query(...),
    guests: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    if check_out <= check_in:
        raise HTTPException(400, "check_out must be after check_in")

    rooms = db.query(RoomModel)
    if guests:
        rooms = rooms.filter(RoomModel.capacity >= guests)

    result = []
    for room in rooms.order_by(RoomModel.room_number).all():
        if is_room_available(db, room.id, check_in, check_out):
            result.append(room)
    return result


@app.get("/api/pricing", response_model=PricingOut)
def get_pricing(
    room_id: int = Query(...),
    check_in: dt.date = Query(...),
    check_out: dt.date = Query(...),
    db: Session = Depends(get_db),
):
    if check_out <= check_in:
        raise HTTPException(400, "check_out must be after check_in")

    room = db.query(RoomModel).filter(RoomModel.id == room_id).first()
    if not room:
        raise HTTPException(404, "Room not found")

    total, breakdown = calculate_price(room.base_price_per_night, check_in, check_out)
    num_nights = (check_out - check_in).days

    return PricingOut(
        room_id=room.id,
        room_number=room.room_number,
        room_type=room.room_type,
        check_in=check_in,
        check_out=check_out,
        num_nights=num_nights,
        base_price_per_night=room.base_price_per_night,
        total_price=total,
        breakdown=breakdown,
    )


@app.post("/api/reservations", response_model=ReservationOut, status_code=201)
def create_reservation(data: ReservationCreate, db: Session = Depends(get_db)):
    if data.check_out <= data.check_in:
        raise HTTPException(400, "check_out must be after check_in")

    room = db.query(RoomModel).filter(RoomModel.id == data.room_id).first()
    if not room:
        raise HTTPException(404, "Room not found")

    if data.num_guests > room.capacity:
        raise HTTPException(
            400,
            f"Room {room.room_number} has a max capacity of {room.capacity} guests",
        )

    if not is_room_available(db, room.id, data.check_in, data.check_out):
        raise HTTPException(
            409,
            f"Room {room.room_number} is not available for the requested dates",
        )

    total, _ = calculate_price(room.base_price_per_night, data.check_in, data.check_out)

    reservation = ReservationModel(
        room_id=data.room_id,
        guest_name=data.guest_name,
        guest_email=data.guest_email,
        check_in=data.check_in,
        check_out=data.check_out,
        num_guests=data.num_guests,
        total_price=total,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    return ReservationOut(
        id=reservation.id,
        room_id=reservation.room_id,
        room_number=room.room_number,
        guest_name=reservation.guest_name,
        guest_email=reservation.guest_email,
        check_in=reservation.check_in,
        check_out=reservation.check_out,
        num_guests=reservation.num_guests,
        total_price=reservation.total_price,
        status=reservation.status,
        created_at=reservation.created_at,
    )


@app.get("/api/reservations", response_model=list[ReservationOut])
def list_reservations(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(ReservationModel).join(RoomModel)
    if status:
        query = query.filter(ReservationModel.status == status)

    results = []
    for r in query.order_by(ReservationModel.created_at.desc()).all():
        results.append(ReservationOut(
            id=r.id,
            room_id=r.room_id,
            room_number=r.room.room_number,
            guest_name=r.guest_name,
            guest_email=r.guest_email,
            check_in=r.check_in,
            check_out=r.check_out,
            num_guests=r.num_guests,
            total_price=r.total_price,
            status=r.status,
            created_at=r.created_at,
        ))
    return results


@app.get("/api/reservations/{reservation_id}", response_model=ReservationOut)
def get_reservation(reservation_id: int, db: Session = Depends(get_db)):
    r = db.query(ReservationModel).filter(ReservationModel.id == reservation_id).first()
    if not r:
        raise HTTPException(404, "Reservation not found")
    return ReservationOut(
        id=r.id,
        room_id=r.room_id,
        room_number=r.room.room_number,
        guest_name=r.guest_name,
        guest_email=r.guest_email,
        check_in=r.check_in,
        check_out=r.check_out,
        num_guests=r.num_guests,
        total_price=r.total_price,
        status=r.status,
        created_at=r.created_at,
    )


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

    return ReservationOut(
        id=r.id,
        room_id=r.room_id,
        room_number=r.room.room_number,
        guest_name=r.guest_name,
        guest_email=r.guest_email,
        check_in=r.check_in,
        check_out=r.check_out,
        num_guests=r.num_guests,
        total_price=r.total_price,
        status=r.status,
        created_at=r.created_at,
    )
