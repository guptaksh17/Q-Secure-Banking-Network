"""AES-256-GCM: correctness, tamper detection, nonce uniqueness, replay rejection."""

import os
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.crypto.aead import (
    MAX_COUNTER,
    AEADReceiver,
    AEADSender,
    AuthenticationError,
    EncryptedMessage,
    KeyMismatchError,
    NonceExhaustedError,
    ReplayError,
)

KEY = bytes(range(32))
KID = "00112233aabbccdd"
PLAINTEXT = b'{"txn":"T-001","from":"Bank A","to":"Bank B","amount":"2500.00","currency":"USD"}'
AAD = b"txn=T-001|from=bank_a|to=bank_b|session=s1"


def _pair(key=KEY):
    return AEADSender(key, KID, "bank_a"), AEADReceiver(key, KID, "bank_a")


# --- library sanity: published AES-256-GCM vectors (McGrew & Viega, cases 13/14) ----

def test_aes256gcm_reference_vectors():
    k, iv = bytes(32), bytes(12)
    assert AESGCM(k).encrypt(iv, b"", None).hex() == "530f8afbc74536b9a963b4f1c4cb738b"
    assert AESGCM(k).encrypt(iv, bytes(16), None).hex() == (
        "cea7403d4d606b6e074ec5d3baf39d18" "d0d1c8a799996bf0265b98b5d48ab919"
    )


# --- correctness --------------------------------------------------------------

@pytest.mark.parametrize("plaintext", [b"", b"x", PLAINTEXT, os.urandom(10_000)])
def test_roundtrip_recovers_plaintext(plaintext):
    s, r = _pair()
    assert r.decrypt(s.encrypt(plaintext, AAD)) == plaintext


def test_ciphertext_length_and_tag_size():
    m = _pair()[0].encrypt(PLAINTEXT, AAD)
    assert len(m.ciphertext) == len(PLAINTEXT)   # GCM is a stream mode: no padding
    assert len(m.tag) == 16 and len(m.nonce) == 12
    assert m.ciphertext != PLAINTEXT


def test_same_plaintext_encrypts_differently_each_time():
    s, _ = _pair()
    a, b = s.encrypt(PLAINTEXT, AAD), s.encrypt(PLAINTEXT, AAD)
    assert a.nonce != b.nonce and a.ciphertext != b.ciphertext


def test_serialisation_roundtrip():
    s, r = _pair()
    m = s.encrypt(PLAINTEXT, AAD)
    restored = EncryptedMessage.from_dict(m.to_dict())
    assert restored == m
    assert r.decrypt(restored) == PLAINTEXT


# --- tamper detection: every single-bit flip must be rejected -------------------

@pytest.mark.parametrize("field", ["ciphertext", "tag", "nonce", "aad"])
def test_any_single_bit_flip_is_rejected(field):
    s, _ = _pair()
    m = s.encrypt(PLAINTEXT, AAD)
    original = getattr(m, field)
    for byte_index in range(len(original)):
        for bit in (0, 7):
            tampered = bytearray(original)
            tampered[byte_index] ^= 1 << bit
            r = AEADReceiver(KEY, KID, "bank_a")
            with pytest.raises(AuthenticationError):
                r.decrypt(replace(m, **{field: bytes(tampered)}))


def test_truncated_or_extended_ciphertext_rejected():
    s, _ = _pair()
    m = s.encrypt(PLAINTEXT, AAD)
    for ct in (m.ciphertext[:-1], m.ciphertext + b"\x00", b""):
        with pytest.raises(AuthenticationError):
            AEADReceiver(KEY, KID, "bank_a").decrypt(replace(m, ciphertext=ct))


def test_truncated_tag_rejected():
    m = _pair()[0].encrypt(PLAINTEXT, AAD)
    with pytest.raises(AuthenticationError):
        AEADReceiver(KEY, KID, "bank_a").decrypt(replace(m, tag=m.tag[:12]))


def test_wrong_key_rejected():
    m = _pair()[0].encrypt(PLAINTEXT, AAD)
    with pytest.raises(AuthenticationError):
        AEADReceiver(bytes(32), KID, "bank_a").decrypt(m)


def test_key_id_mismatch_rejected_before_decryption():
    m = _pair()[0].encrypt(PLAINTEXT, AAD)
    with pytest.raises(KeyMismatchError):
        AEADReceiver(KEY, "ffffffffffffffff", "bank_a").decrypt(m)


def test_unknown_version_rejected():
    m = _pair()[0].encrypt(PLAINTEXT, AAD)
    with pytest.raises(AuthenticationError):
        AEADReceiver(KEY, KID, "bank_a").decrypt(replace(m, version=2))


def test_message_from_unexpected_sender_rejected():
    """A Bank B-originated nonce must not be accepted by a receiver expecting Bank A."""
    m = AEADSender(KEY, KID, "bank_b").encrypt(PLAINTEXT, AAD)
    with pytest.raises(AuthenticationError):
        AEADReceiver(KEY, KID, "bank_a").decrypt(m)


# --- nonce uniqueness ------------------------------------------------------------

def test_nonces_unique_over_many_encryptions():
    s, _ = _pair()
    nonces = [s.encrypt(b"m", b"").nonce for _ in range(20_000)]
    assert len(set(nonces)) == len(nonces)
    assert s.messages_sent == 20_000


def test_nonce_structure_is_sender_field_plus_counter():
    s, _ = _pair()
    for i in range(3):
        n = s.encrypt(b"m").nonce
        assert n[:4] == b"QSBA" and int.from_bytes(n[4:], "big") == i


def test_banks_use_distinct_nonce_spaces():
    a = AEADSender(KEY, KID, "bank_a").encrypt(b"m").nonce
    b = AEADSender(KEY, KID, "bank_b").encrypt(b"m").nonce
    assert a != b and a[4:] == b[4:]  # same counter, different fixed field


def test_counter_exhaustion_refuses_to_reuse_nonce():
    s = AEADSender(KEY, KID, "bank_a", start_counter=MAX_COUNTER)
    s.encrypt(b"last allowed")
    with pytest.raises(NonceExhaustedError):
        s.encrypt(b"would wrap")


def test_encrypt_api_does_not_accept_caller_nonce():
    s, _ = _pair()
    with pytest.raises(TypeError):
        s.encrypt(b"m", b"", nonce=bytes(12))  # type: ignore[call-arg]


# --- replay ---------------------------------------------------------------------

def test_replay_rejected():
    s, r = _pair()
    m = s.encrypt(PLAINTEXT, AAD)
    assert r.decrypt(m) == PLAINTEXT
    with pytest.raises(ReplayError):
        r.decrypt(m)


def test_forged_message_does_not_poison_replay_cache():
    s, r = _pair()
    m = s.encrypt(PLAINTEXT, AAD)
    with pytest.raises(AuthenticationError):
        r.decrypt(replace(m, tag=bytes(16)))
    assert r.decrypt(m) == PLAINTEXT  # genuine message still accepted


def test_out_of_order_delivery_is_allowed():
    s, r = _pair()
    m1, m2 = s.encrypt(b"one"), s.encrypt(b"two")
    assert r.decrypt(m2) == b"two" and r.decrypt(m1) == b"one"


# --- construction ---------------------------------------------------------------

@pytest.mark.parametrize("key", [b"", bytes(16), bytes(24), bytes(33)])
def test_only_256_bit_keys_accepted(key):
    with pytest.raises(ValueError):
        AEADSender(key, KID, "bank_a")
    with pytest.raises(ValueError):
        AEADReceiver(key, KID, "bank_a")


def test_repr_hides_key():
    s, r = _pair()
    assert KEY.hex() not in repr(s) + repr(r)
