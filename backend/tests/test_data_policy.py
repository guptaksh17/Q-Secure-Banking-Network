"""Enforce the data policy: no raw/final/derived key material is ever persisted.

Captures every key the run derives, then searches the raw SQLite file bytes for it in
binary, hex (both cases) and bit-string form.
"""

import numpy as np
import pytest
from sqlalchemy import inspect

from app.crypto.kdf import bits_to_bytes
from app.db.database import Database
from app.qkd.channel import ChannelConfig
from app.services import transfers
from app.services.transfers import SimulationOptions, TransferRequest, submit_transfer


def _forms(secret: bytes) -> list[bytes]:
    return [secret, secret.hex().encode(), secret.hex().upper().encode()]


def test_no_key_material_in_database_file(tmp_path, monkeypatch):
    captured = []
    real = transfers.establish_endpoints

    def spy(result, session_id):
        a, b = real(result, session_id)
        captured.append((result, a.keys))
        return a, b

    monkeypatch.setattr(transfers, "establish_endpoints", spy)

    path = tmp_path / "policy.db"
    database = Database(f"sqlite:///{path}")
    database.create_all()
    req = TransferRequest("QSB-A-1001", "QSB-B-2001", "99.99", "USD", "policy check")
    with database.session() as db:
        for seed, tamper in [(1, "none"), (2, "tag"), (3, "replay"), (4, "none")]:
            submit_transfer(db, req, SimulationOptions(seed=seed, tamper=tamper))
        submit_transfer(db, req, SimulationOptions(seed=5, channel=ChannelConfig(noise=0.06), n_qubits=16_384))
    database.dispose()

    assert len(captured) == 5
    blob = path.read_bytes()
    for result, keys in captured:
        for secret in (keys.bank_a_to_bank_b, keys.bank_b_to_bank_a,
                       bits_to_bytes(result.alice_final_key), bits_to_bytes(result.bob_final_key)):
            for form in _forms(secret):
                assert form not in blob
        # first 64 bits of the final key and of the reconciled key as '0101...' text
        for bits in (result.alice_final_key, result.estimate.alice_remaining):
            assert "".join(map(str, bits[:64].tolist())).encode() not in blob
        assert keys.key_id.encode() in blob  # sanity: the public id IS stored


def test_schema_has_no_key_columns(database):
    """Only the public key_id and integer *_length counters may mention 'key'."""
    from sqlalchemy import Integer

    insp = inspect(database.engine)
    for table in insp.get_table_names():
        for col in insp.get_columns(table):
            name = col["name"].lower()
            if "key" not in name:
                continue
            is_counter = name.endswith("_length") and isinstance(col["type"], Integer)
            assert name == "key_id" or is_counter, f"{table}.{col['name']} looks like key storage"


@pytest.mark.parametrize("field", ["alice_final_key", "bob_final_key", "alice_key", "bob_key"])
def test_stored_metrics_json_has_no_key_fields(db, field):
    from app.db.models import QKDSessionRecord
    submit_transfer(db, TransferRequest("QSB-A-1001", "QSB-B-2001", "5.00"), SimulationOptions(seed=9))
    record = db.query(QKDSessionRecord).one()
    assert field not in str(record.metrics)

    def max_list(obj):
        if isinstance(obj, dict):
            return max([max_list(v) for v in obj.values()] or [0])
        if isinstance(obj, (list, tuple, np.ndarray)):
            return len(obj)
        return 0
    assert max_list(record.metrics) <= 16
