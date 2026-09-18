import unittest
from adapters.court import get_court_adapter
from adapters.jail import get_jail_adapter
from core.db import get_ohio_coverage_summary, get_remaining_counties


class TestBatchExpansionAdapters(unittest.TestCase):
    def test_new_court_adapters_resolution(self):
        """Verify all 20 CourtView court adapters resolve from registry."""
        courts = [
            "wood_oh", "union_oh", "ross_oh", "allen_oh", "knox_oh", "belmont_oh", "greene_oh",
            "richland_oh", "paulding_oh", "pickaway_oh", "perry_oh", "henry_oh", "coshocton_oh",
            "guernsey_oh", "muskingum_oh", "meigs_oh", "erie_oh", "athens_oh", "morgan_oh", "jackson_oh"
        ]
        for cid in courts:
            adapter = get_court_adapter(cid)
            self.assertIsNotNone(adapter, f"Failed to resolve court adapter for {cid}")
            curl = adapter.generate_curl_command()
            self.assertIn("curl", curl)
            self.assertIn("eservices", curl)

    def test_caselook_court_adapters_resolution(self):
        """Verify all 15 Henschen CaseLook court adapters resolve from registry."""
        caselook_courts = [
            "fulton_oh", "lawrence_oh", "monroe_oh", "noble_oh", "vinton_oh", "crawford_oh",
            "carroll_oh", "gallia_oh", "harrison_oh", "marion_oh", "mercer_oh", "ottawa_oh",
            "pike_oh", "washington_oh", "williams_oh"
        ]
        for cid in caselook_courts:
            adapter = get_court_adapter(cid)
            self.assertIsNotNone(adapter, f"Failed to resolve CaseLook adapter for {cid}")
            curl = adapter.generate_curl_command()
            self.assertIn("curl", curl)

    def test_lucas_court_adapter_resolution(self):
        """Verify Lucas County Tyler Odyssey court adapter resolves from registry."""
        adapter = get_court_adapter("lucas_oh")
        self.assertIsNotNone(adapter)
        curl = adapter.generate_curl_command()
        self.assertIn("curl", curl)
        self.assertIn("portal-ohlucas.tylertech.cloud", curl)

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
        """Verify updated Ohio coverage summary reflects 87 covered and 1 remaining."""
        s = get_ohio_coverage_summary()
        self.assertEqual(s["total_counties"], 88)
        self.assertEqual(s["covered_counties"], 87)
        self.assertEqual(s["remaining_counties"], 1)
        self.assertEqual(len(s["both"]), 11)
        self.assertEqual(len(s["court_only"]), 37)
        self.assertEqual(len(s["jail_only"]), 39)
        self.assertAlmostEqual(s["percent_covered"], 98.9, delta=0.5)

        rem = get_remaining_counties("neither")
        self.assertEqual(len(rem), 1)
        self.assertEqual(rem[0]["county"], "Licking")


if __name__ == "__main__":
    unittest.main()
