"""Integration tests: the real FastAPI app over a temp SQLite database.

Covers the three core journeys (join -> seat -> queue advances), queue
removals, table CRUD-lite, metrics, and the admin fault-injection surface.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # context manager runs lifespan (create + seed)
        yield c


def _join(client, name, size=2):
    resp = client.post("/api/waitlist", json={"name": name, "party_size": size})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_seed_data_present(client):
    tables = client.get("/api/tables").json()
    assert len(tables) >= 5
    queue = client.get("/api/waitlist").json()
    assert [q["name"] for q in queue] == ["Ada", "Ben"]  # seed queue, in order
    assert queue[0]["position"] == 1
    assert queue[0]["estimated_wait_minutes"] == 0.0


def test_join_appears_in_queue_with_position_and_eta(client):
    entry = _join(client, "Cara", size=2)
    assert entry["position"] == 3
    assert entry["estimated_wait_minutes"] is not None
    queue = client.get("/api/waitlist").json()
    assert any(q["id"] == entry["id"] for q in queue)


def test_seat_party_advances_queue(client):
    queue = client.get("/api/waitlist").json()
    first, second = queue[0], queue[1]
    free_table = next(t for t in client.get("/api/tables").json() if t["status"] == "free")

    resp = client.post(
        f"/api/waitlist/{first['id']}/seat", json={"table_id": free_table["id"]}
    )
    assert resp.status_code == 200, resp.text

    queue_after = client.get("/api/waitlist").json()
    assert all(q["id"] != first["id"] for q in queue_after)
    assert queue_after[0]["id"] == second["id"]
    assert queue_after[0]["position"] == 1
    tables = {t["id"]: t for t in client.get("/api/tables").json()}
    assert tables[free_table["id"]]["status"] == "occupied"


def test_seating_persists_in_database(client):
    # A fresh request reads from the DB, not memory: seated party stays gone.
    queue = client.get("/api/waitlist").json()
    assert all(q["name"] != "Ada" for q in queue)


def test_no_show_and_left_remove_from_queue(client):
    e1 = _join(client, "NoShow Ned")
    e2 = _join(client, "Leaving Lena")
    assert client.post(f"/api/waitlist/{e1['id']}/no-show").status_code == 200
    assert client.post(f"/api/waitlist/{e2['id']}/left").status_code == 200
    ids = [q["id"] for q in client.get("/api/waitlist").json()]
    assert e1["id"] not in ids and e2["id"] not in ids


def test_table_crud_lite(client):
    created = client.post("/api/tables", json={"name": "Patio 1", "capacity": 3})
    assert created.status_code == 201
    table = created.json()
    updated = client.patch(f"/api/tables/{table['id']}", json={"capacity": 5})
    assert updated.json()["capacity"] == 5


def test_join_rejects_bad_party_size(client):
    resp = client.post("/api/waitlist", json={"name": "Zero", "party_size": 0})
    assert resp.status_code == 422


def test_metrics_expose_join_journey(client):
    _join(client, "Metrics Mia")
    body = client.get("/metrics").text
    assert "tablenow_join_requests_total" in body
    assert 'result="success"' in body
    assert "tablenow_join_latency_seconds" in body
    assert "tablenow_queue_length" in body


def test_fault_injection_breaks_and_reset_fixes_join(client):
    client.post("/admin/faults/reset")
    injected = client.post("/admin/faults", json={"error_rate": 1.0})
    assert injected.json()["active_faults"] == [
        {"type": "join_error_rate", "error_rate": 1.0}
    ]
    detail = client.get("/admin/health/detail").json()
    assert detail["status"] == "degraded"
    assert detail["db_ok"] is True

    resp = client.post("/api/waitlist", json={"name": "Unlucky", "party_size": 2})
    assert resp.status_code == 503

    client.post("/admin/faults/reset")
    assert client.get("/admin/health/detail").json()["status"] == "ok"
    ok = client.post("/api/waitlist", json={"name": "Lucky", "party_size": 2})
    assert ok.status_code == 201
    client.post(f"/api/waitlist/{ok.json()['id']}/left")  # tidy up


def test_latency_fault_is_reported_and_resettable(client):
    client.post("/admin/faults", json={"latency_ms": 50})
    faults = client.get("/admin/faults").json()["active_faults"]
    assert {"type": "join_latency", "latency_ms": 50} in faults
    client.post("/admin/faults/reset")
    assert client.get("/admin/faults").json()["active_faults"] == []
