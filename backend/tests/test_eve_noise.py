"""End-to-end BB84 behaviour under Eve and noise (statistical, fixed seeds)."""

import numpy as np
import pytest

from app.qkd.backends import get_backend
from app.qkd.bb84 import run_bb84
from app.qkd.channel import ChannelConfig, expected_qber

N = 40_000  # ~20,000 sifted bits per run


def _within(observed, expected, m, sigmas=5):
    """Sifted errors are i.i.d. Bernoulli(expected): check |obs - exp| < k * sd."""
    sd = np.sqrt(max(expected * (1 - expected), 1e-12) / m)
    return abs(observed - expected) < sigmas * sd


def _qber(cfg, seed, backend=None, n=N):
    m = run_bb84(n, seed=seed, channel=cfg, backend=backend).metrics()
    return m["true_sifted_error_rate"], m["sifted_key_length"], m


# --- Eve ---------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(5))
def test_full_intercept_resend_gives_about_25_percent_qber(seed):
    qber, m, _ = _qber(ChannelConfig(eve_probability=1.0), seed)
    assert _within(qber, 0.25, m)


def test_full_intercept_mean_over_runs_converges_to_quarter():
    rates = [_qber(ChannelConfig(eve_probability=1.0), s, n=8192)[0] for s in range(40)]
    assert np.mean(rates) == pytest.approx(0.25, abs=0.005)


@pytest.mark.parametrize("p", [0.1, 0.25, 0.5, 0.75])
def test_partial_interception_qber_is_p_over_4(p):
    qber, m, _ = _qber(ChannelConfig(eve_probability=p), seed=int(p * 100))
    assert _within(qber, p / 4, m)


def test_eve_learns_about_half_of_sifted_bits_under_full_attack():
    _, m, metrics = _qber(ChannelConfig(eve_probability=1.0), seed=21)
    assert _within(metrics["eve_known_sifted_fraction"], 0.5, m)


def test_eve_does_not_change_sifting_ratio():
    """Sifting depends only on Alice's and Bob's public bases, not on Eve."""
    clean = run_bb84(N, seed=3).metrics()
    attacked = run_bb84(N, seed=3, channel=ChannelConfig(eve_probability=1.0)).metrics()
    assert attacked["basis_matches"] == clean["basis_matches"]


# --- noise -------------------------------------------------------------------

@pytest.mark.parametrize("model", ["depolarizing", "bit_phase_flip"])
@pytest.mark.parametrize("noise", [0.02, 0.1, 0.3])
def test_noise_qber_matches_channel_theory(model, noise):
    cfg = ChannelConfig(noise=noise, noise_model=model)
    qber, m, _ = _qber(cfg, seed=int(noise * 1000))
    assert _within(qber, expected_qber(cfg), m)


@pytest.mark.parametrize("model", ["depolarizing", "bit_phase_flip"])
def test_more_noise_raises_observed_qber(model):
    levels = [0.0, 0.05, 0.1, 0.2, 0.3, 0.4]
    means = [
        np.mean([_qber(ChannelConfig(noise=x, noise_model=model), s, n=8192)[0] for s in range(10)])
        for x in levels
    ]
    assert all(b > a for a, b in zip(means, means[1:])), means


def test_noise_alone_can_exceed_illustrative_threshold():
    """High QBER does not prove Eve: pure noise with no eavesdropper can exceed 11%."""
    qber, _, metrics = _qber(ChannelConfig(noise=0.3), seed=4)
    assert metrics["eve_intercepted"] == 0
    assert qber > 0.11


def test_noise_gives_eve_no_information():
    _, _, metrics = _qber(ChannelConfig(noise=0.3), seed=5)
    assert metrics["eve_known_sifted_fraction"] == 0.0


# --- combined ----------------------------------------------------------------

@pytest.mark.parametrize("model", ["depolarizing", "bit_phase_flip"])
@pytest.mark.parametrize("eve, noise", [(0.5, 0.05), (1.0, 0.1)])
def test_combined_eve_and_noise_match_theory(model, eve, noise):
    cfg = ChannelConfig(eve_probability=eve, noise=noise, noise_model=model)
    qber, m, _ = _qber(cfg, seed=int(eve * 10 + noise * 100))
    assert _within(qber, expected_qber(cfg), m)


# --- reproducibility & regression -------------------------------------------

def test_ideal_channel_matches_phase2_behaviour_bit_for_bit():
    a = run_bb84(4096, seed=77)
    b = run_bb84(4096, seed=77, channel=ChannelConfig())
    np.testing.assert_array_equal(a.bob_results, b.bob_results)
    assert a.metrics()["true_sifted_errors"] == 0


def test_attacked_runs_are_reproducible():
    cfg = ChannelConfig(eve_probability=0.6, noise=0.1)
    a, b = run_bb84(5000, seed=9, channel=cfg), run_bb84(5000, seed=9, channel=cfg)
    np.testing.assert_array_equal(a.bob_results, b.bob_results)
    np.testing.assert_array_equal(a.channel.eve.bases, b.channel.eve.bases)
    assert a.metrics() == b.metrics()


def test_trace_reports_eve_noise_and_errors_consistently():
    run = run_bb84(500, seed=10, channel=ChannelConfig(eve_probability=1.0, noise=0.2))
    for row in run.trace(64):
        assert row["eve_intercepted"] is True and row["eve_basis"] in ("Z", "X")
        assert row["error"] == (row["bases_match"] and row["bob_result"] != row["alice_bit"])
    clean = run_bb84(100, seed=10).trace(10)
    assert all(r["eve_basis"] is None and r["eve_result"] is None for r in clean)


# --- Qiskit backend ----------------------------------------------------------

@pytest.mark.qiskit
def test_full_intercept_on_qiskit_backend_gives_about_25_percent():
    pytest.importorskip("qiskit_aer")
    qber, m, metrics = _qber(ChannelConfig(eve_probability=1.0), seed=31,
                             backend=get_backend("qiskit"), n=16_000)
    assert metrics["simulation_kind"] == "circuit_simulation"
    assert _within(qber, 0.25, m)


@pytest.mark.qiskit
def test_noise_on_qiskit_backend_matches_theory():
    pytest.importorskip("qiskit_aer")
    cfg = ChannelConfig(eve_probability=0.5, noise=0.1, noise_model="bit_phase_flip")
    qber, m, _ = _qber(cfg, seed=32, backend=get_backend("qiskit"), n=16_000)
    assert _within(qber, expected_qber(cfg), m)
