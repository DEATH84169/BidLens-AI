"""Source verification adapter preserving the original six-card response contract."""
import os
import re
from integrations.apisetu import verify

GATEWAYS = [
    ("gst", "GSTN Common Portal", "gstin", r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]"),
    ("pan", "ITD PAN Registry", "pan", r"[A-Z]{5}\d{4}[A-Z]"),
    ("mca", "MCA21 Corporate Affairs", "cin", None),
    ("udyam", "Udyam MSME Portal", "udyam", r"UDYAM-[A-Z]{2}-\d{2}-\d{7}"),
    ("epfo_esic", "EPFO & ESIC Labour Compliance", "establishment_id", None),
    ("debarment", "CPPP Central Debarment Watchlist", "pan", None),
]


def verify_government_credentials(extracted_data: dict) -> dict:
    mode = os.getenv("BIDLENS_VERIFICATION_MODE", "live")
    if mode not in ("live", "sandbox", "demo"):
        mode = "live"
    gateways = []
    for key, name, field, pattern in GATEWAYS:
        identifier = extracted_data.get(field)
        valid_format = bool(identifier and (not pattern or re.fullmatch(pattern, str(identifier))))
        if mode == "demo":
            result = verify(key, identifier, mode)
        elif not identifier:
            result = {"status": "NOT_VERIFIED", "reason": "Identifier not supplied or not extracted; officer review required.", "authoritative": False}
        elif not valid_format:
            result = {"status": "NOT_VERIFIED", "reason": "Identifier format needs correction; no registry lookup performed.", "authoritative": False}
        else:
            result = verify(key, identifier, mode)
        badge = "PASS" if result["status"] == "VERIFIED" else "FAIL" if result["status"] == "FAILED" else "NEUTRAL"
        gateways.append({"name": name, "check_id": key, "status": result["status"], "badge": badge,
            "details": {**result, "portal": name, "valid_format": valid_format, "identifier": identifier,
                "scope": "This configured check only; registration does not establish return filing, exemptions, or unrelated compliance."}})
    gstin, pan = extracted_data.get("gstin"), extracted_data.get("pan")
    consistent = gstin[2:12] == pan if gstin and pan and len(gstin) >= 12 else None
    count = sum(g["badge"] == "PASS" for g in gateways)
    return {"overall_govt_verification": "PASS" if count == len(gateways) and consistent is True else "FLAGGED_FOR_REVIEW",
        "verified_gateways_count": count, "total_gateways": len(gateways), "environment": mode,
        "pan_gstin_consistent": consistent,
        "consistency_note": "GSTIN embedded PAN matches declared PAN." if consistent is True else "GSTIN/PAN require officer comparison or missing identifiers.",
        "gateways": gateways}
