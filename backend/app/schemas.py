"""Pydantic request/response schemas for the REST API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class JoinRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    party_size: int = Field(ge=1, le=20)
    phone: str | None = Field(default=None, max_length=32)


class SeatRequest(BaseModel):
    table_id: int


class TableCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    capacity: int = Field(ge=1, le=20)


class TableUpdate(BaseModel):
    name: str | None = None
    capacity: int | None = Field(default=None, ge=1, le=20)
    status: str | None = Field(default=None, pattern="^(free|occupied)$")


class FaultRequest(BaseModel):
    # Either field may be set; omit a field to leave it unchanged.
    error_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    latency_ms: int | None = Field(default=None, ge=0, le=60_000)


class EntryOut(BaseModel):
    id: int
    name: str
    party_size: int
    phone: str | None
    status: str
    position: int | None
    estimated_wait_minutes: float | None


class TableOut(BaseModel):
    id: int
    name: str
    capacity: int
    status: str
