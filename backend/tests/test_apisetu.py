import unittest, os, sys, json, tempfile
from pathlib import Path
from unittest.mock import patch
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integrations.apisetu import verify

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


