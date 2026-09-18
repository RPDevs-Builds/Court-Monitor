import unittest
import json
import tempfile
from pathlib import Path
from adapters.court import get_court_adapter, TylerCourtAdapter, ClevelandMunicipalCourtAdapter


MOCK_SMART_SEARCH_RESULTS_HTML = """
<div id="SmartSearchResults">
    <table class="k-grid-table">
        <tbody>
            <tr>
                <td><a href="/CMCPORTAL/Case/CaseDetail?caseId=1001">2026-CRB-001234</a></td>
                <td>CITY OF CLEVELAND vs. DOE, JOHN</td>
                <td>08/15/2026</td>
                <td>Active</td>
                <td>Judge Smith</td>
            </tr>
            <tr>
                <td><a href="/CMCPORTAL/Case/CaseDetail?caseId=1002">2026-TRD-005678</a></td>
                <td>CITY OF CLEVELAND vs. ROE, JANE</td>
                <td>09/01/2026</td>
                <td>Adjudicated</td>
                <td>Judge Jones</td>
            </tr>
        </tbody>
    </table>
</div>
"""

MOCK_CASE_DETAIL_ROA_HTML = """
<div class="register-of-actions">
    <div class="case-header">
        <h1>Case #: 2026-CRB-001234</h1>
        <div class="case-title">CITY OF CLEVELAND vs. DOE, JOHN</div>
    </div>
    <div class="party-information">
        <div class="party-info">DOE, JOHN | Defendant</div>
        <div class="party-info">CITY OF CLEVELAND | Plaintiff</div>
    </div>
    <table class="roa-table">
        <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Description</th>
        </tr>
        <tr>
            <td>08/15/2026</td>
            <td>Complaint</td>
            <td>Complaint filed for Assault ORC 2903.13</td>
        </tr>
        <tr>
            <td>08/16/2026</td>
            <td>Arraignment</td>
            <td>Arraignment held before Judge Smith. Plea of Not Guilty entered.</td>
        </tr>
        <tr>
            <td>08/20/2026</td>
            <td>Bond</td>
            <td>Bond set at $5,000 Personal Recognizance</td>
        </tr>
    </table>
</div>
"""


class TestTylerCourtAdapter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_registry_resolution(self):
        adapter = get_court_adapter("cleveland_muni_oh")
        self.assertIsNotNone(adapter)
        self.assertIsInstance(adapter, ClevelandMunicipalCourtAdapter)
        self.assertIsInstance(adapter, TylerCourtAdapter)
        self.assertEqual(adapter.portal_url, "https://portal-ohcleveland.tylertech.cloud/CMCPORTAL")

    def test_headers_browser_requirements(self):
        adapter = TylerCourtAdapter(session_cache_dir=self.session_dir)
        headers = adapter.get_headers(is_ajax=True)
        self.assertEqual(headers["X-Requested-With"], "XMLHttpRequest")
        self.assertIn("Firefox", headers["User-Agent"])
        self.assertEqual(headers["Sec-Fetch-Mode"], "cors")

    def test_waf_challenge_detection(self):
        adapter = TylerCourtAdapter(session_cache_dir=self.session_dir)
        # Case 1: Status 202 with x-amzn-waf-action
        self.assertTrue(adapter.is_waf_challenge(202, {"x-amzn-waf-action": "challenge"}, ""))
        # Case 2: Status 403 with challenge header
        self.assertTrue(adapter.is_waf_challenge(403, {"x-amzn-waf-action": "challenge"}, ""))
        # Case 3: HTML with Human Verification title
        self.assertTrue(adapter.is_waf_challenge(200, {}, "<title>Human Verification</title>"))
        # Case 4: Normal 200 response
        self.assertFalse(adapter.is_waf_challenge(200, {}, "<html><title>Smart Search</title></html>"))

    def test_session_save_and_load(self):
        adapter = TylerCourtAdapter(county_id="test_court", session_cache_dir=self.session_dir)
        test_cookies = {
            "aws-waf-token": "token-xyz-123",
            "ASP.NET_SessionId": "sess-abc-456",
            "AWSALB": "alb-789"
        }
        adapter.update_cookies(test_cookies)

        # Create a new adapter instance and verify cookies loaded from disk
        adapter2 = TylerCourtAdapter(county_id="test_court", session_cache_dir=self.session_dir)
        self.assertEqual(adapter2.cookies.get("aws-waf-token"), "token-xyz-123")
        self.assertEqual(adapter2.cookies.get("ASP.NET_SessionId"), "sess-abc-456")
        self.assertIn("aws-waf-token=token-xyz-123", adapter2.get_cookie_header())

    def test_parse_smart_search_results(self):
        adapter = TylerCourtAdapter(session_cache_dir=self.session_dir)
        cases = adapter.parse_smart_search_results_html(MOCK_SMART_SEARCH_RESULTS_HTML)
        self.assertEqual(len(cases), 2)
        
        c1 = cases[0]
        self.assertEqual(c1.case_number, "2026-CRB-001234")
        self.assertEqual(c1.title, "CITY OF CLEVELAND vs. DOE, JOHN")
        self.assertEqual(c1.filing_date, "08/15/2026")
        self.assertEqual(c1.status, "Active")
        self.assertEqual(c1.judge, "Judge Smith")

        c2 = cases[1]
        self.assertEqual(c2.case_number, "2026-TRD-005678")
        self.assertEqual(c2.status, "Adjudicated")

    def test_parse_case_detail_roa(self):
        adapter = TylerCourtAdapter(session_cache_dir=self.session_dir)
        summary = adapter.parse_case_detail_html(MOCK_CASE_DETAIL_ROA_HTML, "2026-CRB-001234")
        self.assertIsNotNone(summary)
        self.assertEqual(summary.case_number, "2026-CRB-001234")
        self.assertEqual(summary.title, "CITY OF CLEVELAND vs. DOE, JOHN")
        
        # Check parties
        self.assertEqual(len(summary.parties), 2)
        self.assertEqual(summary.parties[0].role, "Defendant")
        self.assertEqual(summary.parties[0].name, "DOE, JOHN")

        # Check dockets
        self.assertEqual(summary.docket_count, 3)
        self.assertEqual(len(summary.docket_entries), 3)
        self.assertEqual(summary.docket_entries[0].sequence_id, 1)
        self.assertEqual(summary.docket_entries[0].entry_date, "08/15/2026")
        self.assertIn("Complaint filed", summary.docket_entries[0].description)

    def test_generate_curl_command(self):
        adapter = TylerCourtAdapter(session_cache_dir=self.session_dir)
        adapter.update_cookies({"aws-waf-token": "test-tok"})
        curl_cmd = adapter.generate_curl_command()
        self.assertIn("curl -s", curl_cmd)
        self.assertIn("aws-waf-token=test-tok", curl_cmd)
        self.assertIn("SmartSearchResults", curl_cmd)


class TestTylerCourtAPI(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from api import app
        self.client = TestClient(app)

    def test_session_status_endpoint(self):
        response = self.client.get("/api/court/session/cleveland_muni_oh")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["county_id"], "cleveland_muni_oh")
        self.assertIn("Cleveland", data["court_name"])
        self.assertIn("has_waf_token", data)
        self.assertIn("cookie_count", data)

    def test_search_name_cleveland_muni(self):
        from unittest.mock import patch
        from adapters.court.base import CaseSummary

        mock_cases = [
            CaseSummary(
                case_number="2026-CRB-001234",
                title="CITY OF CLEVELAND vs. DOE, JOHN",
                filing_date="08/15/2026",
                status="Active",
                judge="Judge Smith",
                court_name="Cleveland Municipal Court"
            )
        ]
        with patch("adapters.court.cleveland_muni.ClevelandMunicipalCourtAdapter.search_by_name", return_value=mock_cases):
            response = self.client.get("/api/search/name?last_name=Doe&first_name=John&county=cleveland_muni_oh")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["query"]["county"], "cleveland_muni_oh")
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["results"][0]["case_number"], "2026-CRB-001234")

    def test_search_case_cleveland_muni(self):
        from unittest.mock import patch
        from adapters.court.base import CaseSummary

        mock_case = CaseSummary(
            case_number="2026-CRB-001234",
            title="CITY OF CLEVELAND vs. DOE, JOHN",
            filing_date="08/15/2026",
            status="Active",
            judge="Judge Smith",
            court_name="Cleveland Municipal Court"
        )
        with patch("adapters.court.cleveland_muni.ClevelandMunicipalCourtAdapter.search_by_case", return_value=mock_case):
            response = self.client.get("/api/search/case?case=2026-CRB-001234&county=cleveland_muni_oh")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["query"]["county"], "cleveland_muni_oh")
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["results"][0]["case_number"], "2026-CRB-001234")

    def test_docket_cleveland_muni(self):
        from unittest.mock import patch
        from adapters.court.base import DocketEntry

        mock_entries = [
            DocketEntry(sequence_id=1, entry_date="08/15/2026", action="Complaint", description="Assault charge filed")
        ]
        with patch("adapters.court.cleveland_muni.ClevelandMunicipalCourtAdapter.get_docket", return_value=mock_entries):
            response = self.client.get("/api/docket/2026-CRB-001234?county=cleveland_muni_oh")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["county"], "cleveland_muni_oh")
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["entries"][0]["description"], "Assault charge filed")


if __name__ == "__main__":
    unittest.main()

