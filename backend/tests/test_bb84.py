"""BB84 protocol tests (ideal channel, no Eve, no noise)."""

import numpy as np
import pytest

from app.qkd.backends import get_backend
from app.qkd.bb84 import PreparedStates, alice_prepare, make_rng, run_bb84, sift


@pytest.fixture(params=["numpy", pytest.param("qiskit", marks=pytest.mark.qiskit)])
def backend(request):
    if request.param == "qiskit":
        pytest.importorskip("qiskit_aer")
    return get_backend(request.param)


# --- correctness -----------------------------------------------------------

@pytest.mark.parametrize("seed", range(5))
def test_ideal_channel_sifted_keys_agree_exactly(backend, seed):
    run = run_bb84(2000, seed=seed, backend=backend)
    np.testing.assert_array_equal(run.sift.alice_key, run.sift.bob_key)
    assert run.metrics()["true_sifted_errors"] == 0


def test_bob_matches_alice_wherever_bases_match(backend):
    run = run_bb84(3000, seed=11, backend=backend)
    m = run.alice_bases == run.bob_bases
    np.testing.assert_array_equal(run.bob_results[m], run.alice_bits[m])


def test_mismatched_positions_are_uncorrelated(backend):
    """Where bases differ Bob's result agrees with Alice's bit ~50% of the time."""
    run = run_bb84(20_000, seed=12, backend=backend)
    m = run.alice_bases != run.bob_bases
    agree = (run.bob_results[m] == run.alice_bits[m]).mean()
    assert abs(agree - 0.5) < 5 * np.sqrt(0.25 / m.sum())


def test_sift_keeps_exactly_matching_positions():
    a_bits = np.array([0, 1, 1, 0, 1], np.uint8)
    a_bases = np.array([0, 1, 0, 1, 1], np.uint8)
    b_bases = np.array([0, 0, 0, 1, 0], np.uint8)
    b_res = np.array([0, 1, 1, 0, 0], np.uint8)
    s = sift(a_bits, a_bases, b_bases, b_res)
    np.testing.assert_array_equal(s.indices, [0, 2, 3])
    np.testing.assert_array_equal(s.alice_key, [0, 1, 0])
    np.testing.assert_array_equal(s.bob_key, [0, 1, 0])


# --- statistics ------------------------------------------------------------

@pytest.mark.parametrize("seed", range(10))
def test_sifting_retains_about_half_in_large_runs(seed):
    n = 20_000
    ratio = run_bb84(n, seed=seed).metrics()["sifting_ratio"]
    assert abs(ratio - 0.5) < 5 * np.sqrt(0.25 / n)  # ~0.018


def test_sifting_ratio_concentrates_as_n_grows():
    """Spread of the sifting ratio across trials shrinks roughly like 1/sqrt(n)."""
    def spread(n):
        return np.std([run_bb84(n, seed=s).metrics()["sifting_ratio"] for s in range(40)])
    small, large = spread(256), spread(16_384)
    assert large < small / 4  # theory: ratio of 8


def test_alice_bits_and_bases_are_uniform():
    states = alice_prepare(50_000, make_rng(3))
    tol = 5 * np.sqrt(0.25 / 50_000)
    assert abs(states.bits.mean() - 0.5) < tol
    assert abs(states.bases.mean() - 0.5) < tol
    # independence: P(bit=1, basis=X) ~ 0.25
    joint = (states.bits & states.bases).mean()
    assert abs(joint - 0.25) < 5 * np.sqrt(0.25 * 0.75 / 50_000)


# --- reproducibility, metrics, API surface ---------------------------------

def test_same_seed_same_run():
    a, b = run_bb84(1000, seed=7), run_bb84(1000, seed=7)
    np.testing.assert_array_equal(a.alice_bits, b.alice_bits)
    np.testing.assert_array_equal(a.bob_results, b.bob_results)
    assert a.metrics() == b.metrics()


def test_different_seeds_differ():
    assert not np.array_equal(run_bb84(1000, seed=1).alice_bits, run_bb84(1000, seed=2).alice_bits)


@pytest.mark.qiskit
def test_backends_share_basis_choices_for_same_seed():
    """RNG draws for bits/bases happen before measurement, so sifting is identical."""
    pytest.importorskip("qiskit_aer")
    a = run_bb84(2000, seed=5, backend=get_backend("numpy"))
    b = run_bb84(2000, seed=5, backend=get_backend("qiskit"))
    np.testing.assert_array_equal(a.sift.mask, b.sift.mask)
    np.testing.assert_array_equal(a.sift.bob_key, b.sift.bob_key)


def test_metrics_are_consistent_and_contain_no_key_bits():
    run = run_bb84(4096, seed=8)
    m = run.metrics()
    assert m["n_qubits"] == 4096
    assert m["basis_matches"] == m["sifted_key_length"] == len(run.sift)
    assert m["sifting_ratio"] == pytest.approx(m["basis_matches"] / 4096)
    assert m["simulation_kind"] == "mathematical_model"
    assert all(not isinstance(v, (list, np.ndarray)) for v in m.values())


def test_trace_rows_are_consistent():
    run = run_bb84(100, seed=9)
    rows = run.trace(10)
    assert len(rows) == 10
    labels = {(0, "Z"): "|0>", (1, "Z"): "|1>", (0, "X"): "|+>", (1, "X"): "|->"}
    for r in rows:
        assert r["state"] == labels[(r["alice_bit"], r["alice_basis"])]
        assert r["bases_match"] == (r["alice_basis"] == r["bob_basis"])
        if r["bases_match"]:
            assert r["bob_result"] == r["alice_bit"]
    assert len(run.trace(1000)) == 100


def test_input_validation():
    with pytest.raises(ValueError):
        run_bb84(0)
    with pytest.raises(ValueError):
        run_bb84(10, rng=make_rng(1), seed=1)
    with pytest.raises(ValueError):
        PreparedStates(bits=np.zeros(3, np.uint8), bases=np.zeros(2, np.uint8))
