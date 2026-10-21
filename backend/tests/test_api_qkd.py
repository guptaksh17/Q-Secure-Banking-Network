import pytest


def test_bb84_lab_run_defaults(client):
    r = client.post("/api/qkd/bb84", json={"n_qubits": 1024, "seed": 1})
    assert r.status_code == 200
    body = r.json()
    m = body["metrics"]
    assert m["n_qubits"] == 1024
    assert m["true_sifted_errors"] == 0
    assert m["backend"] == "numpy"
    assert len(body["trace"]) == 16


def test_bb84_lab_run_is_reproducible(client):
    payload = {"n_qubits": 512, "seed": 42, "trace_length": 8}
    assert client.post("/api/qkd/bb84", json=payload).json() == \
        client.post("/api/qkd/bb84", json=payload).json()


def test_bb84_lab_never_returns_full_keys(client):
    body = client.post("/api/qkd/bb84", json={"n_qubits": 4096, "trace_length": 64}).json()
    assert len(body["trace"]) == 64
    flat = str(body).lower()
    for forbidden in ("alice_key", "bob_key", "sifted_key'", "raw_key", "final_key"):
        assert forbidden not in flat


@pytest.mark.parametrize("payload", [
    {"n_qubits": 8},
    {"n_qubits": 300_000},
    {"n_qubits": 100, "trace_length": 65},
    {"n_qubits": 100, "backend": "hardware"},
    {"n_qubits": 100, "seed": -1},
])
def test_bb84_lab_rejects_bad_input(client, payload):
    assert client.post("/api/qkd/bb84", json=payload).status_code == 422


def test_qiskit_backend_qubit_cap(client):
    r = client.post("/api/qkd/bb84", json={"n_qubits": 50_000, "backend": "qiskit"})
    assert r.status_code == 422


@pytest.mark.qiskit
def test_bb84_lab_run_on_qiskit(client):
    pytest.importorskip("qiskit_aer")
    m = client.post("/api/qkd/bb84", json={"n_qubits": 512, "backend": "qiskit", "seed": 3}).json()["metrics"]
    assert m["simulation_kind"] == "circuit_simulation"
    assert m["true_sifted_errors"] == 0


# --- Phase 3: Eve and noise ---------------------------------------------------

def test_bb84_lab_run_with_full_eve(client):
    body = client.post("/api/qkd/bb84", json={
        "n_qubits": 20_000, "seed": 5, "eve_probability": 1.0,
    }).json()
    m = body["metrics"]
    assert body["channel"]["expected_qber"] == 0.25
    assert abs(m["true_sifted_error_rate"] - 0.25) < 0.02
    assert m["eve_intercepted"] == 20_000
    assert all(row["eve_intercepted"] for row in body["trace"])


def test_bb84_lab_run_with_noise_model(client):
    body = client.post("/api/qkd/bb84", json={
        "n_qubits": 20_000, "seed": 6, "channel_noise": 0.1, "noise_model": "bit_phase_flip",
    }).json()
    assert body["metrics"]["noise_model"] == "bit_phase_flip"
    assert abs(body["metrics"]["true_sifted_error_rate"] - 0.1) < 0.02


@pytest.mark.parametrize("payload", [
    {"eve_probability": 1.5}, {"eve_probability": -0.1},
    {"channel_noise": 1.01}, {"noise_model": "amplitude_damping"},
])
def test_bb84_lab_rejects_bad_channel_params(client, payload):
    assert client.post("/api/qkd/bb84", json={"n_qubits": 100, **payload}).status_code == 422


# --- Phase 4: full key exchange ----------------------------------------------

def test_key_exchange_accepts_clean_channel(client):
    body = client.post("/api/qkd/key-exchange", json={"seed": 1}).json()
    m = body["metrics"]
    assert m["n_qubits"] == 4096
    assert m["accepted"] and m["abort_reason"] is None
    assert m["final_key_length"] >= 256 and m["final_keys_match"] is True
    assert m["qber_threshold"] == 0.11 and m["sample_fraction"] == 0.25


def test_key_exchange_aborts_under_full_eve(client):
    m = client.post("/api/qkd/key-exchange", json={"seed": 2, "eve_probability": 1.0}).json()["metrics"]
    assert not m["accepted"]
    assert m["abort_reason"] == "qber_above_threshold"
    assert m["final_key_length"] == 0 and m["reconciliation"] is None


def test_key_exchange_threshold_override(client):
    m = client.post("/api/qkd/key-exchange", json={
        "seed": 3, "n_qubits": 16_384, "channel_noise": 0.12, "qber_threshold": 0.03,
    }).json()["metrics"]
    assert m["abort_reason"] == "qber_above_threshold" and m["qber_threshold"] == 0.03


def test_key_exchange_never_returns_key_bits(client):
    text = client.post("/api/qkd/key-exchange", json={"seed": 4}).text
    for forbidden in ("alice_final_key", "bob_final_key", "alice_key", "bob_key", "toeplitz_seed"):
        assert forbidden not in text


@pytest.mark.parametrize("payload", [{"qber_threshold": 0.6}, {"sample_fraction": 1.0}])
def test_key_exchange_rejects_bad_processing_params(client, payload):
    assert client.post("/api/qkd/key-exchange", json=payload).status_code == 422
