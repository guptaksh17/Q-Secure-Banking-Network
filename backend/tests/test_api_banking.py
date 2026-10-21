import pytest

TRANSFER = {"sender_account": "QSB-A-1001", "receiver_account": "QSB-B-2001",
            "amount": "250.00", "currency": "USD", "memo": "test"}


def _post(client, seed, **sim):
    return client.post("/api/transfers", json={**TRANSFER, "simulation": {"seed": seed, **sim}})


def test_banks_listed(client):
    banks = client.get("/api/banks").json()
    assert [b["code"] for b in banks] == ["bank_a", "bank_b"]
    assert banks[0]["example_accounts"][0] == "QSB-A-1001"


def test_create_and_fetch_transfer(client):
    r = _post(client, 1)
    assert r.status_code == 201
    body = r.json()
    t = body["transaction"]
    assert t["status"] == "delivered" and t["amount"] == "250.00"
    assert t["encryption"]["algorithm"] == "AES-256-GCM" and len(t["encryption"]["auth_tag"]) == 32
    assert body["qkd_session"]["accepted"] and body["qkd_session"]["key_id"] == t["key_id"]
    assert [e["event_type"] for e in body["events"]][-1] == "transaction_delivered"
    assert t["created_at"].endswith("Z")

    again = client.get(f"/api/transfers/{t['id']}").json()
    assert again["transaction"] == t


def test_blocked_transfer_via_api(client):
    t = _post(client, 2, eve_probability=1.0).json()["transaction"]
    assert t["status"] == "blocked" and t["encryption"]["ciphertext"] is None


def test_tampered_transfer_via_api(client):
    t = _post(client, 3, tamper="ciphertext").json()["transaction"]
    assert t["status"] == "rejected" and t["tag_verified"] is False


@pytest.mark.parametrize("override", [
    {"sender_account": "1234567890"}, {"receiver_account": "QSB-A-2001"},
    {"amount": "0.001"}, {"currency": "BTC"}, {"memo": "x" * 141},
])
def test_invalid_transfers_rejected(client, override):
    assert client.post("/api/transfers", json={**TRANSFER, **override}).status_code == 422


@pytest.mark.parametrize("sim", [{"n_qubits": 100}, {"eve_probability": 2}, {"tamper": "bogus"}])
def test_invalid_simulation_options_rejected(client, sim):
    assert client.post("/api/transfers", json={**TRANSFER, "simulation": sim}).status_code == 422


def test_list_filter_and_paginate(client):
    _post(client, 10)
    _post(client, 11, eve_probability=1.0)
    _post(client, 12)
    all_ = client.get("/api/transfers").json()
    assert all_["total"] == 3
    assert client.get("/api/transfers?status=delivered").json()["total"] == 2
    assert client.get("/api/transfers?status=blocked").json()["total"] == 1
    page = client.get("/api/transfers?limit=2&offset=2").json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert "encryption" not in all_["items"][0]  # list view is summary only


def test_missing_resources_404(client):
    assert client.get("/api/transfers/nope").status_code == 404
    assert client.get("/api/qkd/sessions/nope").status_code == 404
    assert client.get("/api/experiments/nope").status_code == 404


def test_sessions_and_events_history(client):
    _post(client, 20)
    _post(client, 21, eve_probability=1.0)
    client.post("/api/qkd/key-exchange", json={"seed": 22})
    sessions = client.get("/api/qkd/sessions").json()
    assert sessions["total"] == 3
    assert client.get("/api/qkd/sessions?purpose=lab").json()["total"] == 1
    assert client.get("/api/qkd/sessions?accepted=false").json()["total"] == 1
    sid = sessions["items"][0]["id"]
    assert "metrics" in client.get(f"/api/qkd/sessions/{sid}").json()

    crit = client.get("/api/security-events?severity=critical").json()
    assert crit["total"] == 1 and crit["items"][0]["event_type"] == "high_qber_detected"
    typed = client.get("/api/security-events?event_type=transaction_delivered").json()
    assert typed["total"] == 1


def test_dashboard_summary(client):
    _post(client, 30)
    _post(client, 31, eve_probability=1.0)
    _post(client, 32, tamper="tag")
    s = client.get("/api/dashboard/summary").json()
    assert s["transactions"]["total"] == 3
    assert s["transactions"]["by_status"]["delivered"] == 1
    assert s["transactions"]["by_status"]["blocked"] == 1
    assert s["transactions"]["by_status"]["rejected"] == 1
    assert s["qkd_sessions"]["acceptance_rate"] == pytest.approx(2 / 3)
    assert s["security_events"]["critical"] == 2
    assert len(s["recent_events"]) == 10


def test_empty_dashboard(client):
    s = client.get("/api/dashboard/summary").json()
    assert s["transactions"]["total"] == 0 and s["qkd_sessions"]["acceptance_rate"] is None


def test_lab_key_exchange_is_persisted(client):
    body = client.post("/api/qkd/key-exchange", json={"seed": 40}).json()
    s = client.get(f"/api/qkd/sessions/{body['session_id']}").json()
    assert s["purpose"] == "lab" and s["accepted"]
