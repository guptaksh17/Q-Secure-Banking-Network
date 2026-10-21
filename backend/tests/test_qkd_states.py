import numpy as np
import pytest

from app.qkd.states import (
    KET_0,
    KET_1,
    KET_MINUS,
    KET_PLUS,
    PROB_ONE,
    Basis,
    bb84_state,
    born_probability,
)

SQRT_HALF = 1 / np.sqrt(2)


def test_x_basis_states_match_definitions():
    np.testing.assert_allclose(KET_PLUS, [SQRT_HALF, SQRT_HALF])
    np.testing.assert_allclose(KET_MINUS, [SQRT_HALF, -SQRT_HALF])


@pytest.mark.parametrize("bit", [0, 1])
@pytest.mark.parametrize("basis", list(Basis))
def test_states_are_normalised(bit, basis):
    assert np.linalg.norm(bb84_state(bit, basis)) == pytest.approx(1.0)


@pytest.mark.parametrize("basis", list(Basis))
def test_each_basis_is_orthonormal(basis):
    assert abs(np.vdot(bb84_state(0, basis), bb84_state(1, basis))) == pytest.approx(0.0)


def test_bases_are_mutually_unbiased():
    """|<z|x>|^2 = 1/2 for every Z state and X state — the core of BB84 security."""
    for z in (KET_0, KET_1):
        for x in (KET_PLUS, KET_MINUS):
            assert abs(np.vdot(z, x)) ** 2 == pytest.approx(0.5)


@pytest.mark.parametrize("bit", [0, 1])
@pytest.mark.parametrize("basis", list(Basis))
def test_born_probabilities_sum_to_one(bit, basis):
    state = bb84_state(bit, basis)
    for meas in Basis:
        total = born_probability(state, 0, meas) + born_probability(state, 1, meas)
        assert total == pytest.approx(1.0)


def test_prob_table_matching_basis_is_deterministic_and_mismatch_is_half():
    for prep in Basis:
        for bit in (0, 1):
            for meas in Basis:
                expected = float(bit) if prep == meas else 0.5
                assert PROB_ONE[prep, bit, meas] == pytest.approx(expected)


def test_invalid_bit_rejected():
    with pytest.raises(ValueError):
        bb84_state(2, Basis.Z)
