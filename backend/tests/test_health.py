def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"
    assert "not production-grade" in body["disclaimer"]


def test_health_reports_qkd_defaults(client):
    defaults = client.get("/api/health").json()["qkd_defaults"]
    assert defaults["qber_threshold"] == 0.11
    assert defaults["quantum_backend"] in {"numpy", "qiskit"}


def test_health_reports_simulation_capabilities(client):
    caps = client.get("/api/health").json()["capabilities"]
    assert caps["numpy"] is not None
    assert caps["cryptography"] is not None
    # Circuit simulation is only claimed when BOTH qiskit and qiskit-aer import.
    assert caps["circuit_simulation_available"] == bool(caps["qiskit"] and caps["qiskit_aer"])


def test_cors_allows_vite_dev_origin(client):
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_never_exposes_key_material(client):
    text = client.get("/api/health").text.lower()
    for forbidden in ("secret", "aes_key", "raw_key", "final_key"):
        assert forbidden not in text
