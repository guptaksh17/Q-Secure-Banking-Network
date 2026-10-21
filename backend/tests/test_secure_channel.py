"""QKD key exchange -> HKDF -> AES-256-GCM between Bank A and Bank B."""

from dataclasses import replace

import numpy as np
import pytest

from app.crypto.aead import AEADError, AuthenticationError, KeyMismatchError
from app.crypto.kdf import derive_session_keys
from app.crypto.secure_channel import KeyNotEstablishedError, endpoint, establish_endpoints
from app.qkd.channel import ChannelConfig
from app.qkd.key_exchange import run_key_exchange

TXN = b'{"txn":"T-42","amount":"750.00","currency":"EUR"}'
AAD = b"txn=T-42|from=bank_a|to=bank_b"


@pytest.fixture(scope="module")
def accepted():
    r = run_key_exchange(4096, seed=1)
    assert r.accepted
    return r


def test_both_banks_derive_identical_keys(accepted):
    a, b = establish_endpoints(accepted, "s1")
    assert a.keys == b.keys


def test_bank_a_to_bank_b_and_back(accepted):
    a, b = establish_endpoints(accepted, "s1")
    assert b.receiver.decrypt(a.sender.encrypt(TXN, AAD)) == TXN
    ack = b"ack T-42"
    assert a.receiver.decrypt(b.sender.encrypt(ack, AAD)) == ack


def test_reflection_attack_rejected(accepted):
    """A message Bank A sent must not be accepted if bounced back to Bank A."""
    a, _ = establish_endpoints(accepted, "s1")
    with pytest.raises(AuthenticationError):
        a.receiver.decrypt(a.sender.encrypt(TXN, AAD))


def test_noisy_reconciled_session_still_interoperates():
    r = run_key_exchange(16_384, channel=ChannelConfig(noise=0.06), seed=2)
    assert r.accepted and r.metrics()["errors_before_reconciliation"] > 0
    a, b = establish_endpoints(r, "s2")
    assert b.receiver.decrypt(a.sender.encrypt(TXN, AAD)) == TXN


def test_one_bit_key_disagreement_means_rejection_not_wrong_plaintext(accepted):
    a, _ = establish_endpoints(accepted, "s1")
    bad = accepted.bob_final_key.copy()
    bad[17] ^= 1
    bad_b = endpoint("bank_b", derive_session_keys(bad, "s1"))
    with pytest.raises(KeyMismatchError):
        bad_b.receiver.decrypt(a.sender.encrypt(TXN, AAD))
    # even if an attacker rewrote key_id to match, GCM authentication still fails
    m = a.sender.encrypt(TXN, AAD)
    with pytest.raises(AuthenticationError):
        bad_b.receiver.decrypt(replace(m, key_id=bad_b.keys.key_id))


def test_messages_do_not_cross_sessions(accepted):
    a1, _ = establish_endpoints(accepted, "s1")
    _, b2 = establish_endpoints(accepted, "s-other")
    with pytest.raises(AEADError):
        b2.receiver.decrypt(a1.sender.encrypt(TXN, AAD))


@pytest.mark.parametrize("channel", [ChannelConfig(eve_probability=1.0), ChannelConfig(noise=0.4)])
def test_aborted_exchange_blocks_encryption(channel):
    r = run_key_exchange(4096, channel=channel, seed=3)
    assert not r.accepted
    with pytest.raises(KeyNotEstablishedError):
        establish_endpoints(r, "s3")


def test_independent_sessions_have_independent_keys():
    k1 = establish_endpoints(run_key_exchange(4096, seed=4), "s")[0].keys
    k2 = establish_endpoints(run_key_exchange(4096, seed=5), "s")[0].keys
    assert k1.bank_a_to_bank_b != k2.bank_a_to_bank_b


def test_ciphertext_reveals_no_plaintext_bytes(accepted):
    a, _ = establish_endpoints(accepted, "s1")
    m = a.sender.encrypt(TXN * 20, AAD)
    assert b"amount" not in m.ciphertext and b"EUR" not in m.ciphertext
    # ciphertext bytes should look uniform
    ct = np.frombuffer(m.ciphertext, dtype=np.uint8)
    assert abs(np.unpackbits(ct).mean() - 0.5) < 0.05
