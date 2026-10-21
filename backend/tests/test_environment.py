"""Smoke tests that the scientific stack is installed and behaves as expected."""

import pytest


def test_numpy_generator_is_reproducible_with_seed():
    import numpy as np

    a = np.random.default_rng(123).integers(0, 2, size=64)
    b = np.random.default_rng(123).integers(0, 2, size=64)
    assert (a == b).all()


def test_aesgcm_available():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = AESGCM.generate_key(bit_length=256)
    assert len(key) == 32


@pytest.mark.qiskit
def test_qiskit_aer_measures_plus_state_on_x_basis_deterministically():
    """|+> measured in X basis (H then Z-measure) must always give 0."""
    qiskit = pytest.importorskip("qiskit")
    aer = pytest.importorskip("qiskit_aer")

    qc = qiskit.QuantumCircuit(1, 1)
    qc.h(0)  # prepare |+>
    qc.h(0)  # rotate X basis onto Z basis
    qc.measure(0, 0)
    counts = aer.AerSimulator(seed_simulator=7).run(qc, shots=200).result().get_counts()
    assert counts == {"0": 200}
