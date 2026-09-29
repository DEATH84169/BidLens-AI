# BidLens AI — evidence-based bid review

This fork improves the SIH GeM/CPCL prototype by separating **document claims, source verification and the procurement officer's decision**. Original project: https://github.com/BidLens-AI/BidLens-AI.

## Implemented workflow

- Upload an RFP, inspect extracted draft values and save an officer-confirmed tender version. Missing values remain unknown.
- Group up to 20 attachments for one bidder. PDF, OCR images/scans, DOCX, XLSX and CSV supported. Every PDF page is accounted for. Maximum 200 PDF pages and 20 MB per attachment.
- Compare explicit turnover, EMD amount, warranty and local-content claims against that tender. Document claims do not establish issuer authenticity.
- Use contract-configured API Setu transport. Missing approved access remains NOT_VERIFIED. Sandbox/demo never qualifies bidders.
- Review source snippets, page/sheet evidence, registry status, unresolved findings and a check-coverage score (not a probability).
- Record justified overrides and separate officer decisions in SQLite. Preserve original snapshots and hash-linked event history.
- Download original evidence and a PDF report using authenticated endpoints.
- Look up 11 selected, attributed MoSPI NIC 2008 divisions as historical reference data.

## Local setup

Requires Python 3.11+ and Node.js 20+.

For scanned documents, install the platform prerequisites in the [ONNX Runtime installation guide](https://onnxruntime.ai/docs/install/). On Windows, a native DLL loading failure is an environment/setup error: it is reported as unread evidence, never a successful check. Run `python scripts/check_ocr.py` in the configured virtual environment before relying on OCR.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
```

Generate a random access key of at least 24 characters locally. Put it in `BIDLENS_API_KEY` in `backend/.env`, set `BIDLENS_OFFICER_NAME`, and keep the key private. Data endpoints fail closed without it.

```powershell
.venv\Scripts\python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000 and enter the **officer access key**, not an API Setu provider secret. The UI keeps it in page memory. The frontend proxies to localhost:8000; set `BACKEND_PROXY_URL` at build time for your own deployed backend. No requests are forwarded to the upstream project's hosted backend.

1. Connect, upload/enter the tender and review thresholds. Blank means unknown; 0 means officer-confirmed no minimum. Explain check applicability and tender clause references.
2. Save the tender version. Upload all relevant attachments for one bidder.
3. Choose production, sandbox or local demo and evaluate. Without approved source credentials, production checks remain unverified.
4. Review evidence, record justified overrides and then the officer decision. Rerun as a new assessment version to change clauses after a decision.

Extraction conservatively accepts explicit labels such as `Warranty: 3-Year`, `EMD Submitted: INR 100000`, `Local Content: 60%` and `Turnover: 2 crore`. Unsupported formats remain missing rather than guessed. Officers may cite additional reviewed evidence in their final decision without changing an automated registry status.

## API Setu and data

Read [API Setu setup](docs/API_SETU.md), [data provenance](docs/DATA_SOURCES.md) and [migration/change notes](docs/IMPROVEMENTS.md). **No production API Setu subscription or keys were supplied or activated.** Transport is mock-contract tested, not live-publisher tested. Approval and publisher-specific implementation are still required.

## Tests

```powershell
.venv\Scripts\python -m unittest discover -s backend/tests -v
cd frontend
npm run build
npm audit
```

The regression suite covers false exemptions, tender binding, provider outages, response-subject mismatch, all-page OCR accounting, evidence tampering, durable overrides and officer decisions. Existing sample bids and the new regression scenarios are synthetic, not government records.

## Deployment boundaries

This is a **single-officer pilot**, not a production compliance certification. The pilot key authenticates one server-configured identity. Add individual SSO/RBAC, organization isolation, retention controls, encryption and protected backups, malware/resource controls, rate limits and job workers for production.

Use persistent volumes for `BIDLENS_DB_PATH` and `BIDLENS_UPLOAD_DIR`. Local event hashes are not independently anchored; an administrator can replace/truncate the DB. No CERT-In certification, complete legal coverage, zero-error or measured 60–80% effort-reduction claim is made.

Remaining work includes publisher-specific consent/OAuth and filing-period semantics, broader identifier extraction, issuer/signature authenticity, reviewed statutory applicability, entity-role attribution and multilingual OCR benchmarks. Qualification/disqualification always remains with the procurement officer.
