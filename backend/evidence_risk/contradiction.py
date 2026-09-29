"""Ambiguous entities are review findings, never automatic allegations of fraud."""


def detect_cross_document_contradictions(data, govt, tender_requirements=None):
    findings = []
    for field, evidence in data.get("evidence", {}).items():
        values = list(dict.fromkeys(e["value"] for e in evidence))
        if len(values) > 1:
            findings.append(
                {
                    "contradiction_id": f"CONFLICT-{field}",
                    "severity": "REVIEW",
                    "title": f"Multiple {field} values require attribution",
                    "description": "Different values may belong to bidder, OEM, another entity or another period. Officer attribution is required.",
                    "source_evidence": evidence,
                    "remedy": "Identify the bidder-owned and tender-relevant evidence before deciding.",
                }
            )
    if govt.get("pan_gstin_consistent") is False:
        findings.append(
            {
                "contradiction_id": "GST-PAN-MISMATCH",
                "severity": "REVIEW",
                "title": "GSTIN and declared PAN differ",
                "description": "Check entity attribution before deciding.",
                "source_evidence": data.get("evidence", {}).get("pan", [])
                + data.get("evidence", {}).get("gstin", []),
                "remedy": "Confirm which identifiers belong to the bidder.",
            }
        )
    return findings


def calculate_claim_integrity_score(data, contradictions):
    return {
        "integrity_score": None,
        "integrity_tier": "NOT_ASSESSED",
        "description": "Identity consistency is not an authenticity score.",
        "unsubstantiated_claims_count": len(contradictions),
    }
