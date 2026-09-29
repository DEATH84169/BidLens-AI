"""Durable audit snapshots; overrides append events and recompute derived findings."""

import copy
import hashlib
import uuid
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
import storage
from security.auth import require_officer
from security.sha256_audit import hash_file
from orchestrator.orchestrator import run_full_audit, assess
from utils.pdf_generator import render_audit_pdf

router = APIRouter(dependencies=[Depends(require_officer)])


class RunAuditPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_ids: list[str] = Field(min_length=1, max_length=20)
    tender_version_id: str
    mode: Literal["live", "sandbox", "demo"] = "live"


@router.post("/run")
async def trigger_audit(
    payload: RunAuditPayload, actor: str = Depends(require_officer)
):
    tender = storage.get("tender", payload.tender_version_id)
    if not tender:
        raise HTTPException(404, "Confirm and save a tender version before evaluation.")
    if len(set(payload.file_ids)) != len(payload.file_ids):
        raise HTTPException(422, "Duplicate attachments.")
    documents = []
    for file_id in payload.file_ids:
        doc = storage.get("document", file_id)
        if not doc or doc["kind"] != "bid":
            raise HTTPException(404, "Bid attachment not found.")
        if not Path(doc["path"]).is_file() or hash_file(doc["path"]) != doc["sha256"]:
            raise HTTPException(
                409, "Attachment changed after upload; upload a fresh version."
            )
        documents.append(doc)
    if tender.get("tender_file_id"):
        source = storage.get("document", tender["tender_file_id"])
        if (
            not source
            or not Path(source["path"]).is_file()
            or hash_file(source["path"]) != tender["document_sha256"]
        ):
            raise HTTPException(409, "Tender evidence changed after confirmation.")
    try:
        result = await run_full_audit(
            [d["path"] for d in documents], tender, payload.mode
        )
    except (ValueError, RuntimeError, OSError):
        raise HTTPException(
            422,
            "Document parsing failed. Review attachment format, size and readability.",
        )
    # Re-check to bind the assessment to the exact uploaded bytes.
    if any(hash_file(d["path"]) != d["sha256"] for d in documents):
        raise HTTPException(
            409, "An attachment changed during evaluation; retry with a fresh upload."
        )
    names = {Path(d["path"]).name: d["filename"] for d in documents}
    extracted = result["branch_a_extracted_data"]
    for entries in extracted["evidence"].values():
        for entry in entries:
            entry["filename"] = names.get(entry["filename"], entry["filename"])
    for entry in extracted["unread_pages"]:
        entry["filename"] = names.get(entry["filename"], entry["filename"])
    extracted.pop("raw_text", None)
    result["audit_id"] = str(uuid.uuid4())
    result["created_at"] = storage.now()
    result["documents"] = [
        {k: v for k, v in d.items() if k != "path"} for d in documents
    ]
    result["snapshot_sha256"] = hashlib.sha256(
        storage.canonical(result).encode()
    ).hexdigest()
    storage.put("audit", result["audit_id"], result)
    storage.append_event(
        result["audit_id"],
        "AUDIT_CREATED",
        actor,
        {"snapshot_sha256": result["snapshot_sha256"]},
    )
    return {
        "audit_id": result["audit_id"],
        "status": "COMPLETED",
        "results": current_audit(result["audit_id"]),
    }


def current_audit(audit_id):
    snapshot = storage.get("audit", audit_id)
    if not snapshot:
        raise HTTPException(404, "Audit not found.")
    unhashed = {k: v for k, v in snapshot.items() if k != "snapshot_sha256"}
    if (
        hashlib.sha256(storage.canonical(unhashed).encode()).hexdigest()
        != snapshot["snapshot_sha256"]
    ):
        raise HTTPException(409, "Stored audit integrity check failed.")
    if not storage.verify_chain()["valid"]:
        raise HTTPException(409, "Audit event integrity check failed.")
    result = copy.deepcopy(snapshot)
    history = storage.events(audit_id)
    created = next((e for e in history if e["type"] == "AUDIT_CREATED"), None)
    if not created or created["data"]["snapshot_sha256"] != snapshot["snapshot_sha256"]:
        raise HTTPException(
            409, "Audit snapshot does not match its recorded creation event."
        )
    for event in history:
        if event["type"] == "CLAUSE_OVERRIDE":
            for clause in result["clause_level_decisions"]:
                if clause["clause_id"] == event["data"]["clause_id"]:
                    clause["status"] = event["data"]["new_status"]
                    clause["officer_override_note"] = event["data"]["justification"]
    result.update(
        assess(
            result["branch_a_extracted_data"],
            result["tender"],
            result["government_verification"],
            result["clause_level_decisions"],
        )
    )
    decisions = [e for e in history if e["type"] == "OFFICER_DECISION"]
    result["officer_decision"] = decisions[-1] if decisions else None
    result["history"] = history
    result["automated_assessment_status"] = snapshot["assessment_status"]
    return result


class ClauseOverridePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audit_id: str
    clause_id: str
    new_status: Literal["PASS", "FAIL", "EXEMPT", "PENDING", "NOT_APPLICABLE"]
    justification: str = Field(min_length=10, max_length=4000)


@router.post("/clause-override")
def record_clause_override(
    payload: ClauseOverridePayload, actor: str = Depends(require_officer)
):
    if len(payload.justification.strip()) < 10:
        raise HTTPException(422, "A meaningful written justification is required.")
    result = current_audit(payload.audit_id)
    if result["officer_decision"]:
        raise HTTPException(
            409,
            "A final/review decision already exists; run a new assessment version before changing clauses.",
        )
    clause = next(
        (
            c
            for c in result["clause_level_decisions"]
            if c["clause_id"] == payload.clause_id
        ),
        None,
    )
    if not clause:
        raise HTTPException(404, "Clause not found.")
    storage.append_event(
        payload.audit_id,
        "CLAUSE_OVERRIDE",
        actor,
        {**payload.model_dump(), "original_status": clause["status"]},
    )
    return {"results": current_audit(payload.audit_id)}


@router.get("/status/{audit_id}")
def get_audit_status(audit_id: str):
    return {"audit_id": audit_id, "results": current_audit(audit_id)}


@router.get("/list")
def list_audits():
    return {
        "audits": [
            {
                "audit_id": a["audit_id"],
                "created_at": a["created_at"],
                "vendor_name": a["file_info"]["vendor_name"],
                "tender_id": a["tender"]["tender_id"],
                "mode": a["mode"],
            }
            for a in storage.listing("audit")
        ]
    }


@router.get("/report/pdf/{audit_id}")
def download_audit_pdf(audit_id: str):
    return Response(
        render_audit_pdf(current_audit(audit_id)),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="BidLens-{uuid.UUID(audit_id)}.pdf"'
        },
    )
