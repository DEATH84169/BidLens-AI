"""Bounded uploads, hash snapshots, immutable tender versions."""

import asyncio
import os
import uuid
import zipfile
from pathlib import Path
from typing import Annotated
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
import storage
from security.auth import require_officer
from security.sha256_audit import hash_file
from orchestrator.ai_processing import extract_tender_rfp_data
from orchestrator.govt_verify import CHECKS

router = APIRouter(dependencies=[Depends(require_officer)])
ALLOWED = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".csv",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
}


def upload_dir():
    path = Path(
        os.getenv(
            "BIDLENS_UPLOAD_DIR",
            str(Path(__file__).resolve().parents[1] / "uploaded_docs"),
        )
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_upload(file, kind):
    filename = Path((file.filename or "").replace("\\", "/")).name
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(
            400, "Unsupported file format. Convert legacy DOC/XLS to DOCX/XLSX."
        )
    file_id = str(uuid.uuid4())
    path = upload_dir() / (file_id + ext)
    size = 0
    try:
        with path.open("wb") as stream:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > 20 * 1024 * 1024:
                    raise HTTPException(413, "Maximum attachment size is 20 MB.")
                stream.write(chunk)
        if not size:
            raise HTTPException(400, "Empty file.")
        if ext in {".docx", ".xlsx"}:
            try:
                with zipfile.ZipFile(path) as archive:
                    if (
                        sum(item.file_size for item in archive.infolist())
                        > 100 * 1024 * 1024
                    ):
                        raise HTTPException(
                            413, "Expanded Office document exceeds the 100 MB limit."
                        )
            except zipfile.BadZipFile:
                raise HTTPException(422, "Invalid Office document container.")
        record = {
            "file_id": file_id,
            "filename": filename,
            "path": str(path.resolve()),
            "sha256": hash_file(str(path)),
            "kind": kind,
            "size_bytes": size,
            "uploaded_at": storage.now(),
        }
        storage.put("document", file_id, record)
        return record
    except Exception:
        path.unlink(missing_ok=True)
        raise


def public_doc(record):
    return {k: v for k, v in record.items() if k != "path"}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    record = await save_upload(file, "bid")
    return {**public_doc(record), "status": "uploaded"}


@router.post("/tender/upload")
async def upload_tender_rfp(file: UploadFile = File(...)):
    record = await save_upload(file, "tender")
    try:
        data = await asyncio.to_thread(extract_tender_rfp_data, record["path"])
    except Exception:
        raise HTTPException(
            422,
            "Tender could not be parsed. Convert to a readable document or enter requirements for officer review.",
        )
    return {
        "status": "DRAFT",
        "tender_data": {
            **data,
            "filename": record["filename"],
            "tender_file_id": record["file_id"],
            "sha256": record["sha256"],
        },
    }


class Requirements(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    budget_inr: float | None = Field(default=None, ge=0)
    min_turnover_cr: float | None = Field(default=None, ge=0)
    emd_required_inr: float | None = Field(default=None, ge=0)
    min_local_content_pct: float | None = Field(default=None, ge=0, le=100)
    min_warranty_years: float | None = Field(default=None, ge=0, le=100)


class TenderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tender_id: str = Field(min_length=3, max_length=120)
    title: str = Field(min_length=3, max_length=300)
    tender_file_id: str | None = None
    requirements: Requirements
    required_checks: list[str] = Field(min_length=1, max_length=len(CHECKS))
    confirmation_note: str = Field(min_length=10, max_length=4000)


@router.post("/tender/confirm")
def confirm_tender(payload: TenderPayload, actor: str = Depends(require_officer)):
    if (
        not payload.confirmation_note.strip()
        or len(payload.confirmation_note.strip()) < 10
    ):
        raise HTTPException(
            422, "Explain the confirmed tender scope and omitted checks."
        )
    if set(payload.required_checks) - set(CHECKS):
        raise HTTPException(422, "Unknown verification check.")
    record = (
        storage.get("document", payload.tender_file_id)
        if payload.tender_file_id
        else None
    )
    if payload.tender_file_id and (not record or record["kind"] != "tender"):
        raise HTTPException(404, "Tender document not found.")
    if record and hash_file(record["path"]) != record["sha256"]:
        raise HTTPException(
            409, "Tender document changed after upload; upload a fresh version."
        )
    value = {
        **payload.model_dump(),
        "version_id": str(uuid.uuid4()),
        "confirmed_at": storage.now(),
        "confirmed_by": actor,
        "document_sha256": record["sha256"] if record else None,
    }
    storage.put("tender", value["version_id"], value)
    storage.append_event(value["version_id"], "TENDER_CONFIRMED", actor, value)
    return {"tender": value}


@router.get("/list")
def list_documents():
    return {"documents": [public_doc(d) for d in storage.listing("document")]}


@router.get("/file/{file_id}")
def download_document(file_id: str):
    record = storage.get("document", file_id)
    if not record:
        raise HTTPException(404, "Document not found.")
    if (
        not Path(record["path"]).is_file()
        or hash_file(record["path"]) != record["sha256"]
    ):
        raise HTTPException(409, "Document missing or changed; evidence unavailable.")
    return FileResponse(
        record["path"],
        filename=record["filename"],
        media_type="application/octet-stream",
    )
