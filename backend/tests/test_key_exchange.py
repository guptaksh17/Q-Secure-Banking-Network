"""End-to-end key exchange: accept/abort decisions and matching final keys."""

import numpy as np
import pytest

from app.qkd.channel import ChannelConfig
from app.qkd.key_exchange import AbortReason, ProcessingConfig, run_key_exchange


@pytest.mark.parametrize("seed", range(5))
def test_ideal_channel_is_accepted_with_matching_keys(seed):
    r = run_key_exchange(4096, seed=seed)
    assert r.accepted
    assert r.alice_final_key.size >= 256
    np.testing.assert_array_equal(r.alice_final_key, r.bob_final_key)


@pytest.mark.parametrize("model, noise", [("depolarizing", 0.06), ("bit_phase_flip", 0.03)])
@pytest.mark.parametrize("seed", range(3))
def test_moderate_noise_is_reconciled_and_accepted(model, noise, seed):
    r = run_key_exchange(16_384, channel=ChannelConfig(noise=noise, noise_model=model), seed=seed)
    m = r.metrics()
    assert r.accepted, m["abort_reason"]
    assert m["errors_before_reconciliation"] > 0
    assert m["reconciliation"]["residual_errors"] == 0
    np.testing.assert_array_equal(r.alice_final_key, r.bob_final_key)


@pytest.mark.parametrize("seed", range(10))
def test_full_intercept_resend_always_aborts_on_threshold(seed):
    r = run_key_exchange(4096, channel=ChannelConfig(eve_probability=1.0), seed=seed)
    assert r.abort_reason is AbortReason.QBER_ABOVE_THRESHOLD
    assert r.alice_final_key is None and r.bob_final_key is None
    assert r.reconciliation is None  # aborted before any further disclosure


def test_high_noise_alone_aborts():
    r = run_key_exchange(4096, channel=ChannelConfig(noise=0.4), seed=1)
    assert r.abort_reason is AbortReason.QBER_ABOVE_THRESHOLD
    assert r.metrics()["eve_intercepted"] == 0


def test_permissive_threshold_still_yields_no_key_under_full_attack():
    """Even if the threshold is misconfigured, privacy amplification leaves nothing for Eve."""
    cfg = ProcessingConfig(qber_threshold=0.45)
    r = run_key_exchange(16_384, channel=ChannelConfig(eve_probability=1.0), processing=cfg, seed=2)
    assert r.abort_reason is AbortReason.INSUFFICIENT_KEY
    assert r.budget.output_bits == 0
    assert r.alice_final_key is None


def test_threshold_is_configurable():
    ch = ChannelConfig(noise=0.12)  # depolarizing -> QBER ~6%
    strict = run_key_exchange(16_384, channel=ch, processing=ProcessingConfig(qber_threshold=0.03), seed=3)
    lenient = run_key_exchange(16_384, channel=ch, processing=ProcessingConfig(qber_threshold=0.11), seed=3)
    assert strict.abort_reason is AbortReason.QBER_ABOVE_THRESHOLD
    assert lenient.accepted


def test_too_few_qubits_aborts_cleanly():
    r = run_key_exchange(64, seed=4)
    assert r.abort_reason is AbortReason.SAMPLE_TOO_SMALL
    small = run_key_exchange(1024, seed=4)
    assert small.abort_reason is AbortReason.INSUFFICIENT_KEY  # finite-size cost dominates


def test_partial_eve_below_threshold_is_accepted_after_privacy_amplification():
    r = run_key_exchange(16_384, channel=ChannelConfig(eve_probability=0.2), seed=5)
    m = r.metrics()
    assert r.accepted
    # PA removes at least as many bits as Eve actually learned on the remaining key
    assert m["privacy_amplification"]["eve_information_bits"] > m["eve_known_sifted_bits"]


def test_sample_bits_are_disjoint_from_final_key_input():
    r = run_key_exchange(4096, seed=6)
    est = r.estimate
    assert est.sample_size + est.remaining_length == est.sifted_length
    assert r.budget.input_bits == est.remaining_length


def test_metrics_contain_no_key_material():
    r = run_key_exchange(4096, seed=7)
    m = r.metrics()
    flat = str(m)
    assert "alice_final_key" not in flat and "bob_final_key" not in flat

    def no_long_bit_lists(obj):
        if isinstance(obj, dict):
            return all(no_long_bit_lists(v) for v in obj.values())
        if isinstance(obj, (list, tuple, np.ndarray)):
            return len(obj) <= 16  # e.g. Cascade block sizes
        return True
    assert no_long_bit_lists(m)


def test_reproducible():
    ch = ChannelConfig(eve_probability=0.1, noise=0.05)
    a, b = run_key_exchange(8192, channel=ch, seed=8), run_key_exchange(8192, channel=ch, seed=8)
    assert a.metrics() == b.metrics()
    if a.accepted:
        np.testing.assert_array_equal(a.alice_final_key, b.alice_final_key)
    assert a.metrics()["seed"] == 8


def test_different_seeds_give_different_final_keys():
    a, b = run_key_exchange(4096, seed=9), run_key_exchange(4096, seed=10)
    n = min(a.alice_final_key.size, b.alice_final_key.size)
    assert not np.array_equal(a.alice_final_key[:n], b.alice_final_key[:n])


@pytest.mark.parametrize("kwargs", [
    {"qber_threshold": 0.0}, {"qber_threshold": 0.5}, {"sample_fraction": 1.0},
    {"estimation_epsilon": 0.0}, {"pa_epsilon": 1.0}, {"cascade_passes": 0},
    {"min_final_key_bits": 0},
])
def test_processing_config_validation(kwargs):
    with pytest.raises(ValueError):
        ProcessingConfig(**kwargs)


@pytest.mark.qiskit
def test_key_exchange_on_qiskit_backend():
    pytest.importorskip("qiskit_aer")
    from app.qkd.backends import get_backend

    r = run_key_exchange(8192, seed=11, backend=get_backend("qiskit"),
                         channel=ChannelConfig(noise=0.04))
    assert r.metrics()["simulation_kind"] == "circuit_simulation"
    assert r.accepted
    np.testing.assert_array_equal(r.alice_final_key, r.bob_final_key)
