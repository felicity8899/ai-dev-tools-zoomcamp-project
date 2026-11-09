"""Unit tests for the pure waitlist domain logic (app/waitlist.py).

Fixed scenarios, no DB and no HTTP: these pin the ETA rules described in
docs/SPEC.md so a refactor cannot silently change guest-facing estimates.
"""
from app.waitlist import (
    QueueEntry,
    TableInfo,
    estimate_wait_for,
    estimate_waits,
    next_for_table,
    position_of,
)


def e(entry_id: int, size: int) -> QueueEntry:
    return QueueEntry(id=entry_id, party_size=size)


def t(table_id: int, capacity: int, free_at: float = 0.0) -> TableInfo:
    return TableInfo(id=table_id, capacity=capacity, free_at_minute=free_at)


class TestPosition:
    def test_positions_are_one_based_in_arrival_order(self):
        entries = [e(10, 2), e(11, 4), e(12, 2)]
        assert position_of(10, entries) == 1
        assert position_of(11, entries) == 2
        assert position_of(12, entries) == 3

    def test_unknown_entry_has_no_position(self):
        assert position_of(99, [e(1, 2)]) is None
        assert position_of(1, []) is None


class TestEstimateWaits:
    def test_first_party_with_free_table_waits_zero(self):
        waits = estimate_waits([e(1, 2)], [t(1, 4)], turnover_minutes=45)
        assert waits[1] == 0.0

    def test_second_party_waits_one_turnover_when_one_table(self):
        waits = estimate_waits([e(1, 2), e(2, 2)], [t(1, 4)], turnover_minutes=45)
        assert waits[1] == 0.0
        assert waits[2] == 45.0

    def test_two_free_tables_seat_first_two_immediately(self):
        waits = estimate_waits(
            [e(1, 2), e(2, 2), e(3, 2)],
            [t(1, 2), t(2, 4)],
            turnover_minutes=30,
        )
        assert waits[1] == 0.0
        assert waits[2] == 0.0
        assert waits[3] == 30.0

    def test_busy_table_delays_by_remaining_time(self):
        # Only table frees in 20 min; turnover 40 -> second party waits 60.
        waits = estimate_waits(
            [e(1, 2), e(2, 2)], [t(1, 4, free_at=20.0)], turnover_minutes=40
        )
        assert waits[1] == 20.0
        assert waits[2] == 60.0

    def test_party_too_big_for_every_table_gets_none(self):
        waits = estimate_waits([e(1, 8)], [t(1, 4), t(2, 6)], turnover_minutes=45)
        assert waits[1] is None

    def test_big_party_does_not_block_small_party_behind_it(self):
        # Party of 6 takes the 6-top; party of 2 behind it takes the 2-top.
        entries = [e(1, 6), e(2, 2)]
        tables = [t(1, 2), t(2, 6)]
        waits = estimate_waits(entries, tables, turnover_minutes=45)
        assert waits[1] == 0.0
        assert waits[2] == 0.0

    def test_small_tables_preferred_so_big_table_stays_free(self):
        # Party of 2 must take the 2-top (not the 6-top), so the party of 6
        # behind it still seats immediately.
        entries = [e(1, 2), e(2, 6)]
        tables = [t(1, 6), t(2, 2)]  # big table listed first on purpose
        waits = estimate_waits(entries, tables, turnover_minutes=45)
        assert waits[1] == 0.0
        assert waits[2] == 0.0

    def test_estimate_wait_for_matches_bulk(self):
        entries = [e(1, 2), e(2, 2)]
        tables = [t(1, 4)]
        assert estimate_wait_for(2, entries, tables, 45) == 45.0
        assert estimate_wait_for(99, entries, tables, 45) is None


class TestNextForTable:
    def test_skips_parties_that_do_not_fit(self):
        entries = [e(1, 6), e(2, 2)]
        assert next_for_table(entries, table_capacity=4).id == 2

    def test_returns_none_when_nobody_fits(self):
        assert next_for_table([e(1, 6)], table_capacity=4) is None
        assert next_for_table([], table_capacity=4) is None
