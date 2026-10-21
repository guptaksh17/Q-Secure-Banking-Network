"""QBER test-sample disclosure and estimation."""

import numpy as np
import pytest

from app.qkd.estimation import _binomial_cdf, clopper_pearson_upper, estimate_qber


def _keys(n, error_rate, seed):
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 2, n, dtype=np.uint8)
    b = a ^ (rng.random(n) < error_rate).astype(np.uint8)
    return a, b


def test_sample_size_and_removal():
    a, b = _keys(2000, 0.05, 0)
    est = estimate_qber(a, b, 0.25, np.random.default_rng(1))
    assert est.sample_size == 500
    assert est.sample_mask.sum() == 500
    assert est.remaining_length == 1500
    # remaining bits are exactly the unsampled positions, order preserved
    np.testing.assert_array_equal(est.alice_remaining, a[~est.sample_mask])
    np.testing.assert_array_equal(est.bob_remaining, b[~est.sample_mask])


def test_estimate_counts_errors_in_sample_exactly():
    a = np.zeros(100, np.uint8)
    b = np.zeros(100, np.uint8)
    b[:100:2] = 1  # 50% errors at even positions
    est = estimate_qber(a, b, 0.5, np.random.default_rng(2))
    expected = int(est.sample_mask[::2].sum())
    assert est.sample_errors == expected
    assert est.qber_estimate == pytest.approx(expected / 50)


def test_sample_positions_are_uniform():
    """Every position should be sampled ~fraction of the time across many draws."""
    a, b = _keys(200, 0.0, 3)
    rng = np.random.default_rng(4)
    hits = sum(estimate_qber(a, b, 0.25, rng).sample_mask.astype(int) for _ in range(2000))
    freq = hits / 2000
    assert abs(freq.mean() - 0.25) < 1e-9
    assert freq.min() > 0.17 and freq.max() < 0.33


def test_estimate_is_unbiased_for_true_error_rate():
    ests = [estimate_qber(*_keys(4000, 0.07, s), 0.25, np.random.default_rng(100 + s)).qber_estimate
            for s in range(200)]
    assert np.mean(ests) == pytest.approx(0.07, abs=0.003)


def test_zero_errors_gives_zero_estimate_and_positive_upper_bound():
    a, _ = _keys(1000, 0.0, 5)
    est = estimate_qber(a, a.copy(), 0.2, np.random.default_rng(6), epsilon=1e-3)
    assert est.qber_estimate == 0.0
    # closed form for zero errors: 1 - eps^(1/k)
    assert est.qber_upper == pytest.approx(1 - 1e-3 ** (1 / 200), rel=1e-6)


@pytest.mark.parametrize("kwargs", [{"sample_fraction": 0.0}, {"sample_fraction": 1.0}])
def test_invalid_fraction_rejected(kwargs):
    a, b = _keys(10, 0, 0)
    with pytest.raises(ValueError):
        estimate_qber(a, b, rng=np.random.default_rng(0), **kwargs)


def test_mismatched_lengths_rejected():
    with pytest.raises(ValueError):
        estimate_qber(np.zeros(3, np.uint8), np.zeros(4, np.uint8), 0.5, np.random.default_rng(0))


# --- Clopper-Pearson bound -------------------------------------------------

def test_binomial_cdf_matches_direct_sum():
    from math import comb
    n, p = 30, 0.2
    for k in (0, 3, 10, 30):
        direct = sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))
        assert _binomial_cdf(k, n, p) == pytest.approx(direct, rel=1e-9)


def test_upper_bound_properties():
    assert clopper_pearson_upper(10, 10, 0.01) == 1.0
    assert clopper_pearson_upper(0, 0, 0.01) == 1.0
    ub = clopper_pearson_upper(20, 400, 1e-3)
    assert ub > 20 / 400
    assert _binomial_cdf(20, 400, ub) == pytest.approx(1e-3, rel=1e-4)
    # more errors -> higher bound; bigger sample -> tighter bound
    assert clopper_pearson_upper(30, 400, 1e-3) > ub
    assert clopper_pearson_upper(200, 4000, 1e-3) < ub
    # higher confidence -> higher bound
    assert clopper_pearson_upper(20, 400, 1e-6) > ub


def test_upper_bound_coverage():
    """With confidence 95%, the true rate should exceed the bound in <= ~5% of samples."""
    rng = np.random.default_rng(7)
    p, k, eps = 0.06, 300, 0.05
    misses = sum(clopper_pearson_upper(int(rng.binomial(k, p)), k, eps) < p for _ in range(2000))
    assert misses / 2000 <= eps + 0.015
