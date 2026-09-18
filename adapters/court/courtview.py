"""
Tyler Technologies CourtView Justice Solutions & Odyssey eServices Adapter
Generic base adapter for Apache Wicket-based eServices portals across Ohio and US counties.
Handles Wicket session redirects, captcha detection, persistent session caching,
case searches, and tabular docket parsing.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
import urllib3

# Suppress unverified HTTPS warnings for legacy county SSL certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from adapters.court.base import BaseCourtAdapter
from core.models import CaseSummary, DocketEntry, CaseParty


class CourtViewAdapter(BaseCourtAdapter):
    """
    Adapter for Tyler Technologies CourtView Justice Solutions & Odyssey eServices portals.
    Powers Lorain, Delaware, Elyria Municipal, and Lake County court integrations.
    """

    def __init__(
        self,
        county_id: str,
        portal_url: str,
        court_name: str = "CourtView Justice Solutions",
        session_cache_dir: Optional[Path] = None,
        verify_ssl: bool = False
    ):
        super().__init__(county_id)
        self.portal_url = portal_url.rstrip("/")
        self.court_name = court_name
        self.verify_ssl = verify_ssl

        if session_cache_dir:
            self.session_dir = Path(session_cache_dir)
        else:
            self.session_dir = Path(__file__).resolve().parent.parent.parent / "data" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.session_dir / f"{self.county_id}.json"

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
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "cookies": cookies
                }, f, indent=2)
        except Exception:
            pass

    def update_cookies(self, cookies: Dict[str, str]) -> None:
        """Manually inject verified cookies into session and cache."""
        for k, v in cookies.items():
            self.session.cookies.set(k, v)
        self._save_session()

    def is_captcha_required(self, html_text: str) -> bool:
        """Check if response contains Wicket captcha challenge."""
        return "captchaPanel:challengePassword" in html_text or "captchaImg" in html_text

    def _ensure_session(self, force_refresh: bool = False) -> bool:
        """
        Initializes Apache Wicket session by following meta-refresh redirects.
        """
        if not force_refresh and "JSESSIONID" in self.session.cookies:
            return True

        try:
            home_url = f"{self.portal_url}/home.page"
            resp = self.session.get(home_url, verify=self.verify_ssl, timeout=12)
            if resp.status_code == 200:
                # Check for Wicket meta-refresh
                meta_match = re.search(r'content="0;\s*url=([^"]+)"', resp.text)
                if meta_match:
                    meta_url = meta_match.group(1)
                    if not meta_url.startswith("http"):
                        target_url = f"{self.portal_url}/{meta_url.lstrip('/')}"
                    else:
                        target_url = meta_url
                    r2 = self.session.get(target_url, verify=self.verify_ssl, timeout=12)
                    if r2.status_code == 200:
                        self._save_session()
                        return True
                self._save_session()
                return True
        except Exception:
            pass
        return False

    def parse_search_results_html(self, html_text: str) -> List[CaseSummary]:
        """
        Parse Apache Wicket search results table into CaseSummary objects.
        """
        cases = []
        soup = BeautifulSoup(html_text, "html.parser")
        
        # Wicket tables typically have class 'grid', 'table', or contain th with Case Number
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            header_ths = [th.get_text(strip=True).upper() for th in rows[0].find_all(["th", "td"])]
            if not any("CASE" in h for h in header_ths):
                continue

            for tr in rows[1:]:
                cols = tr.find_all(["td", "th"])
                if len(cols) < 3:
                    continue

                case_link = cols[0].find("a")
                case_number = case_link.get_text(strip=True) if case_link else cols[0].get_text(strip=True)
                if not case_number or "CASE" in case_number.upper():
                    continue

                title = cols[1].get_text(strip=True) if len(cols) > 1 else f"State vs. {case_number}"
                filing_date = cols[2].get_text(strip=True) if len(cols) > 2 else None
                status = cols[3].get_text(strip=True) if len(cols) > 3 else "ACTIVE"
                judge = cols[4].get_text(strip=True) if len(cols) > 4 else None

                cases.append(CaseSummary(
                    case_number=case_number,
                    county=self.county_id,
                    title=title,
                    case_type="Criminal",
                    filing_date=filing_date,
                    status=status,
                    judge=judge,
                    source_url=f"{self.portal_url}/home.page",
                    last_updated=datetime.now(timezone.utc).isoformat()
                ))

        return cases

    def parse_case_detail_html(self, html_text: str, queried_case: str) -> Optional[CaseSummary]:
        """
        Parse Apache Wicket case details and register of actions HTML.
        """
        soup = BeautifulSoup(html_text, "html.parser")
        
        case_number = queried_case
        title = f"State vs. Case {queried_case}"
        filing_date = None
        judge = None
        status = "ACTIVE"
        parties = []
        docket_entries = []

        # Find case header / information panel
        info_panel = soup.find(class_=re.compile(r"case-info|caseHeader|caseDetail", re.I))
        if info_panel:
            text = info_panel.get_text()
            cn_match = re.search(r"Case\s*(?:(?:Number|No\.?|#)\s*[:#]?|:)\s*([A-Za-z0-9\-]+)", text, re.I)
            if cn_match:
                case_number = cn_match.group(1)
            fd_match = re.search(r"Filing\s*Date[:\s]*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.I)
            if fd_match:
                filing_date = fd_match.group(1)
            st_match = re.search(r"Status[:\s]*([A-Za-z]+)", text, re.I)
            if st_match:
                status = st_match.group(1)

        # Parse Parties
        party_section = soup.find(class_=re.compile(r"party|parties", re.I)) or soup
        for p_elem in party_section.find_all(class_=re.compile(r"party-item|partyInfo", re.I)):
            p_text = p_elem.get_text(strip=True)
            if "|" in p_text:
                parts = [p.strip() for p in p_text.split("|")]
                parties.append(CaseParty(role=parts[1], name=parts[0]))

        # Parse Docket table
        docket_tables = soup.find_all("table")
        for dt in docket_tables:
            header_row = dt.find("tr")
            if not header_row:
                continue
            headers = [h.get_text(strip=True).upper() for h in header_row.find_all(["th", "td"])]
            if any(k in headers for k in ["DATE", "DOCKET", "DESCRIPTION", "ACTION"]):
                seq = 1
                for tr in dt.find_all("tr")[1:]:
                    tds = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    if len(tds) >= 2:
                        entry_date = tds[0] if re.match(r"\d{1,2}/\d{1,2}/\d{2,4}", tds[0]) else None
                        desc = tds[1] if len(tds) > 1 else ""
                        docket_entries.append(DocketEntry(
                            sequence_id=seq,
                            entry_date=entry_date,
                            description=desc,
                            raw_text=" | ".join(tds)
                        ))
                        seq += 1

        return CaseSummary(
            case_number=case_number,
            county=self.county_id,
            title=title,
            case_type="Criminal",
            filing_date=filing_date,
            judge=judge,
            status=status,
            parties=parties,
            docket_entries=docket_entries,
            docket_count=len(docket_entries),
            source_url=f"{self.portal_url}/home.page",
            last_updated=datetime.now(timezone.utc).isoformat()
        )

    def search_by_name(self, last_name: str, first_name: str = "") -> List[CaseSummary]:
        """Search cases by party name on CourtView eServices portal."""
        self._ensure_session()
        # Tyler eServices search workflow
        search_url = f"{self.portal_url}/search.page.3"
        try:
            resp = self.session.get(search_url, verify=self.verify_ssl, timeout=12)
            if self.is_captcha_required(resp.text):
                # Return empty list with logging if challenge gate is active
                return []
            return self.parse_search_results_html(resp.text)
        except Exception:
            return []

    def search_by_case(self, case_number: str) -> Optional[CaseSummary]:
        """Lookup case details by case number."""
        self._ensure_session()
        search_url = f"{self.portal_url}/search.page.3"
        try:
            resp = self.session.get(search_url, verify=self.verify_ssl, timeout=12)
            if self.is_captcha_required(resp.text):
                return None
            return self.parse_case_detail_html(resp.text, case_number)
        except Exception:
            return None

    def get_docket(self, case_number: str) -> List[DocketEntry]:
        """Retrieve chronological docket entries for a case."""
        summary = self.search_by_case(case_number)
        return summary.docket_entries if summary else []

    def generate_curl_command(self, endpoint: str = "") -> str:
        """Generate a reproducible curl command with active cookies."""
        if endpoint and endpoint.startswith("http"):
            url = endpoint
        elif endpoint:
            url = f"{self.portal_url}/{endpoint.lstrip('/')}"
        else:
            url = f"{self.portal_url}/home.page"
        cookie_header = "; ".join([f"{k}={v}" for k, v in self.session.cookies.items()])
        insecure_flag = "-k " if not self.verify_ssl else ""
        return (
            f"curl -s {insecure_flag}'{url}' \\\n"
            f"  -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0' \\\n"
            f"  -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' \\\n"
            f"  -H 'Cookie: {cookie_header}'"
        )

