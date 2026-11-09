"""TableNow backend — FastAPI app.

REST API + WebSocket live updates for the restaurant waitlist, an admin
surface for health detail and fault injection (chaos demo), Prometheus
/metrics for the join journey, and optional OTEL tracing.
"""
from __future__ import annotations

import asyncio
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import config, waitlist as domain
from .database import Base, SessionLocal, engine, get_db
from .faults import FAULTS
from .models import Table, WaitlistEntry
from .observability import (
    JOIN_LATENCY,
    JOIN_REQUESTS,
    QUEUE_LENGTH,
    get_logger,
    setup_logging,
    setup_tracing,
)
from .schemas import (
    EntryOut,
    FaultRequest,
    JoinRequest,
    SeatRequest,
    TableCreate,
    TableOut,
    TableUpdate,
)
from .seed import seed_if_empty

log = get_logger("tablenow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    log.info("tablenow backend started", extra={"trace_id": "-"})
    yield


app = FastAPI(title="TableNow API", version="1.0.0", lifespan=lifespan)
setup_logging()
setup_tracing(app)


# --- WebSocket live updates ----------------------------------------------------

class ConnectionManager:
    """Tracks dashboard sockets and broadcasts queue snapshots on change."""

    def __init__(self) -> None:
        self.active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


# --- Queue helpers ---------------------------------------------------------------

def _waiting(db: Session) -> list[WaitlistEntry]:
    return (
        db.query(WaitlistEntry)
        .filter(WaitlistEntry.status == "waiting")
        .order_by(WaitlistEntry.joined_at, WaitlistEntry.id)
        .all()
    )


def _table_infos(db: Session) -> list[domain.TableInfo]:
    """Domain view of tables: free now, or minutes until the seating ends."""
    now = datetime.now(timezone.utc)
    infos = []
    for table in db.query(Table).all():
        free_at = 0.0
        if table.status == "occupied":
            seated = (
                db.query(WaitlistEntry)
                .filter(
                    WaitlistEntry.table_id == table.id,
                    WaitlistEntry.status == "seated",
                )
                .order_by(WaitlistEntry.seated_at.desc())
                .first()
            )
            if seated and seated.seated_at is not None:
                seated_at = seated.seated_at
                if seated_at.tzinfo is None:  # SQLite returns naive datetimes
                    seated_at = seated_at.replace(tzinfo=timezone.utc)
                elapsed = (now - seated_at).total_seconds() / 60.0
                free_at = max(0.0, config.AVG_TURNOVER_MINUTES - elapsed)
        infos.append(
            domain.TableInfo(id=table.id, capacity=table.capacity, free_at_minute=free_at)
        )
    return infos


def queue_payload(db: Session) -> dict:
    entries = _waiting(db)
    queue_entries = [domain.QueueEntry(id=e.id, party_size=e.party_size) for e in entries]
    waits = domain.estimate_waits(
        queue_entries, _table_infos(db), config.AVG_TURNOVER_MINUTES
    )
    QUEUE_LENGTH.set(len(entries))
    return {
        "type": "queue",
        "entries": [
            EntryOut(
                id=e.id,
                name=e.name,
                party_size=e.party_size,
                phone=e.phone,
                status=e.status,
                position=domain.position_of(e.id, queue_entries),
                estimated_wait_minutes=(
                    round(waits[e.id], 1) if waits.get(e.id) is not None else None
                ),
            ).model_dump()
            for e in entries
        ],
        "tables": [
            TableOut(id=t.id, name=t.name, capacity=t.capacity, status=t.status).model_dump()
            for t in db.query(Table).order_by(Table.id).all()
        ],
    }


async def _broadcast_queue() -> None:
    db = SessionLocal()
    try:
        await manager.broadcast(queue_payload(db))
    finally:
        db.close()


# --- Waitlist API ------------------------------------------------------------------

@app.post("/api/waitlist", status_code=201)
async def join_waitlist(body: JoinRequest, db: Session = Depends(get_db)):
    """THE instrumented journey: guest joins the waitlist.

    Fault injection hooks live here (error rate / latency) so the chaos demo
    degrades exactly this journey and nothing else.
    """
    started = time.perf_counter()
    result = "success"
    try:
        if FAULTS.latency_ms > 0:
            await asyncio.sleep(FAULTS.latency_ms / 1000.0)
        if FAULTS.error_rate > 0 and random.random() < FAULTS.error_rate:
            result = "error"
            log.warning("join failed: injected error fault")
            raise HTTPException(status_code=503, detail="join temporarily unavailable")

        entry = WaitlistEntry(
            name=body.name, party_size=body.party_size, phone=body.phone, status="waiting"
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        payload = queue_payload(db)
        mine = next(e for e in payload["entries"] if e["id"] == entry.id)
        log.info(
            "guest joined waitlist",
            extra={"trace_id": "-"},  # formatter replaces with span trace id
        )
        await manager.broadcast(payload)
        return mine
    finally:
        elapsed = time.perf_counter() - started
        JOIN_REQUESTS.labels(result=result).inc()
        JOIN_LATENCY.labels(result=result).observe(elapsed)


@app.get("/api/waitlist")
def list_waitlist(db: Session = Depends(get_db)):
    return queue_payload(db)["entries"]


@app.post("/api/waitlist/{entry_id}/seat")
async def seat_party(entry_id: int, body: SeatRequest, db: Session = Depends(get_db)):
    entry = db.get(WaitlistEntry, entry_id)
    if entry is None or entry.status != "waiting":
        raise HTTPException(status_code=404, detail="waiting entry not found")
    table = db.get(Table, body.table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="table not found")
    if table.status != "free":
        raise HTTPException(status_code=409, detail="table is not free")
    if entry.party_size > table.capacity:
        raise HTTPException(status_code=422, detail="party does not fit this table")

    entry.status = "seated"
    entry.seated_at = datetime.now(timezone.utc)
    entry.table_id = table.id
    table.status = "occupied"
    db.commit()
    log.info(f"seated entry {entry.id} at table {table.id}")
    await _broadcast_queue()
    return {"ok": True, "entry_id": entry.id, "table_id": table.id}


def _remove_from_queue(entry_id: int, new_status: str, db: Session) -> dict:
    entry = db.get(WaitlistEntry, entry_id)
    if entry is None or entry.status != "waiting":
        raise HTTPException(status_code=404, detail="waiting entry not found")
    entry.status = new_status
    db.commit()
    log.info(f"entry {entry_id} marked {new_status}")
    return {"ok": True, "entry_id": entry_id, "status": new_status}


@app.post("/api/waitlist/{entry_id}/no-show")
async def mark_no_show(entry_id: int, db: Session = Depends(get_db)):
    result = _remove_from_queue(entry_id, "no_show", db)
    await _broadcast_queue()
    return result


@app.post("/api/waitlist/{entry_id}/left")
async def mark_left(entry_id: int, db: Session = Depends(get_db)):
    result = _remove_from_queue(entry_id, "left", db)
    await _broadcast_queue()
    return result


# --- Tables API (CRUD-lite) --------------------------------------------------------

@app.get("/api/tables")
def list_tables(db: Session = Depends(get_db)):
    return [
        TableOut(id=t.id, name=t.name, capacity=t.capacity, status=t.status).model_dump()
        for t in db.query(Table).order_by(Table.id).all()
    ]


@app.post("/api/tables", status_code=201)
async def create_table(body: TableCreate, db: Session = Depends(get_db)):
    table = Table(name=body.name, capacity=body.capacity, status="free")
    db.add(table)
    db.commit()
    db.refresh(table)
    await _broadcast_queue()
    return TableOut(
        id=table.id, name=table.name, capacity=table.capacity, status=table.status
    ).model_dump()


@app.patch("/api/tables/{table_id}")
async def update_table(table_id: int, body: TableUpdate, db: Session = Depends(get_db)):
    table = db.get(Table, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="table not found")
    if body.name is not None:
        table.name = body.name
    if body.capacity is not None:
        table.capacity = body.capacity
    if body.status is not None:
        table.status = body.status
        if body.status == "free":
            # Freeing a table closes out its seated party.
            seated = (
                db.query(WaitlistEntry)
                .filter(
                    WaitlistEntry.table_id == table.id,
                    WaitlistEntry.status == "seated",
                )
                .all()
            )
            for entry in seated:
                entry.status = "left"
    db.commit()
    await _broadcast_queue()
    return TableOut(
        id=table.id, name=table.name, capacity=table.capacity, status=table.status
    ).model_dump()


# --- Health, metrics, admin ---------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/admin/health/detail")
def health_detail(db: Session = Depends(get_db)):
    """Deep health for the responder agent: DB, broadcaster, active faults."""
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    faults = FAULTS.active_faults()
    return {
        "status": "ok" if db_ok and not faults else "degraded",
        "db_ok": db_ok,
        "websocket_clients": len(manager.active),
        "active_faults": faults,
        "journey": "join_waitlist",
    }


@app.get("/admin/faults")
def get_faults():
    return {"active_faults": FAULTS.active_faults()}


@app.post("/admin/faults")
def set_fault(body: FaultRequest):
    """Inject a fault on the join journey (chaos demo — see RUNBOOK)."""
    FAULTS.set(error_rate=body.error_rate, latency_ms=body.latency_ms)
    log.warning(f"fault injected: {FAULTS.active_faults()}")
    return {"active_faults": FAULTS.active_faults()}


@app.post("/admin/faults/reset")
def reset_faults():
    FAULTS.reset()
    log.info("all faults reset")
    return {"active_faults": []}


# --- WebSocket -----------------------------------------------------------------------

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, db: Session = Depends(get_db)):
    await manager.connect(ws)
    try:
        await ws.send_json(queue_payload(db))
        while True:
            await ws.receive_text()  # keep-alive; clients just listen
    except WebSocketDisconnect:
        manager.disconnect(ws)


# --- Demo mode: serve the SPA from the backend (single container) --------------------

if config.STATIC_DIR:
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
