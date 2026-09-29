"""Single-officer pilot authentication. Use SSO/RBAC for a multi-officer deployment."""

import os
import secrets
from fastapi import Header, HTTPException


def require_officer(x_bidlens_key: str = Header(default="")):
    expected = os.getenv("BIDLENS_API_KEY", "")
    if len(expected) < 24:
        raise HTTPException(
            503,
            "Configure a server BIDLENS_API_KEY of at least 24 characters before using data endpoints.",
        )
    if not secrets.compare_digest(expected.encode(), x_bidlens_key.encode()):
        raise HTTPException(401, "Valid officer access key required.")
    return os.getenv("BIDLENS_OFFICER_NAME", "Configured pilot officer")
