"""Private-demo server-to-server authorization helpers."""

from __future__ import annotations

import hashlib
import hmac


def internal_demo_token(password: str) -> str:
    """Derive a separate internal API token without exposing the invite password."""
    return hmac.new(
        password.encode(),
        b"mittimitra-private-demo-internal-api-v1",
        hashlib.sha256,
    ).hexdigest()
