"""HKDF-SHA256 key derivation from the QKD final key."""

import numpy as np
import pytest

from app.crypto.kdf import (
    KeyDerivationError,
    bits_to_bytes,
    derive_session_keys,
    hkdf_sha256,
)


def _key_bits(n=512, seed=0):
    return np.random.default_rng(seed).integers(0, 2, n, dtype=np.uint8)


def test_hkdf_matches_rfc5869_test_case_1():
    okm = hkdf_sha256(
        ikm=bytes([0x0B]) * 22, info=bytes(range(0xF0, 0xFA)), length=42, salt=bytes(range(13))
    )
    assert okm.hex() == (
        "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"
    )


def test_bits_to_bytes_big_endian_and_drops_partial_byte():
    assert bits_to_bytes(np.array([1, 0, 0, 0, 0, 0, 0, 1], np.uint8)) == b"\x81"
    assert bits_to_bytes(np.array([1] * 8 + [1, 1, 1], np.uint8)) == b"\xff"
    with pytest.raises(KeyDerivationError):
        bits_to_bytes(np.array([0, 2], np.uint8))


def test_derived_keys_have_correct_sizes_and_are_deterministic():
    k1 = derive_session_keys(_key_bits(), "s1")
    k2 = derive_session_keys(_key_bits(), "s1")
    assert len(k1.bank_a_to_bank_b) == len(k1.bank_b_to_bank_a) == 32
    assert len(bytes.fromhex(k1.key_id)) == 8
    assert k1 == k2


def test_directions_are_domain_separated():
    k = derive_session_keys(_key_bits(), "s1")
    assert k.bank_a_to_bank_b != k.bank_b_to_bank_a
    assert k.sending_key("bank_a") == k.receiving_key("bank_b") == k.bank_a_to_bank_b
    assert k.sending_key("bank_b") == k.receiving_key("bank_a") == k.bank_b_to_bank_a


def test_session_id_and_key_material_change_all_outputs():
    base = derive_session_keys(_key_bits(), "s1")
    other_session = derive_session_keys(_key_bits(), "s2")
    flipped = _key_bits()
    flipped[0] ^= 1
    other_key = derive_session_keys(flipped, "s1")
    for variant in (other_session, other_key):
        assert variant.key_id != base.key_id
        assert variant.bank_a_to_bank_b != base.bank_a_to_bank_b
        assert variant.bank_b_to_bank_a != base.bank_b_to_bank_a


def test_key_id_is_not_a_prefix_of_any_key():
    k = derive_session_keys(_key_bits(), "s1")
    kid = bytes.fromhex(k.key_id)
    assert not k.bank_a_to_bank_b.startswith(kid) and not k.bank_b_to_bank_a.startswith(kid)


def test_repr_never_shows_key_bytes():
    k = derive_session_keys(_key_bits(), "s1")
    text = repr(k) + str(k)
    assert k.bank_a_to_bank_b.hex() not in text and k.bank_b_to_bank_a.hex() not in text
    assert k.key_id in text


@pytest.mark.parametrize("bits, sid", [
    (np.zeros(255, np.uint8), "s"),   # too short for AES-256
    (_key_bits(), ""),                # empty session id
    (_key_bits(), "a|b"),             # delimiter injection into the HKDF label
])
def test_rejects_bad_inputs(bits, sid):
    with pytest.raises(KeyDerivationError):
        derive_session_keys(bits, sid)


def test_rejects_missing_key():
    with pytest.raises(KeyDerivationError):
        derive_session_keys(None, "s1")
