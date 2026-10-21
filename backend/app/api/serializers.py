"""ORM -> JSON. Every field here is public by design; there is no key material to leak."""

from app.api.deps import iso
from app.db.models import ExperimentResult, QKDSessionRecord, SecurityEvent, Transaction
from app.services.transfers import format_cents


def session_out(s: QKDSessionRecord, full: bool = False) -> dict:
    out = {
        "id": s.id,
        "created_at": iso(s.created_at),
        "purpose": s.purpose,
        "n_qubits": s.n_qubits,
        "backend": s.backend,
        "simulation_kind": s.simulation_kind,
        "seed": s.seed,
        "eve_probability": s.eve_probability,
        "channel_noise": s.channel_noise,
        "noise_model": s.noise_model,
        "qber_threshold": s.qber_threshold,
        "sample_fraction": s.sample_fraction,
        "sifted_key_length": s.sifted_key_length,
        "test_sample_size": s.test_sample_size,
        "test_sample_errors": s.test_sample_errors,
        "estimated_qber": s.estimated_qber,
        "true_qber": s.true_qber,
        "final_key_length": s.final_key_length,
        "accepted": s.accepted,
        "abort_reason": s.abort_reason,
        "key_id": s.key_id,
    }
    if full:
        out["metrics"] = s.metrics
    return out


def transaction_out(t: Transaction, full: bool = False) -> dict:
    out = {
        "id": t.id,
        "reference": t.reference,
        "created_at": iso(t.created_at),
        "updated_at": iso(t.updated_at),
        "status": t.status,
        "failure_reason": t.failure_reason,
        "sender_bank": t.sender_bank,
        "receiver_bank": t.receiver_bank,
        "sender_account": t.sender_account,
        "receiver_account": t.receiver_account,
        "amount": format_cents(t.amount_cents),
        "currency": t.currency,
        "memo": t.memo,
        "tamper_mode": t.tamper_mode,
        "qkd_session_id": t.qkd_session_id,
        "key_id": t.key_id,
        "tag_verified": t.tag_verified,
        "delivered_at": iso(t.delivered_at),
    }
    if full:
        out["encryption"] = {
            "algorithm": "AES-256-GCM",
            "nonce": t.nonce,
            "ciphertext": t.ciphertext,
            "auth_tag": t.auth_tag,
            "associated_data": t.associated_data,
        }
    return out


def event_out(e: SecurityEvent) -> dict:
    return {
        "id": e.id,
        "created_at": iso(e.created_at),
        "event_type": e.event_type,
        "severity": e.severity,
        "message": e.message,
        "qkd_session_id": e.qkd_session_id,
        "transaction_id": e.transaction_id,
        "details": e.details,
    }


def experiment_out(x: ExperimentResult, full: bool = False) -> dict:
    out = {
        "id": x.id,
        "created_at": iso(x.created_at),
        "name": x.name,
        "kind": x.kind,
        "parameter": x.parameter,
        "config": x.config,
        "n_points": len(x.points),
    }
    if full:
        out["points"] = x.points
    return out
