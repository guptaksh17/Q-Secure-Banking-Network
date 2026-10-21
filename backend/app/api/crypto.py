"""AES-256-GCM laboratory endpoint for the Security Simulator.

Runs a full QKD key exchange, derives session keys, encrypts a fictional message as
Bank A, optionally tampers with it in transit, and lets Bank B verify/decrypt.
Returns ciphertext, nonce, tag and the verification outcome — never key material.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.crypto.aead import AEADError, AEADReceiver
from app.crypto.secure_channel import establish_endpoints
from app.crypto.tamper import TamperMode, tamper_message
from app.qkd.channel import ChannelConfig
from app.qkd.key_exchange import ProcessingConfig, run_key_exchange

router = APIRouter(prefix="/crypto", tags=["crypto"])

class CryptoDemoRequest(BaseModel):
    plaintext: str = Field(
        default='{"from":"Bank A","to":"Bank B","amount":"1000.00","currency":"USD"}',
        min_length=1, max_length=4096,
        description="Fictional message only — never real account data",
    )
    associated_data: str = Field(default="demo-transaction", max_length=512)
    tamper: TamperMode = "none"
    n_qubits: int = Field(default=4096, ge=16, le=200_000)
    seed: int | None = Field(default=None, ge=0)
    eve_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    channel_noise: float = Field(default=0.0, ge=0.0, le=1.0)
    noise_model: Literal["depolarizing", "bit_phase_flip"] = "depolarizing"


@router.post("/demo")
def crypto_demo(request: CryptoDemoRequest, settings: Settings = Depends(get_settings)) -> dict:
    session_id = f"lab-{uuid.uuid4().hex[:12]}"
    result = run_key_exchange(
        request.n_qubits,
        channel=ChannelConfig(request.eve_probability, request.channel_noise, request.noise_model),
        processing=ProcessingConfig(
            qber_threshold=settings.qber_threshold, sample_fraction=settings.qber_sample_fraction
        ),
        seed=request.seed,
    )
    m = result.metrics()
    key_exchange = {
        "session_id": session_id,
        "accepted": m["accepted"],
        "abort_reason": m["abort_reason"],
        "estimated_qber": m["estimated_qber"],
        "final_key_length": m["final_key_length"],
    }
    if not result.accepted:
        return {
            "key_exchange": key_exchange,
            "status": "blocked",
            "detail": "QKD key was not established; the transaction is blocked and nothing is encrypted.",
        }

    bank_a, bank_b = establish_endpoints(result, session_id)
    aad = request.associated_data.encode()
    sent = bank_a.sender.encrypt(request.plaintext.encode(), aad)
    received = tamper_message(sent, request.tamper)

    receiver = bank_b.receiver
    if request.tamper == "wrong_key":
        # Correct key_id but a key from a different (unrelated) session: GCM must reject.
        other = run_key_exchange(4096, seed=(request.seed or 0) + 1_000_003)
        _, other_b = establish_endpoints(other, session_id + "-other")
        receiver = AEADReceiver(other_b.keys.receiving_key("bank_b"), bank_b.keys.key_id, "bank_a")

    outcome: dict = {"tamper": request.tamper}
    try:
        if request.tamper == "replay":
            receiver.decrypt(received)       # first delivery succeeds
            outcome["first_delivery"] = "verified"
        plaintext = receiver.decrypt(received)
        outcome.update(status="verified", plaintext=plaintext.decode())
    except AEADError as exc:
        outcome.update(status="rejected", error_type=type(exc).__name__, detail=str(exc))

    return {
        "key_exchange": key_exchange,
        "key_id": bank_a.keys.key_id,
        "algorithm": "AES-256-GCM (96-bit deterministic nonce, 128-bit tag), keys via HKDF-SHA256",
        "sent": sent.to_dict(),
        "delivered": received.to_dict(),
        "decryption": outcome,
        "status": outcome["status"],
    }
