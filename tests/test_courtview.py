"""
Unit & Integration Tests for Tyler CourtView & Odyssey eServices Court Adapters & API
"""

import unittest
from unittest.mock import patch, MagicMock
import tempfile
import json
from pathlib import Path
from fastapi.testclient import TestClient

from adapters.court import get_court_adapter, CourtViewAdapter, LorainCourtAdapter, DelawareCourtAdapter
from adapters.court.base import CaseSummary, DocketEntry, CaseParty
from api import app


MOCK_WICKET_SEARCH_RESULTS_HTML = """
<html>
<body>
    <table class="grid">
        <thead>
            <tr>
                <th>Case Number</th>
                <th>Style / Title</th>
                <th>Filing Date</th>
                <th>Status</th>
                <th>Judge</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><a href="./case.page?x=abc123">24CR050123</a></td>
                <td>STATE OF OHIO vs. DOE, JOHN</td>
                <td>01/15/2024</td>
                <td>OPEN</td>
                <td>HON. RAYMOND J. EWERS</td>
            </tr>
            <tr>
                <td><a href="./case.page?x=def456">23CV010456</a></td>
                <td>BANK OF AMERICA vs. SMITH, JANE</td>
                <td>11/20/2023</td>
                <td>CLOSED</td>
                <td>HON. MARK BETLESKI</td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""

MOCK_WICKET_CASE_DETAIL_HTML = """
<html>
<body>
    <div class="case-info">
        <h3>Case Information</h3>
        <p>Case Number: 24CR050123</p>
        <p>Filing Date: 01/15/2024</p>
        <p>Status: PENDING</p>
    </div>

    <div class="party-list">
        <h4>Parties</h4>
        <div class="party-item">DOE, JOHN | DEFENDANT</div>
        <div class="party-item">STATE OF OHIO | PLAINTIFF</div>
    </div>

    <table class="docket-table">
        <thead>
            <tr>
                <th>Date</th>
                <th>Docket Entry / Action</th>
                <th>Filing Party</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>01/15/2024</td>
                <td>INDICTMENT FILED BY GRAND JURY</td>
                <td>PROSECUTING ATTORNEY</td>
            </tr>
            <tr>
                <td>01/22/2024</td>
                <td>ARRAIGNMENT HELD - PLEA OF NOT GUILTY ENTERED</td>
                <td>COURT</td>
            </tr>
            <tr>
                <td>02/10/2024</td>
                <td>PRE-TRIAL CONFERENCE SCHEDULED</td>
                <td>COURT</td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""

MOCK_WICKET_CAPTCHA_HTML = """
<html>
<body>
    <div id="captchaPanel">
        <img id="captchaImg" src="captcha.jpg" />
        <input type="text" name="captchaPanel:challengePassword" value="" />
        <input type="submit" value="Submit Captcha" />
    </div>
</body>
</html>
"""

MOCK_META_REFRESH_HTML = """
<html>
<head>
    <meta http-equiv="refresh" content="0; url=;jsessionid=ABCD1234EFGH5678?x=InitHome" />
</head>
<body>Redirecting...</body>
</html>
"""


class TestCourtViewAdapter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_dir = Path(self.temp_dir.name)
        self.adapter = CourtViewAdapter(
            county_id="test_courtview",
            portal_url="https://eservices.example.gov/eservices",
            court_name="Test CourtView eServices",
            session_cache_dir=self.session_dir,
            verify_ssl=False
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_registry_resolution(self):
        # Test Lorain resolution
        lorain = get_court_adapter("lorain_oh")
        self.assertIsNotNone(lorain)
        self.assertIsInstance(lorain, LorainCourtAdapter)
        self.assertEqual(lorain.county_id, "lorain_oh")
        self.assertIn("Lorain County", lorain.court_name)

        # Test Delaware resolution
        delaware = get_court_adapter("delaware_oh")
        self.assertIsNotNone(delaware)
        self.assertIsInstance(delaware, DelawareCourtAdapter)
        self.assertEqual(delaware.county_id, "delaware_oh")
        self.assertIn("Delaware County", delaware.court_name)

        # Test generic CourtView instantiation
        generic = CourtViewAdapter(county_id="test_id", portal_url="https://example.com/eservices")
        self.assertIsNotNone(generic)
        self.assertIsInstance(generic, CourtViewAdapter)

    def test_session_persistence(self):
        # Update cookies
        self.adapter.update_cookies({"JSESSIONID": "TESTSESSION123", "AWSALB": "ALBVALUE"})
        
        # Verify cookies in current session
        self.assertEqual(self.adapter.session.cookies.get("JSESSIONID"), "TESTSESSION123")
        self.assertEqual(self.adapter.session.cookies.get("AWSALB"), "ALBVALUE")

        # Verify persisted JSON file
        session_file = self.session_dir / "test_courtview.json"
        self.assertTrue(session_file.exists())
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["county_id"], "test_courtview")
            self.assertEqual(data["cookies"]["JSESSIONID"], "TESTSESSION123")

        # Create a new adapter instance and verify it restores cached cookies
        adapter2 = CourtViewAdapter(
            county_id="test_courtview",
            portal_url="https://eservices.example.gov/eservices",
            session_cache_dir=self.session_dir
        )
        self.assertEqual(adapter2.session.cookies.get("JSESSIONID"), "TESTSESSION123")

    def test_captcha_detection(self):
        self.assertTrue(self.adapter.is_captcha_required(MOCK_WICKET_CAPTCHA_HTML))
        self.assertFalse(self.adapter.is_captcha_required(MOCK_WICKET_SEARCH_RESULTS_HTML))

    def test_ensure_session_with_meta_refresh(self):
        # When JSESSIONID is missing, _ensure_session should query home.page and follow meta-refresh
        mock_resp_home = MagicMock()
        mock_resp_home.status_code = 200
        mock_resp_home.text = MOCK_META_REFRESH_HTML

        mock_resp_target = MagicMock()
        mock_resp_target.status_code = 200
        mock_resp_target.text = "<html><body>Welcome to eServices</body></html>"

        with patch.object(self.adapter.session, "get", side_effect=[mock_resp_home, mock_resp_target]) as mock_get:
            result = self.adapter._ensure_session(force_refresh=True)
            self.assertTrue(result)
            self.assertEqual(mock_get.call_count, 2)
            # Verify target URL resolved properly
            call_url = mock_get.call_args_list[1][0][0]
            self.assertIn(";jsessionid=ABCD1234EFGH5678?x=InitHome", call_url)

    def test_parse_search_results_html(self):
        cases = self.adapter.parse_search_results_html(MOCK_WICKET_SEARCH_RESULTS_HTML)
        self.assertEqual(len(cases), 2)
        
        c1 = cases[0]
        self.assertEqual(c1.case_number, "24CR050123")
        self.assertEqual(c1.title, "STATE OF OHIO vs. DOE, JOHN")
        self.assertEqual(c1.filing_date, "01/15/2024")
        self.assertEqual(c1.status, "OPEN")
        self.assertEqual(c1.judge, "HON. RAYMOND J. EWERS")

        c2 = cases[1]
        self.assertEqual(c2.case_number, "23CV010456")
        self.assertEqual(c2.status, "CLOSED")

    def test_parse_case_detail_html(self):
        summary = self.adapter.parse_case_detail_html(MOCK_WICKET_CASE_DETAIL_HTML, "24CR050123")
        self.assertIsNotNone(summary)
        self.assertEqual(summary.case_number, "24CR050123")
        self.assertEqual(summary.filing_date, "01/15/2024")
        self.assertEqual(summary.status, "PENDING")

        # Verify parties
        self.assertEqual(len(summary.parties), 2)
        self.assertEqual(summary.parties[0].name, "DOE, JOHN")
        self.assertEqual(summary.parties[0].role, "DEFENDANT")

        # Verify docket entries
        self.assertEqual(summary.docket_count, 3)
        self.assertEqual(len(summary.docket_entries), 3)
        self.assertEqual(summary.docket_entries[0].sequence_id, 1)
        self.assertEqual(summary.docket_entries[0].entry_date, "01/15/2024")
        self.assertIn("INDICTMENT FILED", summary.docket_entries[0].description)
        self.assertEqual(summary.docket_entries[1].sequence_id, 2)
        self.assertIn("ARRAIGNMENT HELD", summary.docket_entries[1].description)

    def test_generate_curl_command(self):
        self.adapter.update_cookies({"JSESSIONID": "SECURE_SESSION_XYZ"})
        curl_cmd = self.adapter.generate_curl_command("search.page.3")
        self.assertIn("curl -s -k", curl_cmd)
        self.assertIn("search.page.3", curl_cmd)
        self.assertIn("JSESSIONID=SECURE_SESSION_XYZ", curl_cmd)

    def test_search_by_name_with_captcha_fallback(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_WICKET_CAPTCHA_HTML

        with patch.object(self.adapter.session, "get", return_value=mock_resp):
            cases = self.adapter.search_by_name("DOE", "JOHN")
            # Should catch captcha challenge and return empty list cleanly
            self.assertEqual(cases, [])

    def test_search_by_case_with_captcha_fallback(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_WICKET_CAPTCHA_HTML

        with patch.object(self.adapter.session, "get", return_value=mock_resp):
            case = self.adapter.search_by_case("24CR050123")
            self.assertIsNone(case)


class TestCourtViewAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_search_name_api_lorain(self):
        mock_cases = [
            CaseSummary(
                case_number="24CR050123",
                county="lorain_oh",
                title="STATE OF OHIO vs. DOE, JOHN",
                filing_date="01/15/2024",
                status="OPEN",
                court_name="Lorain County Common Pleas Court"
            )
        ]
        with patch("adapters.court.courtview.CourtViewAdapter.search_by_name", return_value=mock_cases):
            resp = self.client.get("/api/search/name?last_name=DOE&first_name=JOHN&county=lorain_oh")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["results"][0]["case_number"], "24CR050123")
            self.assertEqual(data["query"]["county"], "lorain_oh")

    def test_search_case_api_delaware(self):
        mock_case = CaseSummary(
            case_number="24CR090999",
            county="delaware_oh",
            title="STATE OF OHIO vs. SMITH, JANE",
            filing_date="02/01/2024",
            status="PENDING",
            court_name="Delaware County Common Pleas Court"
        )
        with patch("adapters.court.courtview.CourtViewAdapter.search_by_case", return_value=mock_case):
            resp = self.client.get("/api/search/case?case=24CR090999&county=delaware_oh")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["results"][0]["case_number"], "24CR090999")
            self.assertEqual(data["query"]["county"], "delaware_oh")

    def test_docket_api_lorain(self):
        mock_dockets = [
            DocketEntry(sequence_id=1, entry_date="01/15/2024", description="INDICTMENT FILED")
        ]
        with patch("adapters.court.courtview.CourtViewAdapter.get_docket", return_value=mock_dockets):
            resp = self.client.get("/api/docket/24CR050123?county=lorain_oh")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["entries"][0]["description"], "INDICTMENT FILED")


if __name__ == "__main__":
    unittest.main()
