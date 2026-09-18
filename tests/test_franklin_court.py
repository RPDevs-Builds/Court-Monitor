"""
Unit & Integration Tests for Franklin County Court Adapter & REST API
"""

import unittest
from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from adapters.court import get_court_adapter, FranklinCourtAdapter
from adapters.court.base import CaseSummary, DocketEntry, CaseParty
from api import app


MOCK_FRANKLIN_NAME_SEARCH_HTML = """
<table>
    <tr>
        <th>CASE</th>
        <th>CASE TYPE</th>
        <th>NAME</th>
        <th>ITN</th>
        <th>MALE/FEMALE</th>
        <th>PLAINTIFF/DEFENDANT</th>
        <th>DATE OF BIRTH</th>
        <th>DESCRIPTION</th>
        <th>FILED</th>
        <th>STATUS</th>
        <th>SUBSCRIBE</th>
    </tr>
    <tr>
        <td><input type="submit" name="alinkvalue" value="24 CR 001000" class="submitLink" /></td>
        <td>INDICTMENT</td>
        <td>SMITH, JOHN A</td>
        <td>161018DC</td>
        <td>M</td>
        <td>DF</td>
        <td>07/29/1967</td>
        <td>STATE OF OHIO -VS- JOHN A SMITH</td>
        <td>03/03/2024</td>
        <td>CLOSED</td>
        <td><input type="checkbox" name="caseNumber" value="24CR001000" /></td>
    </tr>
    <tr>
        <td><input type="submit" name="alinkvalue" value="24 CR 002000" class="submitLink" /></td>
        <td>INDICTMENT</td>
        <td>SMITH, JOHN B</td>
        <td></td>
        <td>M</td>
        <td>DF</td>
        <td>10/12/1985</td>
        <td>STATE OF OHIO -VS- JOHN B SMITH</td>
        <td>06/15/2024</td>
        <td>ACTIVE</td>
        <td><input type="checkbox" name="caseNumber" value="24CR002000" /></td>
    </tr>
</table>
"""

MOCK_FRANKLIN_CASE_DETAIL_HTML = """
<div>
    <!-- Table 0: Metadata -->
    <table>
        <tr>
            <th>CASE NUMBER</th>
            <th>HOW FILED</th>
            <th>DATE FILED</th>
            <th>MUNICIPALITY</th>
            <th>COMP</th>
            <th>ARREST DATE</th>
            <th>STATUS</th>
        </tr>
        <tr>
            <td></td>
            <td>24 CR 001000</td>
            <td>INDICTMENT</td>
            <td>02/22/2024</td>
            <td>CPD</td>
            <td>24CRA2492</td>
            <td>02/13/2024</td>
            <td>CLOSED</td>
        </tr>
    </table>

    <!-- Table 1: Judge, Courtroom, Prosecutor -->
    <table>
        <tr>
            <th>JUDGE</th>
            <th>COURTROOM</th>
            <th>PROSECUTOR</th>
        </tr>
        <tr>
            <td></td>
            <td>MARK A SERROTT</td>
            <td>COURTROOM 6E</td>
            <td>KATHLEEN M KENNEDY</td>
        </tr>
    </table>

    <!-- Table 2: Name & Attorney -->
    <table>
        <tr>
            <th>Name</th>
            <th>Attorney</th>
        </tr>
        <tr>
            <td></td>
            <td>DORIAN C HIGHT</td>
            <td>JACOB B WILLIAMS</td>
            <td>JACOB B WILLIAMS</td>
        </tr>
    </table>

    <!-- Table 3: Offenses -->
    <table>
        <tr><th>Offense Date</th><th>Code</th><th>Description</th></tr>
    </table>

    <!-- Table 4: Fines -->
    <table>
        <tr><td>Date</td></tr>
    </table>

    <!-- Table 5: Chronological Docket Entries -->
    <table>
        <tr>
            <th>Date</th>
            <th>Charge Level</th>
            <th>Description</th>
            <th>Image</th>
            <th>Fiche</th>
            <th>Frame</th>
            <th>Pages</th>
        </tr>
        <tr>
            <td></td>
            <td>09/18/25</td>
            <td>00</td>
            <td>NOTICE RETURNED</td>
            <td></td>
            <td>59582</td>
            <td>H48</td>
            <td>1</td>
        </tr>
        <tr>
            <td></td>
            <td>08/08/24</td>
            <td>00</td>
            <td>CAPIAS - DETAINER</td>
            <td></td>
            <td>59200</td>
            <td>A10</td>
            <td>1</td>
        </tr>
        <tr>
            <td></td>
            <td>02/22/24</td>
            <td>00</td>
            <td>INDICTMENT FILED</td>
            <td></td>
            <td>58100</td>
            <td>C05</td>
            <td>3</td>
        </tr>
    </table>
</div>
"""


class TestFranklinCourtAdapter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_dir = Path(self.temp_dir.name)
        self.adapter = FranklinCourtAdapter(
            county_id="franklin_oh",
            session_cache_dir=self.session_dir
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_registry_resolution(self):
        adapter = get_court_adapter("franklin_oh")
        self.assertIsNotNone(adapter)
        self.assertIsInstance(adapter, FranklinCourtAdapter)
        self.assertEqual(adapter.county_id, "franklin_oh")
        self.assertIn("Franklin County", adapter.court_name)

    def test_case_number_normalization(self):
        # Format 1: '24 CR 001000'
        p1 = self.adapter._normalize_case_number("24 CR 001000")
        self.assertEqual(p1, {"year": "24", "type": "CR", "seq": "001000"})

        # Format 2: '2024-CR-001000'
        p2 = self.adapter._normalize_case_number("2024-CR-001000")
        self.assertEqual(p2, {"year": "24", "type": "CR", "seq": "001000"})

        # Format 3: '24CR1000'
        p3 = self.adapter._normalize_case_number("24CR1000")
        self.assertEqual(p3, {"year": "24", "type": "CR", "seq": "001000"})

    def test_parse_name_search_html(self):
        cases = self.adapter.parse_name_search_html(MOCK_FRANKLIN_NAME_SEARCH_HTML)
        self.assertEqual(len(cases), 2)
        c1 = cases[0]
        self.assertEqual(c1.case_number, "24 CR 001000")
        self.assertEqual(c1.title, "STATE OF OHIO -VS- JOHN A SMITH")
        self.assertEqual(c1.filing_date, "03/03/2024")
        self.assertEqual(c1.status, "CLOSED")
        self.assertEqual(len(c1.parties), 1)
        self.assertEqual(c1.parties[0].name, "SMITH, JOHN A")

    def test_parse_case_detail_html(self):
        summary = self.adapter.parse_case_detail_html(MOCK_FRANKLIN_CASE_DETAIL_HTML, "24 CR 001000")
        self.assertIsNotNone(summary)
        self.assertEqual(summary.case_number, "24 CR 001000")
        self.assertEqual(summary.filing_date, "02/22/2024")
        self.assertEqual(summary.status, "CLOSED")
        self.assertEqual(summary.judge, "MARK A SERROTT")
        self.assertEqual(len(summary.parties), 1)
        self.assertEqual(summary.parties[0].name, "DORIAN C HIGHT")
        self.assertEqual(summary.parties[0].attorney, "JACOB B WILLIAMS")

        # Check docket entries
        self.assertEqual(summary.docket_count, 3)
        self.assertEqual(len(summary.docket_entries), 3)
        self.assertEqual(summary.docket_entries[0].sequence_id, 1)
        self.assertEqual(summary.docket_entries[0].entry_date, "09/18/25")
        self.assertIn("NOTICE RETURNED", summary.docket_entries[0].description)

    def test_generate_curl_command(self):
        curl_cmd = self.adapter.generate_curl_command()
        self.assertIn("curl -s", curl_cmd)
        self.assertIn("fcdcfcjs.co.franklin.oh.us", curl_cmd)


class TestFranklinCourtAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_search_name_api(self):
        mock_cases = [
            CaseSummary(
                case_number="24 CR 001000",
                title="STATE OF OHIO -VS- JOHN A SMITH",
                filing_date="03/03/2024",
                status="CLOSED",
                court_name="Franklin County Municipal & Common Pleas Court"
            )
        ]
        with patch("adapters.court.franklin.FranklinCourtAdapter.search_by_name", return_value=mock_cases):
            resp = self.client.get("/api/search/name?last_name=SMITH&first_name=JOHN&county=franklin_oh")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["results"][0]["case_number"], "24 CR 001000")

    def test_search_case_api(self):
        mock_case = CaseSummary(
            case_number="24 CR 001000",
            title="STATE OF OHIO -VS- DORIAN C HIGHT",
            filing_date="02/22/2024",
            status="CLOSED",
            judge="MARK A SERROTT"
        )
        with patch("adapters.court.franklin.FranklinCourtAdapter.search_by_case", return_value=mock_case):
            resp = self.client.get("/api/search/case?case=24CR001000&county=franklin_oh")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["results"][0]["judge"], "MARK A SERROTT")

    def test_docket_api(self):
        mock_dockets = [
            DocketEntry(sequence_id=1, entry_date="02/22/24", description="INDICTMENT FILED")
        ]
        with patch("adapters.court.franklin.FranklinCourtAdapter.get_docket", return_value=mock_dockets):
            resp = self.client.get("/api/docket/24CR001000?county=franklin_oh")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["entries"][0]["description"], "INDICTMENT FILED")


if __name__ == "__main__":
    unittest.main()
