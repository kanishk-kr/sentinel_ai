"""
SENTINEL — Model supply-chain verifier (FR2.1 / Section 3.2).
Minimal keypair + checksum check — not a full PKI.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from src.shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SupplyChainRejected(ValueError):
    """Raised when a model bundle fails verification and must not become selectable."""


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_bundle(
    *,
    bundle_path: str | None,
    claimed_sha256: str | None,
    signature: str | None,
    capabilities: dict | list | None,
    requirements: dict | None,
    context_window: int,
) -> dict:
    """
    signature → checksum → manifest schema → capability-claim sanity.
    Returns metadata to persist on model_registry.
    """
    if not capabilities:
        raise SupplyChainRejected("Manifest schema invalid: capabilities are required")
    if not isinstance(requirements, dict):
        raise SupplyChainRejected("Manifest schema invalid: requirements must be an object")
    if context_window < 512:
        raise SupplyChainRejected("Capability-claim check failed: context_window is implausibly small")

    model_hash = None
    if bundle_path:
        path = Path(bundle_path)
        if not path.is_file():
            raise SupplyChainRejected(f"Model bundle not found: {bundle_path}")
        model_hash = sha256_file(path)
        if claimed_sha256 and claimed_sha256.lower() != model_hash.lower():
            raise SupplyChainRejected("SHA-256 checksum does not match the on-disk bundle")
    elif claimed_sha256:
        model_hash = claimed_sha256.lower()
    else:
        raise SupplyChainRejected(
            "Unsigned/unhashed model rejected: provide bundle_path or bundle_sha256"
        )

    pub_key = Path(settings.model_signing_public_key_path)
    if pub_key.exists() and not signature:
        raise SupplyChainRejected("Signature verification failed: detached signature is required")
    if signature and pub_key.exists():
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding

            public_key = serialization.load_pem_public_key(pub_key.read_bytes())
            public_key.verify(
                bytes.fromhex(signature) if all(c in "0123456789abcdefABCDEF" for c in signature) else signature.encode(),
                bytes.fromhex(model_hash),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except InvalidSignature as exc:
            raise SupplyChainRejected("Signature verification failed") from exc
        except Exception as exc:
            raise SupplyChainRejected(f"Signature verification failed: {exc}") from exc

    return {
        "model_hash": model_hash,
        "model_signature": signature,
        "verified": True,
    }
