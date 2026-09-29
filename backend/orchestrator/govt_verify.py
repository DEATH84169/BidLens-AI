"""Evidence-aware gateway: missing data never becomes PASS."""

import re
from integrations.apisetu import verify

CHECKS = {
    "gst_registration": ("GST registration", "gstin"),
    "gst_returns": ("GST return filing", "gstin"),
    "pan": ("PAN status", "pan"),
    "income_tax": ("Income Tax compliance", "pan"),
    "udyam": ("Udyam registration", "udyam"),
    "mca": ("MCA registration", "cin"),
    "epfo": ("EPFO compliance", "epfo"),
    "esic": ("ESIC compliance", "esic"),
    "startup": ("Startup India recognition", "startup"),
    "nsic": ("NSIC registration", "nsic"),
    "oem": ("OEM authorization", "oem"),
    "digilocker": ("DigiLocker / issuer authenticity", "document_uri"),
    "debarment": ("Debarment orders", "pan"),
    "bis": ("BIS certification", "bis"),
}
PATTERNS = {
    "gstin": r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]",
    "pan": r"[A-Z]{5}\d{4}[A-Z]",
    "udyam": r"UDYAM-[A-Z]{2}-\d{2}-\d{7}",
}


def verify_government_credentials(extracted_data, required_checks=None, mode="live"):
    required = set(
        required_checks
        if required_checks is not None
        else ["gst_registration", "pan", "debarment"]
    )
    gateways = []
    for key, (name, field) in CHECKS.items():
        identifier = extracted_data.get(field)
        valid = bool(
            identifier
            and (
                field not in PATTERNS or re.fullmatch(PATTERNS[field], str(identifier))
            )
        )
        if key not in required:
            details = {
                "status": "NOT_APPLICABLE",
                "reason": "Not selected in the officer-confirmed tender scope.",
                "authoritative": False,
            }
        elif mode == "demo":
            details = verify(key, identifier or "", mode)
        elif not valid:
            details = {
                "status": "NOT_VERIFIED",
                "reason": "Identifier missing or invalid; supply evidence for review.",
                "authoritative": False,
            }
        else:
            details = verify(key, str(identifier), mode)
        status = details["status"]
        gateways.append(
            {
                "id": key,
                "name": name,
                "required": key in required,
                "status": status,
                "badge": "PASS"
                if status == "VERIFIED"
                else "FAIL"
                if status == "FAILED"
                else "NEUTRAL",
                "details": {
                    **details,
                    "format_valid": valid,
                    "format_is_not_verification": True,
                },
            }
        )
    gstin, pan = extracted_data.get("gstin"), extracted_data.get("pan")
    consistent = None if not gstin or not pan else gstin[2:12] == pan
    relevant = [g for g in gateways if g["required"]]
    passed = sum(g["status"] == "VERIFIED" for g in relevant)
    return {
        "overall_govt_verification": "VERIFIED"
        if relevant and passed == len(relevant) and consistent is not False
        else "REQUIRES_REVIEW",
        "verified_gateways_count": passed,
        "total_gateways": len(relevant),
        "mode": mode,
        "pan_gstin_consistent": consistent,
        "consistency_note": "Identifiers consistent."
        if consistent
        else "Missing or inconsistent identifiers require review.",
        "gateways": gateways,
    }
