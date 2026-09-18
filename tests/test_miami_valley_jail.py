"""
Unit & Integration Tests for Miami Valley Jails Consortium Adapter (*.miamivalleyjails.org)
Covers Montgomery, Butler, Warren, Clark, Greene, Miami, Darke, and Preble counties.
"""

import unittest
from unittest.mock import patch, MagicMock
import tempfile
import json
from pathlib import Path
from fastapi.testclient import TestClient

from adapters.jail import get_jail_adapter, MiamiValleyJailAdapter
from core.models import InmateRecord, CustodyCheckResult
from api import app


MOCK_MIAMI_VALLEY_ROSTER_HTML = """
<html>
<body>
    <table class="DatatableInner" id="ctl00_ContentPlaceHolder1_SearchGrid" style="width:100%;">
        <thead>
            <tr>
                <th>INMATE NAME</th>
                <th>BOOKING DATE</th>
                <th>INMATE ID</th>
                <th>AGE</th>
                <th>CHARGES</th>
            </tr>
        </thead>
        <tbody>
            <tr class="DataRow">
                <td>SMITH, JOHN ALLEN</td>
                <td>08/14/2026</td>
                <td>BCO2600123</td>
                <td>42</td>
                <td>FELONIOUS ASSAULT - F2</td>
            </tr>
            <tr class="AltDataRow">
                <td>MILLER, SARAH JANE</td>
                <td>09/01/2026</td>
                <td>BCO2600456</td>
                <td>29</td>
                <td>THEFT - M1</td>
            </tr>
        </tbody>
    </table>
</body>
</html>
"""

MOCK_MIAMI_VALLEY_CAPTCHA_HTML = """
<html>
<head><title>Persons Currently In Custody</title></head>
<body>
    <form action="/CheckCaptcha.ASPX">
        <div id="ctl00_ContentPlaceHolder1_CheckCaptcha1_Panel1">
            <img id="ctl00_ContentPlaceHolder1_CheckCaptcha1_ASPxCaptcha1_IMG" src="/DXB.axd?DXCache=abc12345" />
            <label>Type the code shown:</label>
            <input name="ctl00$ContentPlaceHolder1$CheckCaptcha1$ASPxCaptcha1$TB" type="text" />
            <input type="submit" value="Continue" />
        </div>
    </form>
</body>
</html>
"""


class TestMiamiValleyJailAdapter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_dir = Path(self.temp_dir.name)
        self.adapter = MiamiValleyJailAdapter(
            county_id="butler_oh",
            subdomain="butler",
            session_cache_dir=self.session_dir,
            verify_ssl=False
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_registry_resolution_all_counties(self):
        expected_counties = [
            ("montgomery_oh", "mont"),
            ("butler_oh", "butler"),
            ("warren_oh", "warren"),
            ("clark_oh", "clark"),
            ("greene_oh", "greene"),
            ("miami_oh", "miami"),
            ("darke_oh", "darke"),
            ("preble_oh", "preble"),
        ]
        for cid, expected_sub in expected_counties:
            adapter = get_jail_adapter(cid)
            self.assertIsNotNone(adapter, f"Failed resolving jail adapter for {cid}")
            self.assertIsInstance(adapter, MiamiValleyJailAdapter)
            self.assertEqual(adapter.county_id, cid)
            self.assertEqual(adapter.subdomain, expected_sub)
            self.assertIn(expected_sub, adapter.base_url)

    def test_session_persistence(self):
        self.adapter.update_cookies({"ASP.NET_SessionId": "TEST_ASP_SESSION_ID_999"})
        self.assertEqual(self.adapter.session.cookies.get("ASP.NET_SessionId"), "TEST_ASP_SESSION_ID_999")

        session_file = self.session_dir / "miami_valley_butler_oh.json"
        self.assertTrue(session_file.exists())
        with open(session_file, "r") as f:
            data = json.load(f)
            self.assertEqual(data["county_id"], "butler_oh")
            self.assertEqual(data["cookies"]["ASP.NET_SessionId"], "TEST_ASP_SESSION_ID_999")

        # Re-instance and verify cached session loaded
        adapter2 = MiamiValleyJailAdapter(
            county_id="butler_oh",
            session_cache_dir=self.session_dir
        )
        self.assertEqual(adapter2.session.cookies.get("ASP.NET_SessionId"), "TEST_ASP_SESSION_ID_999")

    def test_captcha_challenge_detection(self):
        self.assertTrue(self.adapter.is_captcha_challenge(MOCK_MIAMI_VALLEY_CAPTCHA_HTML, "https://butler.miamivalleyjails.org/CheckCaptcha.ASPX"))
        self.assertFalse(self.adapter.is_captcha_challenge(MOCK_MIAMI_VALLEY_ROSTER_HTML, "https://butler.miamivalleyjails.org/SearchJail.ASPX"))

    def test_parse_roster_html(self):
        inmates = self.adapter.parse_roster_html(MOCK_MIAMI_VALLEY_ROSTER_HTML)
        self.assertEqual(len(inmates), 2)

        i1 = inmates[0]
        self.assertEqual(i1.full_name, "SMITH, JOHN ALLEN")
        self.assertEqual(i1.first_name, "JOHN")
        self.assertEqual(i1.last_name, "SMITH")
        self.assertEqual(i1.middle_name, "ALLEN")
        self.assertEqual(i1.booking_date, "08/14/2026")
        self.assertEqual(i1.inmate_id, "BCO2600123")
        self.assertEqual(i1.age, 42)
        self.assertIn("FELONIOUS ASSAULT - F2", i1.charges)

        i2 = inmates[1]
        self.assertEqual(i2.full_name, "MILLER, SARAH JANE")
        self.assertEqual(i2.age, 29)
        self.assertIn("THEFT - M1", i2.charges)

    def test_check_custody_match(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_MIAMI_VALLEY_ROSTER_HTML
        mock_resp.url = "https://butler.miamivalleyjails.org/SearchJail.ASPX"

        with patch.object(self.adapter.session, "get", return_value=mock_resp):
            res = self.adapter.check_custody("John Smith")
            self.assertTrue(res.is_in_custody)
            self.assertEqual(res.total_matches, 1)
            self.assertEqual(res.matches[0].full_name, "SMITH, JOHN ALLEN")

    def test_generate_curl_command(self):
        self.adapter.update_cookies({"ASP.NET_SessionId": "ACTIVE_SESSION_VAL"})
        cmd = self.adapter.generate_curl_command("Smith")
        self.assertIn("curl -s -k", cmd)
        self.assertIn("SearchJail.ASPX?txtLast=Smith", cmd)
        self.assertIn("ASP.NET_SessionId=ACTIVE_SESSION_VAL", cmd)


class TestMiamiValleyJailAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_jail_status_endpoint_butler(self):
        mock_result = CustodyCheckResult(
            queried_name="John Smith",
            is_in_custody=True,
            total_matches=1,
            matches=[
                InmateRecord(
                    inmate_id="BCO2600123",
                    county="butler_oh",
                    full_name="SMITH, JOHN ALLEN",
                    first_name="JOHN",
                    last_name="SMITH",
                    booking_date="08/14/2026",
                    age=42,
                    charges=["FELONIOUS ASSAULT - F2"]
                )
            ],
            queried_counties=["butler_oh"]
        )
        with patch("adapters.jail.miami_valley.MiamiValleyJailAdapter.check_custody", return_value=mock_result):
            resp = self.client.get("/api/jail/butler_oh/status?name=John+Smith")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data["is_in_custody"])
            self.assertEqual(data["total_matches"], 1)
            self.assertEqual(data["matches"][0]["inmate_id"], "BCO2600123")


if __name__ == "__main__":
    unittest.main()
