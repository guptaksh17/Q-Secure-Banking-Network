"""Transfer workflow service: lifecycle, validation, events, persistence."""

import json

import pytest
from sqlalchemy import select

from app.db.models import QKDSessionRecord, SecurityEvent, Transaction, TransactionStatus
from app.qkd.channel import ChannelConfig
from app.services.transfers import (
    SimulationOptions,
    TransferRequest,
    TransferValidationError,
    format_cents,
    parse_amount,
    submit_transfer,
)

REQ = TransferRequest("QSB-A-1001", "QSB-B-2001", "1250.50", "EUR", "invoice 7")


def _events(db, txn):
    return [e.event_type for e in db.scalars(
        select(SecurityEvent).where(SecurityEvent.transaction_id == txn.id).order_by(SecurityEvent.id))]


# --- happy path ------------------------------------------------------------------

def test_clean_transfer_is_delivered(db):
    txn = submit_transfer(db, REQ, SimulationOptions(seed=1))
    assert txn.status == TransactionStatus.DELIVERED.value
    assert txn.tag_verified is True and txn.delivered_at is not None
    assert txn.amount_cents == 125050 and txn.sender_bank == "bank_a" and txn.receiver_bank == "bank_b"
    assert len(bytes.fromhex(txn.nonce)) == 12 and len(bytes.fromhex(txn.auth_tag)) == 16
    assert txn.ciphertext and "1250.50" not in bytes.fromhex(txn.ciphertext).decode("latin-1")
    assert _events(db, txn) == [
        "transaction_created", "qkd_session_accepted", "transaction_encrypted",
        "auth_tag_verified", "transaction_delivered",
    ]


def test_reverse_direction_bank_b_to_bank_a(db):
    req = TransferRequest("QSB-B-0007", "QSB-A-0042", "10.00")
    txn = submit_transfer(db, req, SimulationOptions(seed=2))
    assert txn.status == "delivered" and txn.sender_bank == "bank_b"
    assert bytes.fromhex(txn.nonce)[:4] == b"QSBB"  # Bank B's nonce space


def test_qkd_session_is_linked_and_stored(db):
    txn = submit_transfer(db, REQ, SimulationOptions(seed=3))
    s = db.get(QKDSessionRecord, txn.qkd_session_id)
    assert s.purpose == "transfer" and s.accepted and s.key_id == txn.key_id
    assert s.final_key_length >= 256 and s.n_qubits == 4096
    assert s.metrics["final_keys_match"] is True


def test_associated_data_binds_routing_metadata(db):
    txn = submit_transfer(db, REQ, SimulationOptions(seed=4))
    aad = json.loads(txn.associated_data)
    assert aad == {
        "version": 1, "reference": txn.reference, "sender_bank": "bank_a",
        "receiver_bank": "bank_b", "qkd_session_id": txn.qkd_session_id, "key_id": txn.key_id,
    }


# --- attacks -----------------------------------------------------------------------

def test_eavesdropper_blocks_transfer_before_encryption(db):
    txn = submit_transfer(db, REQ, SimulationOptions(seed=5, channel=ChannelConfig(eve_probability=1.0)))
    assert txn.status == "blocked" and txn.failure_reason == "qber_above_threshold"
    assert txn.ciphertext is None and txn.nonce is None and txn.key_id is None
    events = _events(db, txn)
    assert "high_qber_detected" in events and events[-1] == "transaction_blocked"
    assert "transaction_encrypted" not in events


def test_high_qber_event_does_not_claim_proof_of_eve(db):
    txn = submit_transfer(db, REQ, SimulationOptions(seed=6, channel=ChannelConfig(noise=0.5)))
    ev = db.scalars(select(SecurityEvent).where(
        SecurityEvent.transaction_id == txn.id, SecurityEvent.event_type == "high_qber_detected")).one()
    assert ev.severity == "critical"
    assert "eavesdropping or excess channel noise" in ev.message


@pytest.mark.parametrize("mode", ["ciphertext", "tag", "nonce", "aad", "wrong_key"])
def test_tampering_is_rejected_by_receiving_bank(db, mode):
    txn = submit_transfer(db, REQ, SimulationOptions(seed=7, tamper=mode))
    assert txn.status == "rejected" and txn.tag_verified is False
    assert txn.failure_reason == "AuthenticationError" and txn.delivered_at is None
    events = _events(db, txn)
    assert events[-3:] == ["tampering_simulated", "auth_tag_failed", "transaction_rejected"]


def test_replay_is_rejected_and_transfer_recorded_once(db):
    txn = submit_transfer(db, REQ, SimulationOptions(seed=8, tamper="replay"))
    assert txn.status == "delivered"
    events = _events(db, txn)
    assert events.count("transaction_delivered") == 1 and events[-1] == "replay_rejected"


def test_unknown_tamper_mode_rejected(db):
    with pytest.raises(TransferValidationError):
        submit_transfer(db, REQ, SimulationOptions(tamper="quantum_magic"))


# --- nonce/key uniqueness across stored transactions --------------------------------

def test_key_nonce_pairs_unique_across_all_transactions(db):
    for s in range(8):
        submit_transfer(db, REQ, SimulationOptions(seed=100 + s))
    rows = db.execute(select(Transaction.key_id, Transaction.nonce)
                      .where(Transaction.nonce.is_not(None))).all()
    assert len(rows) == 8
    assert len(set(rows)) == 8                 # (key, nonce) never repeats
    assert len({k for k, _ in rows}) == 8      # fresh key per transfer


# --- validation ----------------------------------------------------------------------

@pytest.mark.parametrize("sender, receiver", [
    ("QSB-A-1001", "QSB-A-2002"),        # same bank
    ("123456789", "QSB-B-2001"),         # real-looking account number
    ("QSB-C-1001", "QSB-B-2001"),        # unknown bank
    ("QSB-A-100", "QSB-B-2001"),         # wrong length
    ("qsb-a-1001", "QSB-B-2001"),        # case-sensitive
])
def test_account_validation(db, sender, receiver):
    with pytest.raises(TransferValidationError):
        submit_transfer(db, TransferRequest(sender, receiver, "10.00"))


@pytest.mark.parametrize("amount", ["0", "0.00", "0.001", "-5", "1e3", "1,000", "abc", "1000000.01", ""])
def test_bad_amounts_rejected(amount):
    with pytest.raises(TransferValidationError):
        parse_amount(amount)


@pytest.mark.parametrize("amount, cents", [("0.01", 1), ("10", 1000), ("10.5", 1050), ("1000000.00", 100_000_000)])
def test_amount_parsing(amount, cents):
    assert parse_amount(amount) == cents
    assert parse_amount(format_cents(cents)) == cents


def test_bad_currency_and_long_memo(db):
    with pytest.raises(TransferValidationError):
        submit_transfer(db, TransferRequest("QSB-A-1001", "QSB-B-2001", "1.00", "BTC"))
    with pytest.raises(TransferValidationError):
        submit_transfer(db, TransferRequest("QSB-A-1001", "QSB-B-2001", "1.00", memo="x" * 141))


def test_validation_failure_writes_nothing(db):
    with pytest.raises(TransferValidationError):
        submit_transfer(db, TransferRequest("QSB-A-1001", "QSB-A-2001", "1.00"))
    assert db.scalar(select(Transaction).limit(1)) is None
    assert db.scalar(select(SecurityEvent).limit(1)) is None


def test_references_are_unique(db):
    refs = {submit_transfer(db, REQ, SimulationOptions(seed=200 + i)).reference for i in range(5)}
    assert len(refs) == 5
