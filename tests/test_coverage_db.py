import unittest
from fastapi.testclient import TestClient

from api import app
from core.db import get_ohio_coverage_summary, get_remaining_counties, get_db


class TestOhioCountiesDatabaseAndCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_all_88_counties_present_in_sqlite(self):
        """Verify exactly 88 primary Ohio counties exist in SQLite jurisdictions."""
        with get_db() as conn:
            rows = conn.execute("""
                SELECT county_id, county, fips, state
                FROM jurisdictions
                WHERE state = 'OH' AND (jurisdiction_type = 'county' OR jurisdiction_type IS NULL)
            """).fetchall()
        
        self.assertEqual(len(rows), 88)
        # Verify FIPS codes follow 39001 -> 39175
        fips_list = sorted([r["fips"] for r in rows if r["fips"]])
        self.assertEqual(len(fips_list), 88)
        self.assertEqual(fips_list[0], "39001")
        self.assertEqual(fips_list[-1], "39175")

    def test_coverage_summary_counts(self):
        """Verify coverage summary metrics across Ohio's 88 counties (100% milestone)."""
        s = get_ohio_coverage_summary()
        self.assertEqual(s["total_counties"], 88)
        self.assertEqual(s["covered_counties"], 88)
        self.assertEqual(len(s["both"]), 25)
        self.assertEqual(len(s["court_only"]), 38)
        self.assertEqual(len(s["jail_only"]), 25)
        self.assertEqual(s["remaining_counties"], 0)
        self.assertAlmostEqual(s["percent_covered"], 100.0, delta=0.1)

    def test_remaining_counties_filters(self):
        """Verify get_remaining_counties returns correct subsets."""
        neither = get_remaining_counties("neither")
        self.assertEqual(len(neither), 0)

        # Court missing
        court_missing = get_remaining_counties("court")
        self.assertEqual(len(court_missing), 25)

        # Jail missing
        jail_missing = get_remaining_counties("jail")
        self.assertEqual(len(jail_missing), 38)

    def test_api_coverage_endpoint(self):
        """Verify GET /api/counties/coverage."""
        response = self.client.get("/api/counties/coverage")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_counties"], 88)
        self.assertEqual(data["remaining_counties"], 0)
        self.assertIn("both", data)
        self.assertIn("neither", data)

    def test_api_remaining_endpoint(self):
        """Verify GET /api/counties/remaining."""
        response = self.client.get("/api/counties/remaining?type=neither")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["filter"], "neither")
        self.assertEqual(len(data["remaining_counties"]), 0)


if __name__ == "__main__":
    unittest.main()
