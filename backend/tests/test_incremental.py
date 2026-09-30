"""Regression tests for additive changes to the original application contract."""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from main import app
from orchestrator.govt_verify import verify_government_credentials
from orchestrator.rule_engine import evaluate_compliance
from orchestrator.orchestrator import run_full_audit
from evidence_risk.risk_scorer import compute_risk_and_value_intelligence
from routers import audit
import pymupdf

RULES = dict(min_turnover_cr=1.5, emd_required_inr=100000, min_local_content_pct=50, min_warranty_years=3, budget_inr=5000000)

class IncrementalTests(unittest.TestCase):
    def test_warranty_uses_tender_years(self):
        bid = dict(warranty='1-Year', local_content_pct=60)
        self.assertEqual(evaluate_compliance(bid, RULES)[-1]['status'], 'FAIL')
        self.assertEqual(evaluate_compliance(bid, {**RULES, 'min_warranty_years':1})[-1]['status'], 'PASS')

    def test_emd_keyword_without_amount_is_pending(self):
        clauses = evaluate_compliance(dict(emd_status='SUBMITTED', local_content_pct=60), RULES)
        self.assertEqual(next(c for c in clauses if c['clause_id']=='GFR-170-EMD')['status'], 'PENDING')

    def test_emd_amount_compares_active_tender(self):
        for amount, expected in [(50000, 'FAIL'), (100000, 'PASS')]:
            clauses = evaluate_compliance(dict(emd_status='SUBMITTED', emd_amount_inr=amount, local_content_pct=60), RULES)
            self.assertEqual(next(c for c in clauses if c['clause_id']=='GFR-170-EMD')['status'], expected)

    def test_original_gateway_contract_without_credentials(self):
        with patch.dict(os.environ, {'APISETU_CONFIG_PATH':'', 'BIDLENS_VERIFICATION_MODE':'live'}):
            result = verify_government_credentials(dict(pan='AABCT3456L', gstin='27AABCT3456L1ZV'))
        self.assertEqual(result['verified_gateways_count'], 0)
        self.assertEqual(result['total_gateways'], 6)
        self.assertTrue(all(g['status']=='NOT_VERIFIED' and g['badge']=='NEUTRAL' for g in result['gateways']))
        self.assertTrue(result['pan_gstin_consistent'])

    def test_demo_never_calls_registry(self):
        with patch.dict(os.environ, {'BIDLENS_VERIFICATION_MODE':'demo'}), patch('integrations.apisetu.httpx.Client', side_effect=AssertionError('network')):
            result = verify_government_credentials({})
        self.assertTrue(all(g['status']=='SIMULATED' for g in result['gateways']))

    def test_value_comparison_missing_quote_and_selected_budget(self):
        empty = compute_risk_and_value_intelligence({'warranty':'5-Year','bonus_perks':['Extra support']}, [], [], RULES)
        self.assertIsNone(empty['value_spotlight']['estimated_savings_inr'])
        result = compute_risk_and_value_intelligence({'total_quote_inr':400}, [], [], {'budget_inr':500})
        self.assertEqual(result['value_spotlight']['estimated_savings_inr'],100)

    def test_existing_audit_route_and_pdf(self):
        # Keep uploads/reports isolated; test the original one-file request and response contract.
        with tempfile.TemporaryDirectory() as folder, patch.object(audit, 'UPLOAD_DIR',folder), patch.object(audit,'REPORTS_DIR',folder), patch.dict(os.environ, {'APISETU_CONFIG_PATH':'', 'BIDLENS_VERIFICATION_MODE':'live'}):
            doc=pymupdf.open();page=doc.new_page();page.insert_text((40,40),'Synthetic bidder\nPAN: AABCT3456L\nGSTIN: 27AABCT3456L1ZV\nWarranty: 1-Year\nTurnover: 2 crore\nLocal Content: 60%\nEMD Submitted: INR 100000');doc.save(str(Path(folder)/'fixture.pdf'));doc.close()
            with TestClient(app) as client:
                response=client.post('/audit/run',json={'file_id':'fixture.pdf','tender_id':'TEST/RESTORED/001','tender_requirements':RULES})
                self.assertEqual(response.status_code,200,response.text)
                result=response.json()['results']
                self.assertEqual(result['tender_id'],'TEST/RESTORED/001')
                self.assertFalse(result['is_compliant'])
                self.assertEqual(next(c for c in result['clause_level_decisions'] if c['clause_id']=='SPEC-WARRANTY')['status'],'FAIL')
                report=client.get('/audit/report/pdf/fixture.pdf')
                self.assertEqual(report.status_code,200)
                pdf=pymupdf.open(stream=report.content,filetype='pdf')
                text=''.join(p.get_text() for p in pdf)
                self.assertIn('TEST/RESTORED/001',text)
                self.assertIn('CPPP',text)
                pdf.close()
            audit.AUDIT_CACHE.pop('fixture.pdf',None)

    def test_invalid_tender_threshold_rejected(self):
        with TestClient(app) as client:
            response=client.post('/audit/run',json={'file_id':'unused','tender_requirements':{'min_warranty_years':-1}})
            self.assertEqual(response.status_code,422)
