#!/usr/bin/env python3
"""
Cuyahoga County Sheriff Jail Inmate Feed Client
Reverses and interfaces directly with the OCV Sheriff Mobile App backend API.
"""

import datetime
import json
import urllib.request
from typing import Dict, List, Optional, Any

FEED_URL = "https://myocv.s3.us-east-1.amazonaws.com/ocvapps/a26544113/Cuyahogainmates.json"
FALLBACK_URL = "https://apps.myocv.com/feed/rtjb/a26544113/Inmates"

class CuyahogaJailClient:
    def __init__(self, feed_url: str = FEED_URL):
        self.feed_url = feed_url

    def fetch_roster(self) -> List[Dict[str, Any]]:
        """Fetch the full live inmate roster from the Sheriff backend."""
        headers = {
            "User-Agent": "CuyahogaSheriffApp/Android",
            "Accept": "application/json"
        }
        req = urllib.request.Request(self.feed_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except Exception as e:
            print(f"[-] Error fetching primary roster: {e}, trying fallback...")
            req2 = urllib.request.Request(FALLBACK_URL, headers=headers)
            with urllib.request.urlopen(req2, timeout=15) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                # Parse HTML format if returned from fallback
                results = []
                for item in raw:
                    results.append({
                        "name": item.get("title", ""),
                        "raw_content": item.get("content", ""),
                        "images": item.get("images", [])
                    })
                return results

    def search_inmate(self, name_query: str) -> List[Dict[str, Any]]:
        """Search current jail roster for matching name."""
        roster = self.fetch_roster()
        query = name_query.strip().upper()
        matches = []
        for inmate in roster:
            name = inmate.get("name", "").upper()
            if query in name:
                matches.append(inmate)
        return matches

    def check_custody_status(self, full_name: str) -> Dict[str, Any]:
        """Check if a specific person is currently booked in Cuyahoga County Jail."""
        parts = [p.strip().upper() for p in full_name.replace(",", " ").split() if p.strip()]
        roster = self.fetch_roster()
        matches = []
        for inmate in roster:
            name = inmate.get("name", "").upper()
            # Match if all major name parts are in inmate name
            if all(part in name for part in parts):
                matches.append(inmate)

        return {
            "query": full_name,
            "in_custody": len(matches) > 0,
            "total_matches": len(matches),
            "matches": matches,
            "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

if __name__ == "__main__":
    client = CuyahogaJailClient()
    res = client.check_custody_status("Caitlin O'Boyle")
    print(json.dumps(res, indent=2))
