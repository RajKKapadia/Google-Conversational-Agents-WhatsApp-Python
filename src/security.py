"""
Security utilities for webhook verification.
"""

import hmac
import hashlib

from src.config import APP_SECRET


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify the webhook signature from Meta WhatsApp.

    Args:
        payload: Raw request body as bytes
        signature: The X-Hub-Signature-256 header value (format: "sha256=<hash>")

    Returns:
        True if signature is valid, False otherwise
    """
    if not APP_SECRET:
        return False

    # Remove 'sha256=' prefix if present
    if signature.startswith("sha256="):
        signature = signature[7:]

    # Calculate expected signature
    expected_signature = hmac.new(
        key=APP_SECRET.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Compare signatures using constant-time comparison
    return hmac.compare_digest(expected_signature, signature)
