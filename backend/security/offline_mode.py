"""Readiness facts rather than certification assertions."""

import os


def get_system_health_status():
    return {
        "system_status": "OPERATIONAL",
        "mode": "DOCUMENT_REVIEW",
        "authentication_configured": len(os.getenv("BIDLENS_API_KEY", "")) >= 24,
        "registry_configuration_present": bool(os.getenv("APISETU_CONFIG_PATH")),
        "notice": "Configuration presence does not establish publisher approval or live connectivity.",
        "security_integrity": {
            "cert_in_compliance": "NOT_ASSESSED",
            "audit_storage": "SQLITE_HASH_LINKED_EVENTS",
        },
    }
