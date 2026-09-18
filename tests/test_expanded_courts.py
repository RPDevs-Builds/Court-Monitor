"""
Unit & Integration Tests for Expanded Ohio Courts:
- Montgomery County PROv3 (Dayton)
- Medina County Tyler Odyssey Portal
- Butler County CourtView
- Portage County CourtView
- Mahoning County CourtView (Youngstown)
"""

import unittest
from unittest.mock import patch, MagicMock
import tempfile
import json
from pathlib import Path
from fastapi.testclient import TestClient

from adapters.court import (
    get_court_adapter,
    MontgomeryCourtAdapter,
    MedinaCourtAdapter,
    ButlerCourtAdapter,
    PortageCourtAdapter,
    MahoningCourtAdapter,
    TylerCourtAdapter,
    CourtViewAdapter
)
from adapters.court.base import CaseSummary, DocketEntry, CaseParty
from api import app


MOCK_MONTGOMERY_SEARCH_RESULTS_HTML = """
<html>
<body>
    <table id="tblResults" class="table table-striped table-bordered">
        <thead>
            <tr>
                <th>Case Number</th>
                <th>Case Title</th>
                <th>Filing Date</th>
                <th>Status</th>
                <th>Judge</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>2024 CR 01234</td>
                <td>STATE OF OHIO -vs- DOE, JOHN</td>
                <td>03/10/2024</td>
                <td>ACTIVE</td>
                <td>E. GERALD PARKER JR</td>
            </tr>
            <tr>
                <td>2023 CV 04567</td>
                <td>FIFTH THIRD BANK -vs- SMITH, JANE</td>
                <td>11/15/2023</td>
                <td>CLOSED</td>
                <td>MARY L. WISEMAN</td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""

MOCK_MONTGOMERY_CASE_DETAIL_HTML = """
<html>
<body>
    <div id="caseHeader">
        <p>Judge: E. GERALD PARKER JR</p>
        <p>Status: ACTIVE</p>
        <p>Filing Date: 03/10/2024</p>
    </div>

    <table class="table" id="tblDocket">
        <thead>
            <tr>
                <th>Date</th>
                <th>Docket Description</th>
                <th>Amount</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>03/10/2024</td>
                <td>INDICTMENT FILED BY PROSECUTING ATTORNEY</td>
                <td>$0.00</td>
            </tr>
            <tr>
                <td>03/18/2024</td>
                <td>ARRAIGNMENT - PLEA OF NOT GUILTY ENTERED</td>
                <td>$0.00</td>
            </tr>
            <tr>
                <td>04/05/2024</td>
                <td>SCHEDULING CONFERENCE ORDER ISSUED</td>
                <td>$0.00</td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""


class TestExpandedCourtAdapters(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_registry_resolution_all(self):
        # 1. Montgomery County
        mont = get_court_adapter("montgomery_oh")
        self.assertIsNotNone(mont)
        self.assertIsInstance(mont, MontgomeryCourtAdapter)
        self.assertEqual(mont.county_id, "montgomery_oh")

        # 2. Medina County
        medina = get_court_adapter("medina_oh")
        self.assertIsNotNone(medina)
        self.assertIsInstance(medina, MedinaCourtAdapter)
        self.assertIsInstance(medina, TylerCourtAdapter)
        self.assertEqual(medina.county_id, "medina_oh")
        self.assertIn("portal-ohmedina.tylertech.cloud", medina.portal_url)

        # 3. Butler County
        butler = get_court_adapter("butler_oh")
        self.assertIsNotNone(butler)
        self.assertIsInstance(butler, ButlerCourtAdapter)
        self.assertIsInstance(butler, CourtViewAdapter)
        self.assertEqual(butler.county_id, "butler_oh")
        self.assertIn("clerkservices.bcohio.gov", butler.portal_url)

        # 4. Portage County
        portage = get_court_adapter("portage_oh")
        self.assertIsNotNone(portage)
        self.assertIsInstance(portage, PortageCourtAdapter)
        self.assertIsInstance(portage, CourtViewAdapter)
        self.assertEqual(portage.county_id, "portage_oh")
        self.assertIn("services.portageco.com", portage.portal_url)

        # 5. Mahoning County
        mahoning = get_court_adapter("mahoning_oh")
        self.assertIsNotNone(mahoning)
        self.assertIsInstance(mahoning, MahoningCourtAdapter)
        self.assertIsInstance(mahoning, CourtViewAdapter)
        self.assertEqual(mahoning.county_id, "mahoning_oh")
        self.assertIn("ecourts.mahoningcountyoh.gov", mahoning.portal_url)

    def test_montgomery_parsing(self):
        adapter = MontgomeryCourtAdapter(
            county_id="montgomery_oh",
            session_cache_dir=self.session_dir
        )
        # Search results parsing
        cases = adapter.parse_name_search_html(MOCK_MONTGOMERY_SEARCH_RESULTS_HTML)
        self.assertEqual(len(cases), 2)
        c1 = cases[0]
        self.assertEqual(c1.case_number, "2024 CR 01234")
        self.assertEqual(c1.title, "STATE OF OHIO -vs- DOE, JOHN")
        self.assertEqual(c1.filing_date, "03/10/2024")
        self.assertEqual(c1.status, "ACTIVE")
        self.assertEqual(c1.judge, "E. GERALD PARKER JR")

        # Detail parsing
        detail = adapter.parse_case_detail_html(MOCK_MONTGOMERY_CASE_DETAIL_HTML, "2024 CR 01234")
        self.assertIsNotNone(detail)
        self.assertEqual(detail.case_number, "2024 CR 01234")
        self.assertEqual(detail.judge, "E. GERALD PARKER JR")
        self.assertEqual(detail.status, "ACTIVE")
        self.assertEqual(detail.filing_date, "03/10/2024")
        self.assertEqual(detail.docket_count, 3)
        self.assertEqual(len(detail.docket_entries), 3)
        self.assertEqual(detail.docket_entries[0].sequence_id, 1)
        self.assertEqual(detail.docket_entries[0].entry_date, "03/10/2024")
        self.assertIn("INDICTMENT FILED", detail.docket_entries[0].description)

    def test_montgomery_curl_command(self):
        adapter = MontgomeryCourtAdapter(
            county_id="montgomery_oh",
            session_cache_dir=self.session_dir
        )
        adapter.update_cookies({"ASP.NET_SessionId": "MONTGOMERY_SESSION_123"})
        cmd = adapter.generate_curl_command("Helpers/caseInformation.aspx")
        self.assertIn("curl -s -k", cmd)
        self.assertIn("Helpers/caseInformation.aspx", cmd)
        self.assertIn("MONTGOMERY_SESSION_123", cmd)


class TestExpandedCourtsAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_search_name_montgomery(self):
        mock_cases = [
            CaseSummary(
                case_number="2024 CR 01234",
                county="montgomery_oh",
                title="STATE OF OHIO -vs- DOE, JOHN",
                filing_date="03/10/2024",
                status="ACTIVE",
                court_name="Montgomery County Common Pleas & Municipal Court"
            )
        ]
        with patch("adapters.court.montgomery.MontgomeryCourtAdapter.search_by_name", return_value=mock_cases):
            resp = self.client.get("/api/search/name?last_name=DOE&first_name=JOHN&county=montgomery_oh")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["results"][0]["case_number"], "2024 CR 01234")
            self.assertEqual(data["query"]["county"], "montgomery_oh")

    def test_search_case_medina(self):
        mock_case = CaseSummary(
            case_number="24CR0099",
            county="medina_oh",
            title="STATE vs. BROWN, CHRIS",
            filing_date="01/20/2024",
            status="PENDING",
            court_name="Medina County Common Pleas Court"
        )
        with patch("adapters.court.medina.MedinaCourtAdapter.search_by_case", return_value=mock_case):
            resp = self.client.get("/api/search/case?case=24CR0099&county=medina_oh")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["results"][0]["case_number"], "24CR0099")
            self.assertEqual(data["query"]["county"], "medina_oh")

    def test_docket_butler(self):
        mock_dockets = [
            DocketEntry(sequence_id=1, entry_date="02/14/2024", description="COMPLAINT FILED")
        ]
        with patch("adapters.court.butler.ButlerCourtAdapter.get_docket", return_value=mock_dockets):
            resp = self.client.get("/api/docket/CV20240100?county=butler_oh")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["entries"][0]["description"], "COMPLAINT FILED")


if __name__ == "__main__":
    unittest.main()
