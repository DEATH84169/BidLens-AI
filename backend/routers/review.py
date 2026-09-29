"""Officer decisions are separate from automated assessments."""

from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
import storage
from security.auth import require_officer
from routers.audit import current_audit

router = APIRouter(dependencies=[Depends(require_officer)])


class OfficerDecisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audit_id: str
    action: Literal["APPROVE", "REJECT", "REQUEST_CLARIFICATION"]
    justification: str = Field(min_length=10, max_length=4000)


@router.post("/decision")
def submit_officer_decision(
    payload: OfficerDecisionPayload, actor: str = Depends(require_officer)
):
    result = current_audit(payload.audit_id)
    if len(payload.justification.strip()) < 10:
        raise HTTPException(
            422, "Provide a meaningful justification and evidence basis."
        )
    if result["mode"] != "live" and payload.action != "REQUEST_CLARIFICATION":
        raise HTTPException(
            409, "Sandbox and demo assessments cannot produce qualification decisions."
        )
    event = storage.append_event(
        payload.audit_id,
        "OFFICER_DECISION",
        actor,
        {
            **payload.model_dump(),
            "assessment_at_decision": result["assessment_status"],
            "unresolved_at_decision": result["coverage"]["unresolved"],
        },
    )
    return {
        "status": "RECORDED",
        "event": event,
        "results": current_audit(payload.audit_id),
    }


@router.get("/log/{audit_id}")
def audit_trail(audit_id: str):
    current_audit(audit_id)
    return {
        "audit_id": audit_id,
        "audit_trail": storage.events(audit_id),
        "integrity": storage.verify_chain(),
    }
