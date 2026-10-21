"""BB84 bases, single-qubit states and Born-rule measurement probabilities.

Z (rectilinear) basis: |0>, |1>
X (diagonal) basis:    |+> = (|0> + |1>)/sqrt(2),  |-> = (|0> - |1>)/sqrt(2)

Bit encoding: in each basis, bit 0 -> first state, bit 1 -> second state.
So (bit, basis): (0,Z)=|0>, (1,Z)=|1>, (0,X)=|+>, (1,X)=|->.
"""

from enum import IntEnum

import numpy as np


class Basis(IntEnum):
    Z = 0
    X = 1


KET_0 = np.array([1.0, 0.0], dtype=complex)
KET_1 = np.array([0.0, 1.0], dtype=complex)
KET_PLUS = (KET_0 + KET_1) / np.sqrt(2)
KET_MINUS = (KET_0 - KET_1) / np.sqrt(2)

_BASIS_STATES: dict[Basis, tuple[np.ndarray, np.ndarray]] = {
    Basis.Z: (KET_0, KET_1),
    Basis.X: (KET_PLUS, KET_MINUS),
}

STATE_LABELS: dict[tuple[int, Basis], str] = {
    (0, Basis.Z): "|0>",
    (1, Basis.Z): "|1>",
    (0, Basis.X): "|+>",
    (1, Basis.X): "|->",
}


def bb84_state(bit: int, basis: Basis | int) -> np.ndarray:
    """State vector Alice prepares to encode ``bit`` in ``basis``."""
    if bit not in (0, 1):
        raise ValueError(f"bit must be 0 or 1, got {bit!r}")
    return _BASIS_STATES[Basis(basis)][bit]


def born_probability(state: np.ndarray, outcome: int, basis: Basis | int) -> float:
    """P(outcome | measure ``state`` in ``basis``) = |<basis_outcome|state>|^2."""
    projector_vector = _BASIS_STATES[Basis(basis)][outcome]
    return float(abs(np.vdot(projector_vector, state)) ** 2)


def _build_prob_one_table() -> np.ndarray:
    table = np.empty((2, 2, 2), dtype=float)
    for prep_basis in Basis:
        for bit in (0, 1):
            state = bb84_state(bit, prep_basis)
            for meas_basis in Basis:
                table[prep_basis, bit, meas_basis] = born_probability(state, 1, meas_basis)
    return table


# PROB_ONE[prep_basis, prep_bit, meas_basis] = probability the measurement yields 1.
# Derived from the state vectors above (not hand-written), giving 0/1 for matching
# bases and 0.5 for mismatching bases.
PROB_ONE: np.ndarray = _build_prob_one_table()
