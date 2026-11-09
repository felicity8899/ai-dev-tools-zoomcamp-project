"""Pure waitlist domain logic.

Everything in this module is a pure function over plain data classes: no HTTP,
no database, no clocks (callers pass "minutes from now" explicitly). That makes
the position / ETA rules unit-testable against fixed scenarios, which is an
explicit acceptance criterion in docs/SPEC.md.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueueEntry:
    """A party waiting to be seated, in arrival order."""

    id: int
    party_size: int


@dataclass(frozen=True)
class TableInfo:
    """A table that could seat a waiting party.

    ``free_at_minute`` is how many minutes from *now* the table next becomes
    free: 0.0 for a table that is free right now, otherwise the remaining
    minutes of the current seating (turnover - elapsed).
    """

    id: int
    capacity: int
    free_at_minute: float = 0.0


def position_of(entry_id: int, entries: list[QueueEntry]) -> int | None:
    """1-based position of ``entry_id`` in the queue, or None if not waiting."""
    for index, entry in enumerate(entries, start=1):
        if entry.id == entry_id:
            return index
    return None


def estimate_waits(
    entries: list[QueueEntry],
    tables: list[TableInfo],
    turnover_minutes: float = 45.0,
) -> dict[int, float | None]:
    """Estimated wait (minutes from now) for every waiting entry.

    Simulation: walk the queue in arrival order. Each party takes the
    earliest-freeing table that can hold it (ties broken by smallest fitting
    capacity, so big tables stay available for big parties). Seating a party
    pushes that table's next-free time out by one turnover. A party's wait is
    the free-at time of the table it is assigned; a party larger than every
    table gets ``None`` (can never be seated).
    """
    free_at = {t.id: float(t.free_at_minute) for t in tables}
    capacity = {t.id: t.capacity for t in tables}
    waits: dict[int, float | None] = {}
    for entry in entries:
        fitting = [tid for tid, cap in capacity.items() if cap >= entry.party_size]
        if not fitting:
            waits[entry.id] = None
            continue
        chosen = min(fitting, key=lambda tid: (free_at[tid], capacity[tid]))
        waits[entry.id] = max(0.0, free_at[chosen])
        free_at[chosen] += turnover_minutes
    return waits


def estimate_wait_for(
    entry_id: int,
    entries: list[QueueEntry],
    tables: list[TableInfo],
    turnover_minutes: float = 45.0,
) -> float | None:
    """Estimated wait for one entry (None if absent or unseatable)."""
    return estimate_waits(entries, tables, turnover_minutes).get(entry_id)


def next_for_table(
    entries: list[QueueEntry], table_capacity: int
) -> QueueEntry | None:
    """Next party in line that fits a table of ``table_capacity`` seats."""
    for entry in entries:
        if entry.party_size <= table_capacity:
            return entry
    return None
