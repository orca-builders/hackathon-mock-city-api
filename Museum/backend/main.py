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

DATABASE_URL = "sqlite:///./museum.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

TICKET_TYPES = ["adult", "child", "senior", "student"]
TICKET_PRICES = {
    "adult": 25.0,
    "child": 12.0,
    "senior": 18.0,
    "student": 15.0,
}


class Base(DeclarativeBase):
    pass


class TimeSlotModel(Base):
    __tablename__ = "time_slots"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    max_visitors = Column(Integer, nullable=False)

    tickets = relationship("TicketModel", back_populates="time_slot")


class TicketModel(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    time_slot_id = Column(Integer, ForeignKey("time_slots.id"), nullable=False)
    visit_date = Column(Date, nullable=False)
    visitor_name = Column(String, nullable=False)
    visitor_email = Column(String, nullable=False)
    num_visitors = Column(Integer, nullable=False)
    ticket_type = Column(String, nullable=False)
    total_price = Column(Float, nullable=False)
    status = Column(String, default="confirmed")  # confirmed / cancelled
    created_at = Column(DateTime, server_default=func.now())

    time_slot = relationship("TimeSlotModel", back_populates="tickets")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TimeSlotOut(BaseModel):
    id: int
    label: str
    start_time: str
    end_time: str
    max_visitors: int

    model_config = {"from_attributes": True}


class TicketCreate(BaseModel):
    time_slot_id: int
    visit_date: dt.date
    visitor_name: str
    visitor_email: str
    num_visitors: int = Field(ge=1)
    ticket_type: str = "adult"


class TicketOut(BaseModel):
    id: int
    time_slot_id: int
    time_slot_label: str | None = None
    visit_date: dt.date
    visitor_name: str
    visitor_email: str
    num_visitors: int
    ticket_type: str
    total_price: float
    status: str
    created_at: dt.datetime | None = None

    model_config = {"from_attributes": True}


class SlotAvailability(BaseModel):
    time_slot_id: int
    label: str
    start_time: str
    end_time: str
    max_visitors: int
    booked_visitors: int
    remaining_spots: int
    available: bool


class PricingOut(BaseModel):
    ticket_type: str
    price_per_person: float
    num_visitors: int
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


def get_booked_visitors(db: Session, time_slot_id: int, visit_date: dt.date) -> int:
    result = db.query(func.coalesce(func.sum(TicketModel.num_visitors), 0)).filter(
        TicketModel.time_slot_id == time_slot_id,
        TicketModel.visit_date == visit_date,
        TicketModel.status == "confirmed",
    ).scalar()
    return int(result)


def ticket_to_out(t: TicketModel) -> TicketOut:
    return TicketOut(
        id=t.id,
        time_slot_id=t.time_slot_id,
        time_slot_label=t.time_slot.label,
        visit_date=t.visit_date,
        visitor_name=t.visitor_name,
        visitor_email=t.visitor_email,
        num_visitors=t.num_visitors,
        ticket_type=t.ticket_type,
        total_price=t.total_price,
        status=t.status,
        created_at=t.created_at,
    )


SEED_TIME_SLOTS = [
    ("09:00-11:00", "09:00", "11:00", 50),
    ("11:00-13:00", "11:00", "13:00", 50),
    ("13:00-15:00", "13:00", "15:00", 50),
    ("15:00-17:00", "15:00", "17:00", 50),
]


def seed_db():
    db = SessionLocal()
    if db.query(TimeSlotModel).count() == 0:
        for label, start, end, cap in SEED_TIME_SLOTS:
            db.add(TimeSlotModel(
                label=label, start_time=start, end_time=end, max_visitors=cap,
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
    title="Museum Ticket API",
    description=(
        "A simple museum ticket booking API designed for LLM / AI-agent consumption. "
        "Check time-slot availability, get pricing by ticket type, and book visits."
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
        "service": "Museum Ticket Booking API",
        "base_url": "/api",
        "ticket_types": TICKET_TYPES,
        "ticket_prices": TICKET_PRICES,
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/time-slots",
                "description": "List all museum time slots with their visitor capacity.",
            },
            {
                "method": "GET",
                "path": "/api/availability",
                "description": "Check visitor availability for a given date. Returns remaining spots per time slot. Optionally check a specific slot and party size.",
                "parameters": {
                    "date": "date (YYYY-MM-DD) — required",
                    "time_slot_id": "integer — optional, check a specific slot",
                    "visitors": "integer — optional, check if this many spots are available",
                },
            },
            {
                "method": "GET",
                "path": "/api/pricing",
                "description": "Get a price quote by ticket type and number of visitors.",
                "parameters": {
                    "ticket_type": f"string — optional, one of: {', '.join(TICKET_TYPES)} (default: adult)",
                    "visitors": "integer — optional (default: 1)",
                },
            },
            {
                "method": "GET",
                "path": "/api/ticket-types",
                "description": "List all ticket types with their per-person prices.",
            },
            {
                "method": "POST",
                "path": "/api/tickets",
                "description": "Book museum tickets for a specific date and time slot.",
                "body": {
                    "time_slot_id": "integer",
                    "visit_date": "date (YYYY-MM-DD)",
                    "visitor_name": "string",
                    "visitor_email": "string",
                    "num_visitors": "integer (>=1)",
                    "ticket_type": f"string (one of: {', '.join(TICKET_TYPES)}, default: adult)",
                },
            },
            {
                "method": "GET",
                "path": "/api/tickets",
                "description": "List all tickets. Optionally filter by date or status.",
                "parameters": {
                    "date": "date (YYYY-MM-DD) — optional",
                    "status": "string — optional (confirmed / cancelled)",
                },
            },
            {
                "method": "GET",
                "path": "/api/tickets/{id}",
                "description": "Get details of a specific ticket by ID.",
            },
            {
                "method": "DELETE",
                "path": "/api/tickets/{id}",
                "description": "Cancel a ticket by ID. Sets status to 'cancelled' and frees up spots.",
            },
        ],
    }


@app.get("/api/time-slots", response_model=list[TimeSlotOut])
def list_time_slots(db: Session = Depends(get_db)):
    return db.query(TimeSlotModel).order_by(TimeSlotModel.start_time).all()


@app.get("/api/ticket-types")
def list_ticket_types():
    return [
        {"type": t, "price_per_person": p}
        for t, p in TICKET_PRICES.items()
    ]


@app.get("/api/availability", response_model=list[SlotAvailability] | SlotAvailability)
def check_availability(
    date: dt.date = Query(...),
    time_slot_id: Optional[int] = Query(None),
    visitors: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    if time_slot_id:
        slot = db.query(TimeSlotModel).filter(TimeSlotModel.id == time_slot_id).first()
        if not slot:
            raise HTTPException(404, "Time slot not found")
        booked = get_booked_visitors(db, slot.id, date)
        remaining = slot.max_visitors - booked
        return SlotAvailability(
            time_slot_id=slot.id,
            label=slot.label,
            start_time=slot.start_time,
            end_time=slot.end_time,
            max_visitors=slot.max_visitors,
            booked_visitors=booked,
            remaining_spots=remaining,
            available=remaining >= (visitors or 1),
        )

    slots = db.query(TimeSlotModel).order_by(TimeSlotModel.start_time).all()
    result = []
    for slot in slots:
        booked = get_booked_visitors(db, slot.id, date)
        remaining = slot.max_visitors - booked
        result.append(SlotAvailability(
            time_slot_id=slot.id,
            label=slot.label,
            start_time=slot.start_time,
            end_time=slot.end_time,
            max_visitors=slot.max_visitors,
            booked_visitors=booked,
            remaining_spots=remaining,
            available=remaining >= (visitors or 1),
        ))
    return result


@app.get("/api/pricing", response_model=PricingOut)
def get_pricing(
    ticket_type: str = Query("adult"),
    visitors: int = Query(1, ge=1),
):
    if ticket_type not in TICKET_PRICES:
        raise HTTPException(400, f"Invalid ticket_type. Must be one of: {', '.join(TICKET_TYPES)}")

    price = TICKET_PRICES[ticket_type]
    total = round(price * visitors, 2)

    return PricingOut(
        ticket_type=ticket_type,
        price_per_person=price,
        num_visitors=visitors,
        total_price=total,
    )


@app.post("/api/tickets", response_model=TicketOut, status_code=201)
def create_ticket(data: TicketCreate, db: Session = Depends(get_db)):
    if data.ticket_type not in TICKET_PRICES:
        raise HTTPException(400, f"Invalid ticket_type. Must be one of: {', '.join(TICKET_TYPES)}")

    slot = db.query(TimeSlotModel).filter(TimeSlotModel.id == data.time_slot_id).first()
    if not slot:
        raise HTTPException(404, "Time slot not found")

    booked = get_booked_visitors(db, slot.id, data.visit_date)
    remaining = slot.max_visitors - booked
    if data.num_visitors > remaining:
        raise HTTPException(
            409,
            f"Time slot {slot.label} on {data.visit_date} only has {remaining} spots remaining "
            f"(max {slot.max_visitors}), but {data.num_visitors} requested",
        )

    price = TICKET_PRICES[data.ticket_type]
    total = round(price * data.num_visitors, 2)

    ticket = TicketModel(
        time_slot_id=data.time_slot_id,
        visit_date=data.visit_date,
        visitor_name=data.visitor_name,
        visitor_email=data.visitor_email,
        num_visitors=data.num_visitors,
        ticket_type=data.ticket_type,
        total_price=total,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return ticket_to_out(ticket)


@app.get("/api/tickets", response_model=list[TicketOut])
def list_tickets(
    date: Optional[dt.date] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(TicketModel).join(TimeSlotModel)
    if date:
        query = query.filter(TicketModel.visit_date == date)
    if status:
        query = query.filter(TicketModel.status == status)
    return [ticket_to_out(t) for t in query.order_by(TicketModel.created_at.desc()).all()]


@app.get("/api/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    t = db.query(TicketModel).filter(TicketModel.id == ticket_id).first()
    if not t:
        raise HTTPException(404, "Ticket not found")
    return ticket_to_out(t)


@app.delete("/api/tickets/{ticket_id}", response_model=TicketOut)
def cancel_ticket(ticket_id: int, db: Session = Depends(get_db)):
    t = db.query(TicketModel).filter(TicketModel.id == ticket_id).first()
    if not t:
        raise HTTPException(404, "Ticket not found")
    if t.status == "cancelled":
        raise HTTPException(400, "Ticket is already cancelled")

    t.status = "cancelled"
    db.commit()
    db.refresh(t)

    return ticket_to_out(t)


if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
