"""Transparent check coverage, not a statistical rejection probability."""


def compute_risk_and_value_intelligence(
    data, clauses, contradictions, govt=None, tender_requirements=None
):
    required = [g for g in (govt or {}).get("gateways", []) if g.get("required")]
    failures = [c for c in clauses if c["status"] == "FAIL"]
    registry_failures = [g for g in required if g["status"] == "FAILED"]
    pending = [c for c in clauses if c["status"] == "PENDING"]
    unverified = [g for g in required if g["status"] not in ("VERIFIED", "FAILED")]
    passed = sum(c["status"] in ("PASS", "EXEMPT") for c in clauses) + sum(
        g["status"] == "VERIFIED" for g in required
    )
    total = sum(c["status"] != "NOT_APPLICABLE" for c in clauses) + len(required)
    unresolved = (
        len(pending)
        + len(unverified)
        + len(contradictions)
        + len(data.get("unread_pages", []))
    )
    status = (
        "ISSUES_FOUND"
        if failures or registry_failures
        else "REQUIRES_REVIEW"
        if unresolved or not total
        else "CHECKS_PASSED"
    )
    tier = (
        "HIGH"
        if failures or registry_failures
        else "UNKNOWN"
        if unresolved or not total
        else "LOW"
    )
    budget = (tender_requirements or {}).get("budget_inr")
    quote = data.get("total_quote_inr")
    savings = budget - quote if budget is not None and quote is not None else None
    summary = f"{status}: {passed}/{total} applicable checks passed; {unresolved} unresolved findings. Final qualification remains with the procurement officer."
    return {
        "assessment_status": status,
        "compliance_score": round(100 * passed / total, 1) if total else None,
        "coverage": {"passed": passed, "applicable": total, "unresolved": unresolved},
        "rejection_risk": {
            "risk_tier": tier,
            "risk_score": None,
            "rejection_likely": None,
            "total_flaws_found": len(failures) + len(registry_failures),
            "reasons": [
                {"clause": c["clause_name"], "reason": c["evidence"]} for c in failures
            ],
        },
        "value_spotlight": {
            "is_spotlight_candidate": False,
            "quoted_price_inr": quote,
            "estimated_savings_inr": savings,
            "value_highlights": [],
            "vendor_type": "Not independently verified",
        },
        "bid_repair": {
            "repair_needed": bool(unresolved or failures or registry_failures),
            "recommended_actions": [
                {"issue": c["clause_name"], "action_required": c["remedy"]}
                for c in clauses
                if c.get("remedy")
            ],
        },
        "executive_summary": summary,
    }
