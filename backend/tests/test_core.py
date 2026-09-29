"""Regression coverage for false verification, tender binding and saved decisions."""

import asyncio
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import pymupdf
from fastapi.testclient import TestClient
import storage
from main import app
from integrations.apisetu import verify
from orchestrator.ai_processing import (
    extract_from_pages,
    extract_pages,
    merge_documents,
    extract_tender_rfp_data,
)
from orchestrator.govt_verify import verify_government_credentials
from orchestrator.rule_engine import evaluate_compliance
from evidence_risk.contradiction import detect_cross_document_contradictions
from evidence_risk.risk_scorer import compute_risk_and_value_intelligence

KEY = "test-only-officer-access-key-not-production"
REQ = {
    "budget_inr": 500000,
    "min_turnover_cr": 1.5,
    "emd_required_inr": 100000,
    "min_local_content_pct": 50,
    "min_warranty_years": 3,
}
BID = "Company Name: Synthetic Example LLP\nGSTIN: 27AABCT3456L1ZV\nPAN: AABCT3456L\nTurnover: 2 crore\nEMD Submitted: INR 100000\nLocal Content: 60%\nWarranty: 3-Year\nTotal Quote: INR 420000\n"


def extracted(text=BID):
    return extract_from_pages(
        [{"page": 1, "text": text, "error": None}], "synthetic.pdf"
    )


def pdf(text):
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((40, 50), text, fontsize=10)
    result = document.tobytes()
    document.close()
    return result


class CoreRegressionTests(unittest.TestCase):
    def test_negation_does_not_grant_waivers_or_emd(self):
        data = extracted(
            "Company Name: Test\nNot an MSME\nEMD not submitted; bank guarantee required\nGST is not cancelled"
        )
        self.assertFalse(data["is_msme"])
        self.assertFalse(data["msme_claimed"])
        self.assertIsNone(data.get("emd_amount_inr"))
        self.assertNotIn("gstin_expired", data)
        self.assertNotIn(
            "EXEMPT", [c["status"] for c in evaluate_compliance(data, REQ)]
        )

    def test_late_msme_claim_is_not_exemption(self):
        data = extracted(BID + "a " * 1000 + "Not an MSME")
        self.assertNotIn(
            "EXEMPT", [c["status"] for c in evaluate_compliance(data, REQ)]
        )

    def test_explicit_claim_requires_review_without_automatic_exemption(self):
        data = extracted(
            BID.replace("Turnover: 2", "Turnover: 0.2") + "\nMSME Claimed: yes"
        )
        clause = evaluate_compliance(data, REQ)[0]
        self.assertEqual(clause["status"], "PENDING")

    def test_warranty_threshold_pass_and_fail(self):
        self.assertEqual(evaluate_compliance(extracted(), REQ)[3]["status"], "PASS")
        self.assertEqual(
            evaluate_compliance(extracted(BID.replace("3-Year", "1-Year")), REQ)[3][
                "status"
            ],
            "FAIL",
        )

    def test_emd_amount_pass_and_fail(self):
        self.assertEqual(evaluate_compliance(extracted(), REQ)[1]["status"], "PASS")
        self.assertEqual(
            evaluate_compliance(extracted(BID.replace("100000", "1000")), REQ)[1][
                "status"
            ],
            "FAIL",
        )

    def test_tender_threshold_changes_result(self):
        data = extracted(BID.replace("Turnover: 2", "Turnover: 1"))
        low = {**REQ, "min_turnover_cr": 0.5}
        self.assertEqual(evaluate_compliance(data, low)[0]["status"], "PASS")
        self.assertEqual(evaluate_compliance(data, REQ)[0]["status"], "FAIL")
        self.assertEqual(detect_cross_document_contradictions(data, {}, low), [])

    def test_unknown_and_not_applicable_are_distinct(self):
        self.assertEqual(evaluate_compliance({}, {})[0]["status"], "PENDING")
        self.assertEqual(
            evaluate_compliance({}, {"min_turnover_cr": 0})[0]["status"],
            "NOT_APPLICABLE",
        )

    def test_empty_gateway_never_verifies(self):
        result = verify_government_credentials(
            {}, list(__import__("orchestrator.govt_verify", fromlist=["CHECKS"]).CHECKS)
        )
        self.assertEqual(result["verified_gateways_count"], 0)
        self.assertFalse(any(g["badge"] == "PASS" for g in result["gateways"]))

    def test_missing_pan_prevents_checks_passed(self):
        data = extracted(BID.replace("PAN: AABCT3456L", ""))
        with patch.dict(os.environ, {"APISETU_CONFIG_PATH": ""}):
            govt = verify_government_credentials(data)
        scores = compute_risk_and_value_intelligence(
            data, evaluate_compliance(data, REQ), [], govt, REQ
        )
        self.assertEqual(scores["assessment_status"], "REQUIRES_REVIEW")
        self.assertEqual(scores["rejection_risk"]["risk_tier"], "UNKNOWN")

    def test_no_quote_does_not_crash(self):
        data = extracted(BID.replace("Total Quote: INR 420000", ""))
        scores = compute_risk_and_value_intelligence(
            data, evaluate_compliance(data, REQ), [], {}, REQ
        )
        self.assertIsNone(scores["value_spotlight"]["estimated_savings_inr"])

    def test_budget_comes_from_tender(self):
        scores = compute_risk_and_value_intelligence(extracted(), [], [], {}, REQ)
        self.assertEqual(scores["value_spotlight"]["estimated_savings_inr"], 80000)

    def test_attachment_conflicts_are_attributed_not_fraud(self):
        data = merge_documents(
            [extracted(), extracted(BID.replace("AABCT3456L", "AAAAA1111A"))]
        )
        self.assertNotIn("pan", data)
        findings = detect_cross_document_contradictions(data, {})
        self.assertTrue(findings)
        self.assertTrue(all(c["severity"] == "REVIEW" for c in findings))

    def test_ocr_covers_middle_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scan.pdf"
            doc = pymupdf.open()
            for _ in range(8):
                doc.new_page()
            doc.save(path)
            doc.close()
            with patch(
                "orchestrator.ai_processing.ocr_text",
                return_value="Middle page evidence",
            ) as ocr:
                pages = extract_pages(path)
            self.assertEqual(ocr.call_count, 8)
            self.assertEqual(len(pages), 8)

    def test_ocr_failure_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scan.pdf"
            path.write_bytes(pdf(""))
            with patch(
                "orchestrator.ai_processing.ocr_text",
                side_effect=RuntimeError("unavailable"),
            ):
                pages = extract_pages(path)
            self.assertIsNotNone(pages[0]["error"])

    def test_unread_pages_prevent_complete_assessment(self):
        data = extracted()
        data["unread_pages"] = [{"page": 7, "reason": "OCR failed"}]
        result = compute_risk_and_value_intelligence(
            data, evaluate_compliance(data, REQ), [], {}, REQ
        )
        self.assertEqual(result["assessment_status"], "REQUIRES_REVIEW")

    def test_tender_parser_does_not_invent_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tender.pdf"
            path.write_bytes(
                pdf("Tender title only. No financial thresholds in this text.")
            )
            draft = extract_tender_rfp_data(path)
        self.assertTrue(all(v is None for v in draft["requirements"].values()))


class ApiSetuContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "config.json"
        self.cfg = {
            "pan": {
                "url": "https://apisetu.gov.in/test-contract-only",
                "method": "POST",
                "publisher": "Test publisher",
                "environment": "production",
                "headers_from_env": {"X-Test-Key": "TEST_PROVIDER_KEY"},
                "identifier_parameter": "pan",
                "response_identifier_pointer": "/subject",
                "response_status_pointer": "/status",
                "verified_values": ["ACTIVE"],
                "failed_values": ["INACTIVE"],
            }
        }
        self.path.write_text(json.dumps(self.cfg))
        self.env = patch.dict(
            os.environ,
            {
                "APISETU_CONFIG_PATH": str(self.path),
                "TEST_PROVIDER_KEY": "not-a-real-provider-key",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def call(self, status=200, body=None, mode="live"):
        response = (
            body if body is not None else {"subject": "AABCT3456L", "status": "ACTIVE"}
        )
        transport = httpx.MockTransport(
            lambda req: httpx.Response(status, json=response)
        )
        return verify("pan", "AABCT3456L", mode, transport=transport)

    def test_contract_success_matches_identifier(self):
        result = self.call()
        self.assertEqual(result["status"], "VERIFIED")
        self.assertIn("response_sha256", result)

    def test_failure_not_http_success(self):
        self.assertEqual(
            self.call(body={"subject": "AABCT3456L", "status": "INACTIVE"})["status"],
            "FAILED",
        )

    def test_missing_schema_field_is_unverified(self):
        self.assertEqual(self.call(body={"ok": True})["status"], "NOT_VERIFIED")

    def test_other_subject_never_verifies(self):
        self.assertEqual(
            self.call(body={"subject": "AAAAA1111A", "status": "ACTIVE"})["status"],
            "NOT_VERIFIED",
        )

    def test_unmapped_status_never_verifies(self):
        self.assertEqual(
            self.call(body={"subject": "AABCT3456L", "status": "PENDING"})["status"],
            "NOT_VERIFIED",
        )

    def test_outages_and_denials(self):
        for status in (401, 403, 404, 429, 500, 503):
            with self.subTest(status=status):
                self.assertEqual(self.call(status)["status"], "NOT_VERIFIED")

    def test_timeout_not_verification(self):
        def fail(request):
            raise httpx.ReadTimeout("test timeout")

        result = verify("pan", "AABCT3456L", transport=httpx.MockTransport(fail))
        self.assertEqual(result["status"], "NOT_VERIFIED")

    def test_missing_credentials(self):
        with patch.dict(os.environ, {"TEST_PROVIDER_KEY": ""}):
            self.assertEqual(self.call()["status"], "NOT_VERIFIED")

    def test_demo_never_calls_network(self):
        with patch(
            "integrations.apisetu.httpx.Client",
            side_effect=AssertionError("Network called"),
        ):
            self.assertEqual(verify("pan", "anything", "demo")["status"], "SIMULATED")

    def test_sandbox_not_production(self):
        self.cfg["pan"]["environment"] = "sandbox"
        self.path.write_text(json.dumps(self.cfg))
        self.assertEqual(self.call()["status"], "NOT_VERIFIED")
        result = self.call(mode="sandbox")
        self.assertEqual(result["status"], "SIMULATED")
        self.assertFalse(result["authoritative"])

    def test_unapproved_host_is_rejected(self):
        self.cfg["pan"]["url"] = "http://127.0.0.1/private"
        self.path.write_text(json.dumps(self.cfg))
        self.assertEqual(self.call()["status"], "NOT_VERIFIED")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(
            os.environ,
            {
                "BIDLENS_DB_PATH": str(Path(self.temp.name) / "state.sqlite3"),
                "BIDLENS_UPLOAD_DIR": str((Path(self.temp.name) / "uploads").resolve()),
                "BIDLENS_API_KEY": KEY,
                "BIDLENS_OFFICER_NAME": "Test officer",
                "APISETU_CONFIG_PATH": "",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.headers = {"X-BidLens-Key": KEY}

    def post(self, path, **kwargs):
        return self.client.post(path, headers=self.headers, **kwargs)

    def tender(self, req=None):
        response = self.post(
            "/document/tender/confirm",
            json={
                "tender_id": "SYNTHETIC/TENDER/1",
                "title": "Synthetic test tender",
                "requirements": req or REQ,
                "required_checks": ["pan"],
                "confirmation_note": "Synthetic test scope; PAN required for this fixture.",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["tender"]

    def upload(self, text=BID):
        response = self.post(
            "/document/upload",
            files={"file": ("synthetic.pdf", pdf(text), "application/pdf")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def run_audit(self, text=BID, req=None, mode="live"):
        tender = self.tender(req)
        doc = self.upload(text)
        response = self.post(
            "/audit/run",
            json={
                "file_ids": [doc["file_id"]],
                "tender_version_id": tender["version_id"],
                "mode": mode,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["results"]

    def test_authentication_required(self):
        self.assertEqual(self.client.get("/document/list").status_code, 401)
        self.assertEqual(self.client.post("/audit/run", json={}).status_code, 401)

    def test_missing_server_key_fails_closed(self):
        with patch.dict(os.environ, {"BIDLENS_API_KEY": ""}):
            self.assertEqual(self.client.get("/document/list").status_code, 503)

    def test_legacy_extension_rejected(self):
        self.assertEqual(
            self.post(
                "/document/upload", files={"file": ("test.doc", b"legacy")}
            ).status_code,
            400,
        )

    def test_path_names_cannot_escape_upload_directory(self):
        response = self.post(
            "/document/upload", files={"file": ("../../test.pdf", pdf(BID))}
        )
        self.assertEqual(response.status_code, 200)
        record = storage.get("document", response.json()["file_id"])
        self.assertEqual(
            Path(record["path"]).parent, (Path(self.temp.name) / "uploads").resolve()
        )

    def test_modified_upload_rejected(self):
        doc = self.upload()
        record = storage.get("document", doc["file_id"])
        Path(record["path"]).write_bytes(b"changed")
        response = self.post(
            "/audit/run",
            json={
                "file_ids": [doc["file_id"]],
                "tender_version_id": self.tender()["version_id"],
            },
        )
        self.assertEqual(response.status_code, 409)

    def test_invalid_office_container_rejected(self):
        response = self.post(
            "/document/upload", files={"file": ("fake.docx", b"not an Office document")}
        )
        self.assertEqual(response.status_code, 422)

    def test_corrupt_pdf_is_a_parse_error(self):
        response = self.post(
            "/document/upload", files={"file": ("fake.pdf", b"not a PDF")}
        )
        file_id = response.json()["file_id"]
        audit = self.post(
            "/audit/run",
            json={
                "file_ids": [file_id],
                "tender_version_id": self.tender()["version_id"],
            },
        )
        self.assertEqual(audit.status_code, 422)

    def test_saved_tender_controls_run(self):
        result = self.run_audit(req={**REQ, "min_warranty_years": 5})
        self.assertEqual(result["clause_level_decisions"][3]["status"], "FAIL")
        self.assertEqual(result["tender"]["requirements"]["min_warranty_years"], 5)
        self.assertFalse(result["is_compliant"])

    def test_restore_and_pdf_after_new_client(self):
        result = self.run_audit()
        with TestClient(app) as other:
            response = other.get(
                "/audit/status/" + result["audit_id"], headers=self.headers
            )
        self.assertEqual(response.status_code, 200)
        report = self.client.get(
            "/audit/report/pdf/" + result["audit_id"], headers=self.headers
        )
        self.assertEqual(report.status_code, 200)
        self.assertTrue(report.content.startswith(b"%PDF"))

    def test_override_recomputes_without_changing_snapshot(self):
        result = self.run_audit(BID.replace("3-Year", "1-Year"))
        response = self.post(
            "/audit/clause-override",
            json={
                "audit_id": result["audit_id"],
                "clause_id": "TENDER-WARRANTY",
                "new_status": "PASS",
                "justification": "Officer reviewed supplementary warranty evidence.",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["results"]["compliance_summary"]["failed"], 0)
        snapshot = storage.get("audit", result["audit_id"])
        self.assertEqual(snapshot["clause_level_decisions"][3]["status"], "FAIL")
        self.assertTrue(storage.verify_chain()["valid"])

    def test_officer_decision_is_separate_and_durable(self):
        result = self.run_audit()
        response = self.post(
            "/review/decision",
            json={
                "audit_id": result["audit_id"],
                "action": "REQUEST_CLARIFICATION",
                "justification": "Provide current authoritative PAN evidence.",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["results"]["officer_decision"]["actor"], "Test officer"
        )
        self.assertEqual(
            response.json()["results"]["assessment_status"], "REQUIRES_REVIEW"
        )

    def test_demo_cannot_qualify(self):
        result = self.run_audit(mode="demo")
        response = self.post(
            "/review/decision",
            json={
                "audit_id": result["audit_id"],
                "action": "APPROVE",
                "justification": "Synthetic test approval must be blocked.",
            },
        )
        self.assertEqual(response.status_code, 409)

    def test_event_tampering_detected(self):
        result = self.run_audit()
        with storage.connection() as db:
            db.execute(
                "UPDATE events SET payload='{}' WHERE aggregate_id=?",
                (result["audit_id"],),
            )
        self.assertFalse(storage.verify_chain()["valid"])
        self.assertEqual(
            self.client.get(
                "/audit/status/" + result["audit_id"], headers=self.headers
            ).status_code,
            409,
        )

    def test_snapshot_tampering_detected(self):
        result = self.run_audit()
        snapshot = storage.get("audit", result["audit_id"])
        snapshot["mode"] = "changed"
        with storage.connection() as db:
            db.execute(
                "UPDATE records SET payload=? WHERE kind=? AND id=?",
                (storage.canonical(snapshot), "audit", result["audit_id"]),
            )
        self.assertEqual(
            self.client.get(
                "/audit/status/" + result["audit_id"], headers=self.headers
            ).status_code,
            409,
        )

    def test_real_reference_subset_available(self):
        response = self.client.get("/system/reference/nic2008/26", headers=self.headers)
        self.assertIn("computer", response.json()["description"])
        self.assertIn("mospi.gov.in", response.json()["source_url"])


if __name__ == "__main__":
    unittest.main()
