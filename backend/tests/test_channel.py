"""Unit tests for the channel stages (Eve, noise) in isolation."""

import numpy as np
import pytest

from app.qkd.backends import NumpyBackend
from app.qkd.bb84_types import PreparedStates
from app.qkd.channel import (
    ChannelConfig,
    apply_noise,
    expected_qber,
    intercept_resend,
    transmit,
)


def _states(n=10_000, seed=0):
    rng = np.random.default_rng(seed)
    return PreparedStates(
        bits=rng.integers(0, 2, n, dtype=np.uint8),
        bases=rng.integers(0, 2, n, dtype=np.uint8),
    )


# --- configuration ---------------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    {"eve_probability": -0.1}, {"eve_probability": 1.1},
    {"noise": -0.01}, {"noise": 2.0}, {"noise_model": "amplitude_damping"},
])
def test_invalid_channel_config_rejected(kwargs):
    with pytest.raises(ValueError):
        ChannelConfig(**kwargs)


def test_ideal_flag():
    assert ChannelConfig().is_ideal
    assert not ChannelConfig(eve_probability=0.1).is_ideal
    assert not ChannelConfig(noise=0.1).is_ideal


# --- zero parameters are exact no-ops and consume no randomness ------------

def test_ideal_transmit_is_identity_and_draws_no_randomness():
    states = _states()
    rng = np.random.default_rng(5)
    before = rng.bit_generator.state
    out = transmit(states, ChannelConfig(), rng, NumpyBackend())
    assert rng.bit_generator.state == before
    assert out.delivered is states
    assert not out.eve.intercepted.any() and not out.noise_mask.any()


# --- Eve ---------------------------------------------------------------------

def test_full_intercept_resends_in_eves_basis_with_her_result():
    states = _states()
    delivered, eve = intercept_resend(states, 1.0, np.random.default_rng(1), NumpyBackend())
    assert eve.intercepted.all()
    np.testing.assert_array_equal(delivered.bases, eve.bases)
    np.testing.assert_array_equal(delivered.bits, eve.results)


def test_eve_is_exact_when_her_basis_matches_alices():
    states = _states()
    _, eve = intercept_resend(states, 1.0, np.random.default_rng(2), NumpyBackend())
    same = eve.bases == states.bases
    np.testing.assert_array_equal(eve.results[same], states.bits[same])


def test_eve_basis_choice_is_uniform_and_intercept_rate_matches():
    n, p = 40_000, 0.3
    _, eve = intercept_resend(_states(n), p, np.random.default_rng(3), NumpyBackend())
    assert abs(eve.intercepted.mean() - p) < 5 * np.sqrt(p * (1 - p) / n)
    k = eve.intercepted.sum()
    assert abs(eve.bases[eve.intercepted].mean() - 0.5) < 5 * np.sqrt(0.25 / k)


def test_non_intercepted_qubits_untouched():
    states = _states()
    delivered, eve = intercept_resend(states, 0.4, np.random.default_rng(4), NumpyBackend())
    keep = ~eve.intercepted
    np.testing.assert_array_equal(delivered.bits[keep], states.bits[keep])
    np.testing.assert_array_equal(delivered.bases[keep], states.bases[keep])


def test_intercept_does_not_mutate_input():
    states = _states()
    bits, bases = states.bits.copy(), states.bases.copy()
    intercept_resend(states, 1.0, np.random.default_rng(6), NumpyBackend())
    np.testing.assert_array_equal(states.bits, bits)
    np.testing.assert_array_equal(states.bases, bases)


# --- noise -------------------------------------------------------------------

def test_bit_phase_flip_flips_bit_and_keeps_basis():
    states = _states()
    out, mask = apply_noise(states, 1.0, "bit_phase_flip", np.random.default_rng(7))
    assert mask.all()
    np.testing.assert_array_equal(out.bits, states.bits ^ 1)
    np.testing.assert_array_equal(out.bases, states.bases)


def test_depolarizing_replaces_with_uniform_bb84_mixture():
    """Full depolarizing output must be independent of the input: uniform bits and bases."""
    n = 40_000
    states = PreparedStates(np.zeros(n, np.uint8), np.zeros(n, np.uint8))  # all |0>
    out, _ = apply_noise(states, 1.0, "depolarizing", np.random.default_rng(8))
    tol = 5 * np.sqrt(0.25 / n)
    assert abs(out.bits.mean() - 0.5) < tol
    assert abs(out.bases.mean() - 0.5) < tol


@pytest.mark.parametrize("model", ["depolarizing", "bit_phase_flip"])
def test_noise_mask_rate_matches_probability(model):
    n, p = 40_000, 0.2
    _, mask = apply_noise(_states(n), p, model, np.random.default_rng(9))
    assert abs(mask.mean() - p) < 5 * np.sqrt(p * (1 - p) / n)


# --- theory ------------------------------------------------------------------

@pytest.mark.parametrize("cfg, expected", [
    (ChannelConfig(), 0.0),
    (ChannelConfig(eve_probability=1.0), 0.25),
    (ChannelConfig(eve_probability=0.5), 0.125),
    (ChannelConfig(noise=0.1), 0.05),
    (ChannelConfig(noise=1.0), 0.5),
    (ChannelConfig(noise=0.1, noise_model="bit_phase_flip"), 0.1),
    (ChannelConfig(noise=1.0, noise_model="bit_phase_flip"), 1.0),
    (ChannelConfig(eve_probability=1.0, noise=0.1), 0.9 * 0.25 + 0.05),
    (ChannelConfig(eve_probability=1.0, noise=0.1, noise_model="bit_phase_flip"), 0.25 * 0.9 + 0.75 * 0.1),
])
def test_expected_qber_formula(cfg, expected):
    assert expected_qber(cfg) == pytest.approx(expected)
