import pytest
from pydantic import ValidationError

from app.config import Settings


def test_defaults_are_illustrative_bb84_values():
    s = Settings()
    assert s.qber_threshold == pytest.approx(0.11)
    assert 0 < s.qber_sample_fraction < 1
    assert s.quantum_backend == "numpy"
    assert s.random_seed is None


def test_cors_origins_accept_comma_separated_string(monkeypatch):
    monkeypatch.setenv("QSB_CORS_ORIGINS", "http://a.test, http://b.test")
    assert Settings().cors_origins == ["http://a.test", "http://b.test"]


def test_empty_seed_means_os_randomness(monkeypatch):
    monkeypatch.setenv("QSB_RANDOM_SEED", "")
    assert Settings().random_seed is None
    monkeypatch.setenv("QSB_RANDOM_SEED", "42")
    assert Settings().random_seed == 42


@pytest.mark.parametrize("bad", ["0", "0.5", "-0.1", "0.9"])
def test_qber_threshold_must_be_strictly_between_0_and_half(monkeypatch, bad):
    monkeypatch.setenv("QSB_QBER_THRESHOLD", bad)
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("bad", ["0", "1", "1.5"])
def test_sample_fraction_must_be_strictly_between_0_and_1(monkeypatch, bad):
    monkeypatch.setenv("QSB_QBER_SAMPLE_FRACTION", bad)
    with pytest.raises(ValidationError):
        Settings()


def test_unknown_quantum_backend_rejected(monkeypatch):
    monkeypatch.setenv("QSB_QUANTUM_BACKEND", "real-hardware")
    with pytest.raises(ValidationError):
        Settings()
