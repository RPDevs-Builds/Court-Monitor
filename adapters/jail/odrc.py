"""
Statewide Ohio Department of Rehabilitation and Correction (ODRC) Adapter.
Queries the official statewide prison, parole, and post-release control offender database.
"""

import http.cookiejar
import re
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup

from adapters.jail.base import BaseJailAdapter
from core.models import InmateRecord


BASE_URL = "https://appgateway.drc.ohio.gov/OffenderSearch"


class ODRCJailAdapter(BaseJailAdapter):
    def __init__(self, county_id: str = "odrc_statewide"):
        super().__init__(county_id)
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def fetch_roster(self) -> List[InmateRecord]:
        """ODRC contains ~50,000+ active inmates statewide; bulk fetch not recommended. Use search_inmate."""
        return []

    def search_inmate(self, name_query: str) -> List[InmateRecord]:
        parts = [p.strip() for p in name_query.replace(",", " ").split() if p.strip()]
        if not parts:
            return []
        
        last_name = parts[0]
        first_name = parts[1] if len(parts) > 1 else ""

        try:
            # 1. Acquire anti-forgery token from landing page
            req1 = urllib.request.Request(
                f"{BASE_URL}/Search/Search",
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
            )
            with self.opener.open(req1, timeout=15) as resp1:
                html1 = resp1.read().decode("utf-8")

            token_match = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', html1)
            if not token_match:
                return []
            token = token_match.group(1)

            # 2. Post search query
            post_fields = {
                "__RequestVerificationToken": token,
                "LastName": last_name,
                "FirstName": first_name,
                "Status": "A"  # All statuses (Incarcerated, Released, Parole, APA)
            }
            data = urllib.parse.urlencode(post_fields).encode("utf-8")
            req2 = urllib.request.Request(
                f"{BASE_URL}/Search/SearchResults",
                data=data,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": f"{BASE_URL}/Search/Search"
                }
            )
            with self.opener.open(req2, timeout=20) as resp2:
                html2 = resp2.read().decode("utf-8")

            return self._parse_results(html2)
        except Exception as e:
            print(f"[-] ODRC search error: {e}")
            return []

    def _parse_results(self, html: str) -> List[InmateRecord]:
        records: List[InmateRecord] = []
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", class_="table-striped")
        if not table:
            return records

        rows = table.find_all("tr")
        # Skip header row
        for tr in rows[1:]:
            cols = tr.find_all("td")
            if len(cols) < 6:
                continue

            # Col 0: Photo
            img = cols[0].find("img")
            photo_url = img.get("src") if img else None
            if photo_url and photo_url.startswith("/"):
                photo_url = f"https://appgateway.drc.ohio.gov{photo_url}"

            # Col 1: Full Name
            full_name = cols[1].get_text(strip=True)

            # Col 2: Offender Number
            num_tag = cols[2].find("a")
            offender_num = num_tag.get_text(strip=True) if num_tag else cols[2].get_text(strip=True)

            # Col 3: DOB
            dob = cols[3].get_text(strip=True)

            # Col 4: Status (e.g. INCARCERATED, RELEASED, PAROLE)
            status = cols[4].get_text(strip=True)

            # Col 5: Offenses
            offenses_text = cols[5].get_text(strip=True)
            offenses = [o.strip() for o in offenses_text.split(",") if o.strip()]

            records.append(InmateRecord(
                inmate_id=offender_num,
                county="odrc_statewide",
                full_name=full_name,
                charges=offenses,
                photo_url=photo_url,
                housing_facility=f"Ohio State Prison System (ODRC - Status: {status})",
                raw_data={"dob": dob, "status": status}
            ))

        return records
