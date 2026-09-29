"""Deterministic checks against an officer-confirmed tender, not invented law."""


def evaluate_compliance(data, tender_requirements=None):
    req = tender_requirements or {}
    results = []
    checks = [
        (
            "TENDER-TURNOVER",
            "Declared annual turnover",
            "turnover_cr",
            "min_turnover_cr",
        ),
        ("TENDER-EMD", "Declared EMD amount", "emd_amount_inr", "emd_required_inr"),
        (
            "TENDER-LOCAL-CONTENT",
            "Declared local content",
            "local_content_pct",
            "min_local_content_pct",
        ),
        (
            "TENDER-WARRANTY",
            "Declared warranty",
            "warranty_years",
            "min_warranty_years",
        ),
    ]
    for cid, name, field, threshold in checks:
        actual, minimum = data.get(field), req.get(threshold)
        status = "PENDING"
        evidence = "Tender requirement or unambiguous bidder evidence is missing."
        if minimum == 0:
            status = "NOT_APPLICABLE"
            evidence = "Officer confirmed no minimum requirement for this tender."
        elif actual is not None and minimum is not None:
            status = "PASS" if actual >= minimum else "FAIL"
            evidence = f"Declared value {actual:g}; confirmed tender minimum {minimum:g}. Document authenticity remains a separate check."
        # No blanket MSE waiver. An officer may apply an evidence-backed override.
        if (
            data.get("msme_claimed")
            and cid in ("TENDER-TURNOVER", "TENDER-EMD")
            and status == "FAIL"
        ):
            status = "PENDING"
            evidence += " MSE exemption claimed; eligibility and applicability require officer review."
        results.append(
            {
                "clause_id": cid,
                "clause_name": name,
                "status": status,
                "regulation_ref": "Officer-confirmed tender conditions; no universal statutory threshold implied",
                "evidence": evidence,
                "source_evidence": data.get("evidence", {}).get(field, []),
                "remedy": None
                if status in ("PASS", "NOT_APPLICABLE")
                else "Review source evidence and applicable tender clause.",
            }
        )
    return results
