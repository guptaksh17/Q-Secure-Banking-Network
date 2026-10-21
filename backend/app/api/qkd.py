"""QKD Laboratory endpoints.

These runs are for exploration only: their key material is never used to encrypt
anything, never persisted, and only a short per-qubit trace is returned.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db

from app.config import Settings, get_settings
from app.qkd.backends import get_backend
from app.qkd.bb84 import run_bb84
from app.qkd.channel import ChannelConfig, expected_qber
from app.qkd.key_exchange import ProcessingConfig, run_key_exchange
from app.services.records import record_key_exchange

router = APIRouter(prefix="/qkd", tags=["qkd"])

MAX_QUBITS = {"numpy": 200_000, "qiskit": 20_000}


class BB84Request(BaseModel):
    n_qubits: int = Field(default=1024, ge=16, le=200_000)
    seed: int | None = Field(default=None, ge=0, description="Fix for reproducible runs")
    backend: Literal["numpy", "qiskit"] | None = Field(
        default=None, description="Defaults to QSB_QUANTUM_BACKEND"
    )
    eve_probability: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Fraction of qubits Eve intercepts and resends"
    )
    channel_noise: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Noise-channel probability per qubit"
    )
    noise_model: Literal["depolarizing", "bit_phase_flip"] = "depolarizing"
    trace_length: int = Field(default=16, ge=0, le=64)


@router.post("/bb84")
def bb84_lab_run(request: BB84Request, settings: Settings = Depends(get_settings)) -> dict:
    backend_name = request.backend or settings.quantum_backend
    if request.n_qubits > MAX_QUBITS[backend_name]:
        raise HTTPException(
            status_code=422,
            detail=f"{backend_name} backend supports at most {MAX_QUBITS[backend_name]} qubits",
        )
    try:
        backend = get_backend(backend_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    channel = ChannelConfig(
        eve_probability=request.eve_probability,
        noise=request.channel_noise,
        noise_model=request.noise_model,
    )
    run = run_bb84(request.n_qubits, backend=backend, seed=request.seed, channel=channel)
    return {
        "metrics": run.metrics(),
        "trace": run.trace(request.trace_length),
        "channel": {
            "eve_probability": channel.eve_probability,
            "noise": channel.noise,
            "noise_model": channel.noise_model,
            "expected_qber": expected_qber(channel),
            "topology": "Alice -> Eve (intercept-resend) -> noisy channel -> Bob",
        },
        "note": "Laboratory run: key material is discarded and never used for encryption.",
    }


class KeyExchangeRequest(BB84Request):
    n_qubits: int = Field(default=4096, ge=16, le=200_000)
    qber_threshold: float | None = Field(
        default=None, gt=0.0, lt=0.5, description="Defaults to QSB_QBER_THRESHOLD (illustrative)"
    )
    sample_fraction: float | None = Field(
        default=None, gt=0.0, lt=1.0, description="Defaults to QSB_QBER_SAMPLE_FRACTION"
    )


@router.post("/key-exchange")
def key_exchange_lab_run(
    request: KeyExchangeRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict:
    """Full pipeline: BB84 -> QBER estimation -> abort decision -> Cascade -> Toeplitz PA.

    The session's parameters and metrics are stored (purpose "lab"); key bits never are.
    Returns metrics and the accept/abort decision only — never key bits.
    """
    backend_name = request.backend or settings.quantum_backend
    if request.n_qubits > MAX_QUBITS[backend_name]:
        raise HTTPException(
            status_code=422,
            detail=f"{backend_name} backend supports at most {MAX_QUBITS[backend_name]} qubits",
        )
    try:
        backend = get_backend(backend_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    channel = ChannelConfig(
        eve_probability=request.eve_probability,
        noise=request.channel_noise,
        noise_model=request.noise_model,
    )
    processing = ProcessingConfig(
        qber_threshold=request.qber_threshold or settings.qber_threshold,
        sample_fraction=request.sample_fraction or settings.qber_sample_fraction,
    )
    result = run_key_exchange(
        request.n_qubits, channel=channel, processing=processing,
        seed=request.seed, backend=backend,
    )
    record = record_key_exchange(db, result, purpose="lab")
    return {
        "session_id": record.id,
        "metrics": result.metrics(),
        "trace": result.bb84.trace(request.trace_length),
        "channel": {
            "eve_probability": channel.eve_probability,
            "noise": channel.noise,
            "noise_model": channel.noise_model,
            "expected_qber": expected_qber(channel),
        },
        "note": "Laboratory run: final key material is discarded and never returned or stored.",
    }
