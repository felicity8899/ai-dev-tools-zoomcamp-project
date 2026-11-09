"""Database models. Deliberately portable: no Postgres-only column types, so
the identical schema runs on PostgreSQL 16 (compose) and SQLite (tests/demo).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Table(Base):
    __tablename__ = "tables"

    id = Column(Integer, primary_key=True)
    name = Column(String(40), nullable=False)
    capacity = Column(Integer, nullable=False)
    # "free" | "occupied"
    status = Column(String(16), nullable=False, default="free")


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    party_size = Column(Integer, nullable=False)
    phone = Column(String(32), nullable=True)
    # "waiting" | "seated" | "no_show" | "left"
    status = Column(String(16), nullable=False, default="waiting")
    joined_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    seated_at = Column(DateTime(timezone=True), nullable=True)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True)
