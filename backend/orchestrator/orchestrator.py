"""Audit one bidder's attachment set against one saved tender version."""

import asyncio
from orchestrator.ai_processing import extract_document_data, merge_documents
from orchestrator.rule_engine import evaluate_compliance
from orchestrator.govt_verify import verify_government_credentials
from evidence_risk.contradiction import detect_cross_document_contradictions
from evidence_risk.risk_scorer import compute_risk_and_value_intelligence
from evidence_risk.graph_engine import build_compliance_knowledge_graph


def assess(extracted, tender, govt, clauses=None):
    requirements = tender["requirements"]
    clauses = (
        clauses if clauses is not None else evaluate_compliance(extracted, requirements)
    )
    contradictions = detect_cross_document_contradictions(extracted, govt, requirements)
    scores = compute_risk_and_value_intelligence(
        extracted, clauses, contradictions, govt, requirements
    )
    return {
        "is_compliant": False,  # System findings are never a final officer qualification.
        "assessment_status": scores["assessment_status"],
        "executive_summary": scores["executive_summary"],
        "compliance_score": scores["compliance_score"],
        "coverage": scores["coverage"],
        "compliance_summary": {
            "total_clauses_checked": len(clauses),
            "passed": sum(c["status"] == "PASS" for c in clauses),
            "failed": sum(c["status"] == "FAIL" for c in clauses),
            "exempt": sum(c["status"] == "EXEMPT" for c in clauses),
            "overall_status": scores["assessment_status"],
            "risk_tier": scores["rejection_risk"]["risk_tier"],
        },
        "branch_a_extracted_data": extracted,
        "branch_b_clause_results": clauses,
        "clause_level_decisions": clauses,
        "branch_c_govt_verification": govt,
        "government_verification": govt,
        "rejection_risk_analysis": scores["rejection_risk"],
        "value_spotlight": scores["value_spotlight"],
        "bid_repair_guidance": scores["bid_repair"],
        "contradictions_detected": contradictions,
        "knowledge_graph": build_compliance_knowledge_graph(extracted, clauses, govt),
    }


async def run_full_audit(file_paths, tender, mode="live"):
    if isinstance(file_paths, str):
        file_paths = [file_paths]
    # Bound work through the caller's upload/attachment limits. OCR processes every page.
    documents = []
    for path in file_paths:
        documents.append(await asyncio.to_thread(extract_document_data, path))
    extracted = merge_documents(documents)
    govt = await asyncio.to_thread(
        verify_government_credentials, extracted, tender["required_checks"], mode
    )
    result = assess(extracted, tender, govt)
    return {
        **result,
        "file_info": {
            k: extracted[k]
            for k in ("filename", "file_type", "vendor_name", "page_count")
        },
        "tender": tender,
        "mode": mode,
        "documents": extracted["documents"],
    }
