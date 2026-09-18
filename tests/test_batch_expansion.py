import unittest
from adapters.court import get_court_adapter
from adapters.jail import get_jail_adapter
from core.db import get_ohio_coverage_summary, get_remaining_counties


class TestBatchExpansionAdapters(unittest.TestCase):
    def test_new_court_adapters_resolution(self):
        """Verify all 7 new CourtView court adapters resolve from registry."""
        courts = ["wood_oh", "union_oh", "ross_oh", "allen_oh", "knox_oh", "belmont_oh", "greene_oh"]
        for cid in courts:
            adapter = get_court_adapter(cid)
            self.assertIsNotNone(adapter, f"Failed to resolve court adapter for {cid}")
            curl = adapter.generate_curl_command()
            self.assertIn("curl", curl)
            self.assertIn("eservices", curl)

    def test_new_jail_feeds_resolution(self):
        """Verify all 10 new Miami Valley jail feeds resolve from registry."""
        jails = [
            ("adams_oh", "adams"),
            ("brown_oh", "brown"),
            ("clermont_oh", "clermont"),
            ("clinton_oh", "clinton"),
            ("highland_oh", "highland"),
            ("logan_oh", "logan"),
            ("ross_oh", "ross"),
            ("shelby_oh", "shelby"),
            ("champaign_oh", "tricounty"),
            ("union_oh", "tricounty")
        ]
        for cid, expected_sub in jails:
            adapter = get_jail_adapter(cid)
            self.assertIsNotNone(adapter, f"Failed to resolve jail adapter for {cid}")
            self.assertEqual(adapter.subdomain, expected_sub)
            curl = adapter.generate_curl_command()
            self.assertIn("curl", curl)
            self.assertIn("miamivalleyjails.org", curl)

    def test_updated_coverage_metrics(self):
        """Verify updated Ohio coverage summary reflects 59 covered and 29 remaining."""
        s = get_ohio_coverage_summary()
        self.assertEqual(s["total_counties"], 88)
        self.assertEqual(s["covered_counties"], 59)
        self.assertEqual(s["remaining_counties"], 29)
        self.assertEqual(len(s["both"]), 10)
        self.assertEqual(len(s["court_only"]), 9)
        self.assertEqual(len(s["jail_only"]), 40)
        self.assertAlmostEqual(s["percent_covered"], 67.0, delta=0.5)

        rem = get_remaining_counties("neither")
        self.assertEqual(len(rem), 29)


if __name__ == "__main__":
    unittest.main()
