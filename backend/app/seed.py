"""Demo seed data: a small dining room plus two parties already waiting.

Runs on boot only when the tables table is empty, so restarts keep state
(seating must persist across restarts — see docs/SPEC.md).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Table, WaitlistEntry

SEED_TABLES = [
    ("T1", 2),
    ("T2", 2),
    ("T3", 4),
    ("T4", 4),
    ("T5", 6),
]

SEED_QUEUE = [
    ("Ada", 2),
    ("Ben", 4),
]


def seed_if_empty(db: Session) -> None:
    if db.query(Table).count() > 0:
        return
    for name, capacity in SEED_TABLES:
        db.add(Table(name=name, capacity=capacity, status="free"))
    db.flush()
    for name, size in SEED_QUEUE:
        db.add(WaitlistEntry(name=name, party_size=size, status="waiting"))
    db.commit()
