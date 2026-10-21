import pytest


def test_run_store_and_fetch_channel_sweep(client):
    r = client.post("/api/experiments", json={
        "name": "eve-vs-qber", "kind": "channel_sweep", "parameter": "eve_probability",
        "values": [0, 0.5, 1], "n_qubits": 2048, "trials": 5, "seed": 7,
    })
    assert r.status_code == 201
    body = r.json()
    assert body["n_points"] == 3 and body["config"]["seed"] == 7
    assert body["points"][2]["expected_qber"] == 0.25

    listed = client.get("/api/experiments").json()
    assert listed["total"] == 1 and "points" not in listed["items"][0]
    again = client.get(f"/api/experiments/{body['id']}").json()
    assert again["points"] == body["points"]


def test_stored_experiment_is_reproducible(client):
    payload = {"name": "rep", "kind": "channel_sweep", "parameter": "noise",
               "values": [0.1], "n_qubits": 1024, "trials": 3, "seed": 1}
    a = client.post("/api/experiments", json=payload).json()["points"]
    b = client.post("/api/experiments", json=payload).json()["points"]
    assert a == b


def test_key_exchange_sweep_via_api(client):
    body = client.post("/api/experiments", json={
        "name": "acceptance", "kind": "key_exchange_sweep", "parameter": "eve_probability",
        "values": [0, 1], "n_qubits": 4096, "trials": 3, "seed": 3,
    }).json()
    assert [p["acceptance_rate"] for p in body["points"]] == [1.0, 0.0]


@pytest.mark.parametrize("override", [
    {"values": []},
    {"values": [1.5]},
    {"kind": "key_exchange_sweep", "parameter": "n_qubits", "values": [1024]},
    {"parameter": "n_qubits", "values": [100]},
    {"trials": 51},
    {"values": [0.1] * 21, "trials": 50, "n_qubits": 32_768},  # too much work
    {"name": ""},
])
def test_bad_experiment_requests_rejected(client, override):
    payload = {"name": "x", "kind": "channel_sweep", "parameter": "noise", "values": [0.1], **override}
    assert client.post("/api/experiments", json=payload).status_code == 422
