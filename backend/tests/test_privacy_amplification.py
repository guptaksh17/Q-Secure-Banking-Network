"""Toeplitz hashing and the illustrative key-length budget."""

import math

import numpy as np
import pytest

from app.qkd.privacy_amplification import (
    binary_entropy,
    random_seed,
    secure_key_length,
    toeplitz_hash,
    toeplitz_matrix,
)


def _bits(n, seed):
    return np.random.default_rng(seed).integers(0, 2, n, dtype=np.uint8)


@pytest.mark.parametrize("n, m", [(1, 1), (8, 3), (64, 64), (200, 37), (513, 256)])
def test_fft_hash_equals_explicit_matrix_product(n, m):
    seed, x = _bits(n + m - 1, n), _bits(n, n + 1)
    expected = (toeplitz_matrix(seed, n, m).astype(int) @ x.astype(int)) % 2
    np.testing.assert_array_equal(toeplitz_hash(x, seed, m), expected)


def test_large_input_is_exact():
    """FFT rounding must stay exact at realistic sizes (spot-check rows directly)."""
    n, m = 60_000, 20_000
    seed, x = _bits(n + m - 1, 1), _bits(n, 2)
    y = toeplitz_hash(x, seed, m)
    for i in (0, 1, 9_999, 19_999):
        row = seed[i - np.arange(n) + n - 1]
        assert y[i] == int(row.astype(int) @ x.astype(int)) % 2


def test_matrix_is_toeplitz():
    T = toeplitz_matrix(_bits(10 + 6 - 1, 3), 10, 6)
    for i in range(1, 6):
        np.testing.assert_array_equal(T[i, 1:], T[i - 1, :-1])


def test_hash_is_linear_over_gf2():
    n, m = 300, 100
    seed = random_seed(n, m, np.random.default_rng(4))
    x, y = _bits(n, 5), _bits(n, 6)
    np.testing.assert_array_equal(
        toeplitz_hash(x ^ y, seed, m), toeplitz_hash(x, seed, m) ^ toeplitz_hash(y, seed, m)
    )


def test_two_universal_collision_probability():
    """For fixed x != y, Pr_seed[h(x) = h(y)] should be 2^-m."""
    n, m, trials = 64, 4, 8000
    x = _bits(n, 7)
    y = x.copy()
    y[[3, 40]] ^= 1
    rng = np.random.default_rng(8)
    collisions = sum(
        np.array_equal(toeplitz_hash(x, s, m), toeplitz_hash(y, s, m))
        for s in (random_seed(n, m, rng) for _ in range(trials))
    )
    p = 2**-m
    assert abs(collisions / trials - p) < 5 * math.sqrt(p * (1 - p) / trials)


def test_output_bits_are_balanced():
    n, m = 2000, 1000
    out = toeplitz_hash(_bits(n, 9), random_seed(n, m, np.random.default_rng(10)), m)
    assert abs(out.mean() - 0.5) < 5 * math.sqrt(0.25 / m)


def test_seed_length_validated():
    with pytest.raises(ValueError):
        toeplitz_hash(_bits(10, 0), _bits(10, 1), 5)


def test_zero_length_output():
    assert toeplitz_hash(_bits(10, 0), _bits(9, 1), 0).size == 0


# --- entropy and key-length budget ------------------------------------------

@pytest.mark.parametrize("p, h", [(0, 0), (1, 0), (0.5, 1), (0.11, 0.4999)])
def test_binary_entropy(p, h):
    assert binary_entropy(p) == pytest.approx(h, abs=1e-4)


def test_key_length_formula():
    b = secure_key_length(10_000, 0.02, reconciliation_leak=1500, verification_leak=64, epsilon_pa=1e-10)
    expected = math.floor(10_000 * (1 - binary_entropy(0.02)) - 1500 - 64 - 2 * math.log2(1e10))
    assert b.output_bits == expected
    assert b.eve_information_bits == pytest.approx(10_000 * binary_entropy(0.02))


def test_key_length_never_negative_and_zero_at_high_qber():
    assert secure_key_length(1000, 0.3, 900, 64, 1e-10).output_bits == 0
    assert secure_key_length(1000, 0.6, 0, 0, 1e-10).output_bits == 0


def test_key_length_decreases_with_qber_and_leakage():
    a = secure_key_length(10_000, 0.01, 500, 64, 1e-10).output_bits
    assert secure_key_length(10_000, 0.03, 500, 64, 1e-10).output_bits < a
    assert secure_key_length(10_000, 0.01, 900, 64, 1e-10).output_bits < a
    assert secure_key_length(10_000, 0.01, 500, 64, 1e-20).output_bits < a
