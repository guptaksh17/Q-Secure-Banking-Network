"""Runtime detection of optional simulation libraries.

The app must be honest about *how* qubits are simulated. If Qiskit / Qiskit Aer
are not importable, circuit-based simulation is reported as unavailable and the
NumPy model is the only option.
"""

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version


def _package_version(dist_name: str, module_name: str) -> str | None:
    try:
        import_module(module_name)
        return version(dist_name)
    except (ImportError, PackageNotFoundError):
        return None


def detect_capabilities() -> dict[str, str | bool | None]:
    qiskit_version = _package_version("qiskit", "qiskit")
    aer_version = _package_version("qiskit-aer", "qiskit_aer")
    return {
        "numpy": _package_version("numpy", "numpy"),
        "cryptography": _package_version("cryptography", "cryptography"),
        "qiskit": qiskit_version,
        "qiskit_aer": aer_version,
        "circuit_simulation_available": bool(qiskit_version and aer_version),
    }
