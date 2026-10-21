"""Persist QKD session metrics and security events. Never receives key material."""

from sqlalchemy.orm import Session

from app.db.models import EventType, QKDSessionRecord, SecurityEvent, Severity
from app.qkd.key_exchange import AbortReason, KeyExchangeResult


def log_event(
    db: Session,
    event_type: EventType,
    severity: Severity,
    message: str,
    *,
    qkd_session_id: str | None = None,
    transaction_id: str | None = None,
    details: dict | None = None,
) -> SecurityEvent:
    event = SecurityEvent(
        event_type=event_type.value,
        severity=severity.value,
        message=message[:300],
        qkd_session_id=qkd_session_id,
        transaction_id=transaction_id,
        details=details or {},
    )
    db.add(event)
    db.flush()
    return event


def record_key_exchange(
    db: Session,
    result: KeyExchangeResult,
    *,
    purpose: str,
    key_id: str | None = None,
    session_id: str | None = None,
    transaction_id: str | None = None,
) -> QKDSessionRecord:
    """Store session parameters + metrics and log the accept/abort events."""
    m = result.metrics()
    record = QKDSessionRecord(
        purpose=purpose,
        n_qubits=m["n_qubits"],
        backend=m["backend"],
        simulation_kind=m["simulation_kind"],
        seed=m["seed"],
        eve_probability=m["eve_probability"],
        channel_noise=m["channel_noise"],
        noise_model=m["noise_model"],
        qber_threshold=m["qber_threshold"],
        sample_fraction=m["sample_fraction"],
        sifted_key_length=m["sifted_key_length"],
        test_sample_size=m["test_sample_size"],
        test_sample_errors=m["test_sample_errors"],
        estimated_qber=m["estimated_qber"],
        true_qber=m["true_sifted_error_rate"],
        final_key_length=m["final_key_length"],
        accepted=m["accepted"],
        abort_reason=m["abort_reason"],
        key_id=key_id,
        metrics=m,
    )
    if session_id:
        record.id = session_id
    db.add(record)
    db.flush()

    summary = {
        "estimated_qber": round(m["estimated_qber"], 4),
        "threshold": m["qber_threshold"],
        "test_sample_size": m["test_sample_size"],
        "final_key_length": m["final_key_length"],
    }
    ids = {"qkd_session_id": record.id, "transaction_id": transaction_id}
    if result.accepted:
        log_event(db, EventType.QKD_SESSION_ACCEPTED, Severity.INFO,
                  f"QKD key accepted: QBER {m['estimated_qber']:.2%}, "
                  f"{m['final_key_length']} final key bits", details=summary, **ids)
        return record

    if result.abort_reason is AbortReason.QBER_ABOVE_THRESHOLD:
        log_event(db, EventType.HIGH_QBER_DETECTED, Severity.CRITICAL,
                  f"Estimated QBER {m['estimated_qber']:.2%} exceeds threshold "
                  f"{m['qber_threshold']:.0%}: disturbance consistent with eavesdropping "
                  "or excess channel noise", details=summary, **ids)
    log_event(db, EventType.QKD_SESSION_ABORTED, Severity.WARNING,
              f"QKD session aborted ({m['abort_reason']}); no key established",
              details=summary, **ids)
    return record
