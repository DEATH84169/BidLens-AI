"""BidLens AI pilot API. Configure an officer key before uploading documents."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from routers import document, audit, review
from security.auth import require_officer
from security.offline_mode import get_system_health_status
from orchestrator.govt_verify import CHECKS

app = FastAPI(title="BidLens AI — Evidence-based bid review", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        s.strip()
        for s in os.getenv(
            "BIDLENS_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if s.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-BidLens-Key"],
)
app.include_router(document.router, prefix="/document", tags=["Documents"])
app.include_router(audit.router, prefix="/audit", tags=["Audit"])
app.include_router(review.router, prefix="/review", tags=["Officer review"])


@app.get("/")
def root():
    return {"service": "BidLens AI", "version": "2.0.0"}


@app.get("/system/health")
def health():
    return get_system_health_status()


@app.get("/system/checks", dependencies=[Depends(require_officer)])
def checks():
    return {"checks": [{"id": key, "name": value[0]} for key, value in CHECKS.items()]}


@app.get("/system/reference/nic2008/{code}", dependencies=[Depends(require_officer)])
def nic_reference(code: str):
    import json

    data = json.loads(
        (Path(__file__).parent / "data" / "nic2008_selected.json").read_text(
            encoding="utf-8"
        )
    )
    record = next((r for r in data["records"] if r["code"] == code), {})
    return {
        **record,
        "source_url": data["source_url"],
        "edition": data["edition"],
        "coverage": data["coverage"],
        "use": data["use"],
    }
