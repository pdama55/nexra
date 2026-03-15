"""Unit tests for core.crypto — API keys, HMAC, AES-GCM, SHA-256."""

import json

import pytest

from core.crypto import (
    decrypt_aes_gcm,
    encrypt_aes_gcm,
    generate_api_key,
    generate_org_jwt_secret,
    sha256_json,
    sign_webhook_payload,
    verify_api_key,
    verify_webhook_signature,
)


class TestAPIKeyGeneration:
    def test_generate_api_key_format(self) -> None:
        raw, hashed, prefix = generate_api_key()
        assert raw.startswith("nx_live_")
        assert len(raw) > 16
        assert prefix == raw[:16]
        assert hashed.startswith("$2b$12$")

    def test_verify_api_key_valid(self) -> None:
        raw, hashed, _ = generate_api_key()
        assert verify_api_key(raw, hashed) is True

    def test_verify_api_key_invalid(self) -> None:
        _, hashed, _ = generate_api_key()
        assert verify_api_key("nx_live_wrong_key_here", hashed) is False

    def test_generate_api_key_unique(self) -> None:
        key1 = generate_api_key()[0]
        key2 = generate_api_key()[0]
        assert key1 != key2


class TestHMACWebhookSigning:
    def test_sign_and_verify_roundtrip(self) -> None:
        payload = {"delegation_id": "del_123", "task": {"type": "research"}}
        secret = "webhook_secret_abc"

        signature = sign_webhook_payload(payload, secret)
        assert signature.startswith("sha256=")

        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        assert verify_webhook_signature(body, secret, signature) is True

    def test_verify_rejects_wrong_secret(self) -> None:
        payload = {"key": "value"}
        signature = sign_webhook_payload(payload, "correct_secret")

        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        assert verify_webhook_signature(body, "wrong_secret", signature) is False

    def test_verify_rejects_tampered_payload(self) -> None:
        payload = {"key": "value"}
        secret = "my_secret"
        signature = sign_webhook_payload(payload, secret)

        tampered = json.dumps({"key": "tampered"}, separators=(",", ":"), sort_keys=True).encode()
        assert verify_webhook_signature(tampered, secret, signature) is False

    def test_sign_deterministic(self) -> None:
        payload = {"b": 2, "a": 1}
        secret = "s"
        assert sign_webhook_payload(payload, secret) == sign_webhook_payload(payload, secret)


class TestAESGCMEncryption:
    KEY = "a" * 64  # 64 hex chars = 32 bytes

    def test_encrypt_decrypt_roundtrip(self) -> None:
        plaintext = "my-secret-jwt-key-256bit"
        encrypted = encrypt_aes_gcm(plaintext, self.KEY)
        decrypted = decrypt_aes_gcm(encrypted, self.KEY)
        assert decrypted == plaintext

    def test_encrypted_is_hex(self) -> None:
        encrypted = encrypt_aes_gcm("test", self.KEY)
        int(encrypted, 16)  # raises ValueError if not valid hex

    def test_nonce_makes_ciphertext_unique(self) -> None:
        plaintext = "same-plaintext"
        enc1 = encrypt_aes_gcm(plaintext, self.KEY)
        enc2 = encrypt_aes_gcm(plaintext, self.KEY)
        assert enc1 != enc2  # different nonces

    def test_decrypt_fails_with_wrong_key(self) -> None:
        encrypted = encrypt_aes_gcm("data", self.KEY)
        wrong_key = "b" * 64
        with pytest.raises(Exception):
            decrypt_aes_gcm(encrypted, wrong_key)

    def test_generate_org_jwt_secret_format(self) -> None:
        secret = generate_org_jwt_secret()
        assert len(secret) == 64
        int(secret, 16)  # valid hex


class TestSHA256JSON:
    def test_deterministic(self) -> None:
        data = {"b": 2, "a": 1}
        assert sha256_json(data) == sha256_json(data)

    def test_key_order_independent(self) -> None:
        assert sha256_json({"a": 1, "b": 2}) == sha256_json({"b": 2, "a": 1})

    def test_different_data_different_hash(self) -> None:
        assert sha256_json({"a": 1}) != sha256_json({"a": 2})

    def test_returns_64_char_hex(self) -> None:
        h = sha256_json({"key": "value"})
        assert len(h) == 64
        int(h, 16)
