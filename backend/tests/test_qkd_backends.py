"""Both measurement backends must satisfy the same physical contract."""

import numpy as np
import pytest

from app.qkd.backends import NumpyBackend, get_backend
from app.qkd.states import Basis


@pytest.fixture(
    params=[
        "numpy",
        pytest.param("qiskit", marks=pytest.mark.qiskit),
    ]
)
def backend(request):
    if request.param == "qiskit":
        pytest.importorskip("qiskit_aer")
    return get_backend(request.param)


def _uniform(n, bit, prep, meas):
    return (
        np.full(n, bit, dtype=np.uint8),
        np.full(n, prep, dtype=np.uint8),
        np.full(n, meas, dtype=np.uint8),
    )


@pytest.mark.parametrize("bit", [0, 1])
@pytest.mark.parametrize("basis", list(Basis))
def test_matching_basis_measurement_is_deterministic(backend, bit, basis):
    bits, prep, meas = _uniform(500, bit, basis, basis)
    out = backend.measure(bits, prep, meas, np.random.default_rng(0))
    assert (out == bit).all()


@pytest.mark.parametrize("bit", [0, 1])
@pytest.mark.parametrize("prep, meas", [(Basis.Z, Basis.X), (Basis.X, Basis.Z)])
def test_mismatched_basis_measurement_is_unbiased(backend, bit, prep, meas):
    n = 4000
    bits, p, m = _uniform(n, bit, prep, meas)
    ones = backend.measure(bits, p, m, np.random.default_rng(1)).mean()
    # Binomial sd = sqrt(0.25 / n) ~ 0.0079; allow 5 sd.
    assert abs(ones - 0.5) < 5 * np.sqrt(0.25 / n)


def test_outputs_are_binary_uint8(backend):
    rng = np.random.default_rng(2)
    bits = rng.integers(0, 2, 300, dtype=np.uint8)
    out = backend.measure(bits, rng.integers(0, 2, 300, dtype=np.uint8),
                          rng.integers(0, 2, 300, dtype=np.uint8), rng)
    assert out.dtype == np.uint8 and set(np.unique(out)) <= {0, 1}


def test_same_seed_reproduces_outcomes(backend):
    def go():
        rng = np.random.default_rng(99)
        bits = rng.integers(0, 2, 200, dtype=np.uint8)
        return backend.measure(bits, rng.integers(0, 2, 200, dtype=np.uint8),
                               rng.integers(0, 2, 200, dtype=np.uint8), rng)
    np.testing.assert_array_equal(go(), go())


def test_shape_and_value_validation():
    b = NumpyBackend()
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError):
        b.measure(np.zeros(3, np.uint8), np.zeros(4, np.uint8), np.zeros(3, np.uint8), rng)
    with pytest.raises(ValueError):
        b.measure(np.array([0, 2], np.uint8), np.zeros(2, np.uint8), np.zeros(2, np.uint8), rng)


def test_unknown_backend_rejected():
    with pytest.raises(ValueError):
        get_backend("ibm-hardware")


def test_backends_declare_simulation_kind_honestly():
    assert NumpyBackend.simulation_kind == "mathematical_model"
    from app.qkd.backends import QiskitBackend
    assert QiskitBackend.simulation_kind == "circuit_simulation"


@pytest.mark.qiskit
def test_qiskit_circuit_uses_expected_gates():
    pytest.importorskip("qiskit_aer")
    from app.qkd.backends import QiskitBackend

    # qubit0: |0> measured Z; qubit1: |1> measured Z; qubit2: |+> measured X; qubit3: |-> measured Z
    qc = QiskitBackend().build_circuit(
        np.array([0, 1, 0, 1]), np.array([0, 0, 1, 1]), np.array([0, 0, 1, 0])
    )
    ops = {}
    for instr in qc.data:
        q = qc.find_bit(instr.qubits[0]).index
        ops.setdefault(q, []).append(instr.operation.name)
    assert ops[0] == ["measure"]
    assert ops[1] == ["x", "measure"]
    assert ops[2] == ["h", "h", "measure"]
    assert ops[3] == ["x", "h", "measure"]
