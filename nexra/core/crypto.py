import hashlib
import hmac
import json
import os
import secrets

import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ─── API Key Generation ───────────────────────────────────────


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (raw_key, bcrypt_hash, prefix).
        raw_key is returned to the user exactly once.
        bcrypt_hash is stored in the database.
        prefix (first 16 chars) is stored for O(1) lookup.
    """
    raw = "nx_live_" + secrets.token_urlsafe(32)
    hashed = bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    prefix = raw[:16]
    return raw, hashed, prefix


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Verify a raw API key against its bcrypt hash."""
    return bcrypt.checkpw(raw_key.encode("utf-8"), stored_hash.encode("utf-8"))


# ─── HMAC Webhook Signing ─────────────────────────────────────


def sign_webhook_payload(payload: dict, secret: str) -> str:
    """Sign a webhook payload with HMAC-SHA256.

    Returns 'sha256=<hex_digest>' for the X-Nexra-Signature header.
    Payload is serialized with sorted keys and no whitespace for deterministic signing.
    """
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def verify_webhook_signature(payload_bytes: bytes, secret: str, signature: str) -> bool:
    """Verify an incoming webhook signature.

    Uses hmac.compare_digest for constant-time comparison.
    """
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ─── AES-256-GCM Encryption ──────────────────────────────────


def generate_org_jwt_secret() -> str:
    """Generate a 256-bit random secret for signing delegation JWTs.

    Returns the raw hex string (64 chars = 32 bytes).
    This value must be encrypted before storage.
    """
    return secrets.token_hex(32)


def encrypt_aes_gcm(plaintext: str, encryption_key_hex: str) -> str:
    """Encrypt a string using AES-256-GCM.

    Args:
        plaintext: The string to encrypt.
        encryption_key_hex: 64-char hex string (32 bytes).

    Returns:
        Hex-encoded string: nonce (24 chars) + ciphertext.
    """
    key = bytes.fromhex(encryption_key_hex)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return (nonce + ciphertext).hex()


def decrypt_aes_gcm(encrypted_hex: str, encryption_key_hex: str) -> str:
    """Decrypt an AES-256-GCM encrypted string.

    Raises:
        cryptography.exceptions.InvalidTag: If the key is wrong or data is tampered.
    """
    data = bytes.fromhex(encrypted_hex)
    key = bytes.fromhex(encryption_key_hex)
    aesgcm = AESGCM(key)
    nonce = data[:12]
    ciphertext = data[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


# ─── Task Hash ────────────────────────────────────────────────


def sha256_json(data: dict) -> str:
    """SHA-256 hash of a JSON-serialized dict.

    Deterministic: sorted keys, no whitespace.
    """
    body = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(body).hexdigest()
