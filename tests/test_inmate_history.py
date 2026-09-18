import unittest
from fastapi.testclient import TestClient
from core.db import get_inmate_history, get_subject_timeline, normalize_name
from api import app


class TestInmateHistoryAndDisambiguation(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_multi_profile_detection_anthony_smith(self):
        tl = get_subject_timeline("ANTHONY SMITH")
        self.assertTrue(tl.get("multiple_profiles_detected"))
        profiles = tl.get("profiles_detected", [])
        self.assertGreaterEqual(len(profiles), 2)
        ages = {p.get("age") for p in profiles}
        self.assertIn(58, ages)
        self.assertIn(34, ages)

    def test_filter_by_age_anthony_smith(self):
        # Filter for age 58 (Cuyahoga)
        tl_58 = get_subject_timeline("ANTHONY SMITH", age=58)
        self.assertEqual(tl_58["total_events"], 1)
        event_58 = tl_58["events"][0]
        self.assertEqual(event_58["county"], "cuyahoga_oh")
        self.assertEqual(event_58["details"]["age"], 58)
        self.assertEqual(event_58["details"]["inmate_id"], "0156529")

        # Filter for age 34 (Jefferson)
        tl_34 = get_subject_timeline("ANTHONY SMITH", age=34)
        self.assertEqual(tl_34["total_events"], 1)
        event_34 = tl_34["events"][0]
        self.assertEqual(event_34["county"], "jefferson_oh")
        self.assertEqual(event_34["details"]["age"], 34)
        self.assertEqual(event_34["details"]["inmate_id"], "114823")

    def test_filter_by_age_michael_miller(self):
        # Two distinct inmates in same county (cuyahoga_oh), age 60 and age 35
        tl_60 = get_subject_timeline("MICHAEL MILLER", age=60)
        self.assertEqual(tl_60["total_events"], 1)
        self.assertEqual(tl_60["events"][0]["details"]["age"], 60)
        self.assertEqual(tl_60["events"][0]["details"]["inmate_id"], "0145693")

        tl_35 = get_subject_timeline("MICHAEL MILLER", age=35)
        self.assertEqual(tl_35["total_events"], 1)
        self.assertEqual(tl_35["events"][0]["details"]["age"], 35)
        self.assertEqual(tl_35["events"][0]["details"]["inmate_id"], "0283376")

    def test_get_inmate_history_db(self):
        recs = get_inmate_history(name="MICHAEL MILLER", age=35)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["inmate_id"], "0283376")
        self.assertEqual(recs[0]["age"], 35)

    def test_api_timeline_endpoints(self):
        # Test without filter returns multiple profiles
        res = self.client.get("/api/db/timeline/ANTHONY SMITH")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["multiple_profiles_detected"])
        self.assertGreaterEqual(len(data["profiles_detected"]), 2)

        # Test with age filter
        res58 = self.client.get("/api/db/timeline/ANTHONY SMITH?age=58")
        self.assertEqual(res58.status_code, 200)
        data58 = res58.json()
        self.assertEqual(data58["total_events"], 1)
        self.assertEqual(data58["events"][0]["details"]["age"], 58)

    def test_api_history_inmates_endpoint(self):
        res = self.client.get("/api/history/inmates?name=MICHAEL%20MILLER&age=60")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["age"], 60)
        self.assertEqual(data[0]["inmate_id"], "0145693")


if __name__ == "__main__":
    unittest.main()
