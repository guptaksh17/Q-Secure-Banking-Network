import pytest


def _demo(client, **kwargs):
    r = client.post("/api/crypto/demo", json={"seed": 1, **kwargs})
    assert r.status_code == 200, r.text
    return r.json()


def test_untampered_message_is_verified_and_decrypted(client):
    body = _demo(client, plaintext="hello Bank B")
    assert body["status"] == "verified"
    assert body["decryption"]["plaintext"] == "hello Bank B"
    assert body["key_exchange"]["accepted"]
    sent = body["sent"]
    assert len(bytes.fromhex(sent["nonce"])) == 12 and len(bytes.fromhex(sent["tag"])) == 16
    assert sent == body["delivered"]


@pytest.mark.parametrize("mode, error", [
    ("ciphertext", "AuthenticationError"),
    ("tag", "AuthenticationError"),
    ("nonce", "AuthenticationError"),
    ("aad", "AuthenticationError"),
    ("wrong_key", "AuthenticationError"),
    ("replay", "ReplayError"),
])
def test_tampering_is_rejected(client, mode, error):
    body = _demo(client, tamper=mode)
    assert body["status"] == "rejected"
    assert body["decryption"]["error_type"] == error
    assert "plaintext" not in body["decryption"]
    if mode in ("ciphertext", "tag", "nonce", "aad"):
        assert body["sent"][mode] != body["delivered"][mode]


def test_replay_first_delivery_succeeds(client):
    assert _demo(client, tamper="replay")["decryption"]["first_delivery"] == "verified"


def test_attacked_channel_blocks_transaction(client):
    body = _demo(client, eve_probability=1.0)
    assert body["status"] == "blocked"
    assert body["key_exchange"]["abort_reason"] == "qber_above_threshold"
    assert "sent" not in body


def test_response_contains_no_key_material(client):
    body = _demo(client)
    def keys(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield prefix + k
                yield from keys(v, prefix + k + ".")
    names = set(keys(body))
    assert not any(n.endswith(("final_key", "aes_key", "bank_a_to_bank_b", "bank_b_to_bank_a")) for n in names)
    assert body["key_id"] and len(body["key_id"]) == 16


@pytest.mark.parametrize("payload", [{"plaintext": ""}, {"tamper": "bitflip"}, {"plaintext": "x" * 5000}])
def test_bad_requests_rejected(client, payload):
    assert client.post("/api/crypto/demo", json=payload).status_code == 422
