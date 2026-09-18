"""
Miami Valley Jails Consortium Adapter (*.miamivalleyjails.org)
Provides custody monitoring and inmate roster retrieval across 8 southwest Ohio counties:
Montgomery, Butler, Warren, Clark, Greene, Miami, Darke, and Preble.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from adapters.jail.base import BaseJailAdapter
from core.models import InmateRecord, CustodyCheckResult


COUNTY_SUBDOMAINS = {
    "montgomery_oh": "mont",
    "butler_oh": "butler",
    "warren_oh": "warren",
    "clark_oh": "clark",
    "greene_oh": "greene",
    "miami_oh": "miami",
    "darke_oh": "darke",
    "preble_oh": "preble",
}


class MiamiValleyJailAdapter(BaseJailAdapter):
    """
    Adapter for the unified Miami Valley Jails platform (Microsoft-IIS / ASP.NET).
    """

    def __init__(
        self,
        county_id: str,
        subdomain: Optional[str] = None,
        session_cache_dir: Optional[Path] = None,
        verify_ssl: bool = False
    ):
        super().__init__(county_id)
        self.subdomain = subdomain or COUNTY_SUBDOMAINS.get(county_id, county_id.replace("_oh", ""))
        self.base_url = f"https://{self.subdomain}.miamivalleyjails.org"
        self.verify_ssl = verify_ssl

        if session_cache_dir:
            self.session_dir = Path(session_cache_dir)
        else:
            self.session_dir = Path(__file__).resolve().parent.parent.parent / "data" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.session_dir / f"miami_valley_{self.county_id}.json"

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self._load_cached_session()

    def _load_cached_session(self) -> None:
        """Load session cookies from persistent cache if available."""
        if self.session_file.exists():
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cookies = data.get("cookies", {})
                    for k, v in cookies.items():
                        self.session.cookies.set(k, v)
            except Exception:
                pass

    def _save_session(self) -> None:
        """Save session cookies to persistent cache."""
        try:
            cookies = self.session.cookies.get_dict()
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump({
                    "county_id": self.county_id,
                    "subdomain": self.subdomain,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "cookies": cookies
                }, f, indent=2)
        except Exception:
            pass

    def update_cookies(self, cookies: Dict[str, str]) -> None:
        """Manually inject verified session cookies (post-captcha solve)."""
        for k, v in cookies.items():
            self.session.cookies.set(k, v)
        self._save_session()

    def is_captcha_challenge(self, html_text: str, current_url: str = "") -> bool:
        """Check if response is the DevExpress captcha challenge."""
        return (
            "CheckCaptcha" in current_url
            or "CheckCaptcha.ASPX" in html_text
            or "ASPxCaptcha1" in html_text
            or "Type the code shown" in html_text
        )

    def _ensure_session(self) -> bool:
        """Initialize session cookies from home page if needed."""
        if "ASP.NET_SessionId" in self.session.cookies:
            return True
        try:
            resp = self.session.get(self.base_url, verify=self.verify_ssl, timeout=10)
            if resp.status_code == 200:
                self._save_session()
                return True
        except Exception:
            pass
        return False

    def parse_roster_html(self, html_text: str) -> List[InmateRecord]:
        """
        Parse Miami Valley Jails tabular search results into InmateRecord objects.
        Supports standard DevExpress/ASP.NET SearchGrid tables and DataRow elements.
        """
        inmates = []
        soup = BeautifulSoup(html_text, "html.parser")

        # Find search result grid
        grid = soup.find(id=re.compile(r"SearchGrid|grid|table1", re.I)) or soup.find("table", class_=re.compile(r"DatatableInner|grid", re.I))
        if not grid:
            grid = soup

        rows = grid.find_all("tr", class_=re.compile(r"DataRow|AltDataRow|row", re.I))
        if not rows:
            # Fallback to all tr with at least 3 td elements
            all_trs = grid.find_all("tr")
            rows = [tr for tr in all_trs if len(tr.find_all(["td", "th"])) >= 3 and not tr.find("th")]

        for row in rows:
            cols = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cols) < 2:
                continue

            full_name = cols[0]
            if not full_name or full_name.upper() in ("NAME", "INMATE NAME", "LAST, FIRST"):
                continue

            # Standard format: LAST, FIRST MIDDLE
            first_name = None
            last_name = None
            middle_name = None
            if "," in full_name:
                parts = [p.strip() for p in full_name.split(",", 1)]
                last_name = parts[0]
                rest = parts[1].split()
                if rest:
                    first_name = rest[0]
                    if len(rest) > 1:
                        middle_name = " ".join(rest[1:])
            else:
                name_parts = full_name.split()
                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = name_parts[-1]

            booking_date = cols[1] if len(cols) > 1 and re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", cols[1]) else None
            inmate_id = cols[2] if len(cols) > 2 else ""
            age = None
            dob = None
            charges = []

            # Check remaining columns for age, DOB, or charges
            for c in cols[2:]:
                if re.match(r"^\d{1,3}$", c) and 16 <= int(c) <= 110:
                    age = int(c)
                elif re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", c):
                    dob = c
                elif len(c) > 3 and not re.match(r"^\d+$", c):
                    charges.append(c)

            inmates.append(InmateRecord(
                inmate_id=inmate_id or f"{self.county_id}_{full_name.replace(' ', '_')}",
                county=self.county_id,
                full_name=full_name,
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                booking_date=booking_date,
                dob=dob,
                age=age,
                charges=charges,
                housing_facility=f"{self.county_id.replace('_oh', '').title()} County Jail",
                status="ACTIVE"
            ))

        return inmates

    def search_inmate(self, name_query: str) -> List[InmateRecord]:
        """Query jail roster for a specific name."""
        self._ensure_session()
        query_parts = name_query.replace(",", " ").split()
        last_name = query_parts[0] if query_parts else ""
        first_name = query_parts[1] if len(query_parts) > 1 else ""

        url = f"{self.base_url}/SearchJail.ASPX"
        params = {"txtLast": last_name}
        if first_name:
            params["txtFirst"] = first_name

        try:
            resp = self.session.get(url, params=params, verify=self.verify_ssl, timeout=12)
            if self.is_captcha_challenge(resp.text, resp.url):
                print(f"[!] Captcha challenge active on {self.base_url}. Solve via browser or inject cookie.")
                return []
            return self.parse_roster_html(resp.text)
        except Exception as e:
            print(f"[-] Search error for {self.county_id}: {e}")
            return []

    def fetch_roster(self) -> List[InmateRecord]:
        """Fetch all inmates by querying index."""
        self._ensure_session()
        # Query letter 'A' by default to get active listing
        url = f"{self.base_url}/SearchJail.ASPX"
        try:
            resp = self.session.get(url, params={"txtLast": "A"}, verify=self.verify_ssl, timeout=12)
            if self.is_captcha_challenge(resp.text, resp.url):
                return []
            return self.parse_roster_html(resp.text)
        except Exception:
            return []

    def check_custody(self, full_name: str) -> CustodyCheckResult:
        """Check custody status by executing targeted search."""
        parts = [p.strip().upper() for p in full_name.replace(",", " ").split() if p.strip()]
        candidates = self.search_inmate(full_name)
        matches = []
        for inmate in candidates:
            inmate_name = inmate.full_name.upper()
            if all(p in inmate_name for p in parts):
                matches.append(inmate)

        return CustodyCheckResult(
            queried_name=full_name,
            is_in_custody=len(matches) > 0,
            total_matches=len(matches),
            matches=matches,
            queried_counties=[self.county_id]
        )

    def generate_curl_command(self, query: str = "Smith") -> str:
        """Generate curl command reproducing authenticated search."""
        cookie_header = "; ".join([f"{k}={v}" for k, v in self.session.cookies.items()])
        insecure_flag = "-k " if not self.verify_ssl else ""
        url = f"{self.base_url}/SearchJail.ASPX?txtLast={query}"
        return (
            f"curl -s {insecure_flag}'{url}' \\\n"
            f"  -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0' \\\n"
            f"  -H 'Cookie: {cookie_header}'"
        )
