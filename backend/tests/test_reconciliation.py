"""Cascade-inspired reconciliation."""

import numpy as np
import pytest

from app.qkd.privacy_amplification import binary_entropy
from app.qkd.reconciliation import (
    _Cascade,
    cascade_reconcile,
    initial_block_size,
    keys_match_by_hash,
)


def _keys(n, error_rate, seed):
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 2, n, dtype=np.uint8)
    b = a ^ (rng.random(n) < error_rate).astype(np.uint8)
    return a, b


@pytest.mark.parametrize("error_rate", [0.01, 0.03, 0.05, 0.08, 0.11])
@pytest.mark.parametrize("seed", range(5))
def test_cascade_removes_all_errors(error_rate, seed):
    a, b = _keys(6000, error_rate, seed)
    r = cascade_reconcile(a, b, error_rate, np.random.default_rng(seed + 100))
    np.testing.assert_array_equal(r.bob_corrected, a)
    assert r.verified
    assert r.errors_corrected == int(np.count_nonzero(a != b))


@pytest.mark.parametrize("error_rate", [0.02, 0.05, 0.1])
def test_leakage_respects_shannon_limit_and_is_efficient(error_rate):
    """Disclosed parities must be >= n h(e) (information-theoretic minimum) and,
    for Cascade, within ~1.1-1.3x of it."""
    n = 20_000
    a, b = _keys(n, error_rate, 1)
    r = cascade_reconcile(a, b, error_rate, np.random.default_rng(2))
    actual_errors = np.count_nonzero(a != b) / n
    efficiency = r.leaked_bits / (n * binary_entropy(actual_errors))
    assert 1.0 <= efficiency < 1.35, efficiency


def test_no_errors_means_no_corrections_and_only_block_parities_leak():
    a, _ = _keys(1000, 0, 3)
    r = cascade_reconcile(a, a.copy(), 0.0, np.random.default_rng(4), passes=4)
    assert r.errors_corrected == 0
    expected = sum(int(np.ceil(1000 / s)) for s in r.block_sizes)
    assert r.leaked_bits == expected
    assert r.verified


def test_block_sizes_double_each_pass():
    a, b = _keys(5000, 0.05, 5)
    r = cascade_reconcile(a, b, 0.05, np.random.default_rng(6))
    k1 = initial_block_size(0.05, 5000)
    assert k1 == 15  # ceil(0.73 / 0.05)
    assert r.block_sizes == [15, 30, 60, 120]


def test_initial_block_size_bounds():
    assert initial_block_size(0.0, 10_000) == 73     # floored QBER of 1%
    assert initial_block_size(0.4, 10_000) == 4      # minimum block size
    assert initial_block_size(0.001, 50) == 50       # capped at key length


def test_binary_search_finds_single_error_with_log2_leakage():
    a = np.zeros(64, np.uint8)
    b = a.copy()
    b[37] = 1
    c = _Cascade(a, b, np.random.default_rng(0), k1=64)
    assert c._binary_search(np.arange(64)) == 37
    assert c.leaked == 6  # log2(64)


def test_does_not_mutate_inputs():
    a, b = _keys(2000, 0.05, 7)
    a0, b0 = a.copy(), b.copy()
    cascade_reconcile(a, b, 0.05, np.random.default_rng(8))
    np.testing.assert_array_equal(a, a0)
    np.testing.assert_array_equal(b, b0)


def test_verification_detects_residual_errors():
    """One pass cannot see an even number of errors inside a block; the hash catches it."""
    a = np.zeros(400, np.uint8)
    b = a.copy()
    b[[0, 1]] = 1  # two errors in the first block of pass 0
    r = cascade_reconcile(a, b, 0.01, np.random.default_rng(9), passes=1)
    assert not np.array_equal(r.bob_corrected, a)
    assert not r.verified


def test_hash_comparison():
    rng = np.random.default_rng(10)
    a, _ = _keys(500, 0, 11)
    assert keys_match_by_hash(a, a.copy(), 64, rng)
    b = a.copy()
    b[123] ^= 1
    assert not keys_match_by_hash(a, b, 64, rng)


def test_reproducible():
    a, b = _keys(3000, 0.04, 12)
    r1 = cascade_reconcile(a, b, 0.04, np.random.default_rng(13))
    r2 = cascade_reconcile(a, b, 0.04, np.random.default_rng(13))
    assert r1.leaked_bits == r2.leaked_bits and r1.block_sizes == r2.block_sizes


def test_input_validation():
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError):
        cascade_reconcile(np.zeros(3, np.uint8), np.zeros(4, np.uint8), 0.1, rng)
    with pytest.raises(ValueError):
        cascade_reconcile(np.zeros(0, np.uint8), np.zeros(0, np.uint8), 0.1, rng)
    with pytest.raises(ValueError):
        cascade_reconcile(np.zeros(3, np.uint8), np.zeros(3, np.uint8), 0.1, rng, passes=0)


@pytest.mark.parametrize("passes", [2, 3, 4])
@pytest.mark.parametrize("seed", range(8))
def test_cascade_invariant_every_block_in_every_pass_has_even_disagreement(passes, seed):
    """Defining property of Cascade: after it finishes, no block in ANY pass has
    mismatched parity. Without the cascade (back-tracking) step, corrections made
    in later passes leave earlier-pass blocks odd."""
    a, b = _keys(3000, 0.1, seed)
    c = _Cascade(a, b, np.random.default_rng(seed + 50), initial_block_size(0.1, 3000))
    c.run(passes)
    for p, size in enumerate(c.sizes):
        for blk in range(int(np.ceil(3000 / size))):
            idx = c._block(p, blk)
            assert int(a[idx].sum() & 1) == int(c.bob[idx].sum() & 1), (p, blk)
