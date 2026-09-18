"""
Montgomery County Common Pleas & Municipal Court Adapter (Dayton, Ohio)
Interfaces with Montgomery County Public Records Online v3 (PROv3) at https://pro.mcohio.org/
Supports session management, reCAPTCHA challenge handling, case search, and docket parsing.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from adapters.court.base import BaseCourtAdapter
from core.models import CaseSummary, DocketEntry, CaseParty


class MontgomeryCourtAdapter(BaseCourtAdapter):
    """
    Adapter for Montgomery County PROv3 portal (Dayton, OH).
    Handles decoupled ASP.NET AJAX helpers under /Helpers/.
    """
    BASE_URL = "https://pro.mcohio.org"
    RECAPTCHA_SITE_KEY = "6LcIVYQcAAAAAB3UDYAT2rh-EelDlT7i48-tTvhv"

    def __init__(
        self,
        county_id: str = "montgomery_oh",
        court_name: str = "Montgomery County Common Pleas & Municipal Court",
        session_cache_dir: Optional[Path] = None,
        verify_ssl: bool = False
    ):
        super().__init__(county_id)
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
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.BASE_URL}/Default.cshtml"
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
        """Manually inject verified session cookies."""
        for k, v in cookies.items():
            self.session.cookies.set(k, v)
        self._save_session()

    def _ensure_session(self) -> bool:
        """Initialize session cookies via initializeSession.aspx."""
        if "ASP.NET_SessionId" in self.session.cookies:
            return True
        try:
            resp = self.session.get(f"{self.BASE_URL}/Helpers/initializeSession.aspx", verify=self.verify_ssl, timeout=10)
            if resp.status_code == 200:
                self._save_session()
                return True
        except Exception:
            pass
        return False

    def parse_name_search_html(self, html_text: str) -> List[CaseSummary]:
        """Parse tabular generalSearchResults.aspx HTML into CaseSummary objects."""
        cases = []
        soup = BeautifulSoup(html_text, "html.parser")
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            for row in rows[1:]:
                cols = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if len(cols) < 3:
                    continue

                case_num = cols[0]
                if not case_num or "CASE" in case_num.upper():
                    continue

                title = cols[1] if len(cols) > 1 else f"State vs. {case_num}"
                filing_date = cols[2] if len(cols) > 2 and re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", cols[2]) else None
                status = cols[3] if len(cols) > 3 else "ACTIVE"
                judge = cols[4] if len(cols) > 4 else None

                cases.append(CaseSummary(
                    case_number=case_num,
                    county=self.county_id,
                    title=title,
                    case_type="Criminal",
                    filing_date=filing_date,
                    status=status,
                    judge=judge,
                    court_name=self.court_name,
                    source_url=f"{self.BASE_URL}/Default.cshtml",
                    last_updated=datetime.now(timezone.utc).isoformat()
                ))

        return cases

    def parse_case_detail_html(self, html_text: str, case_number: str) -> Optional[CaseSummary]:
        """Parse caseInformation.aspx detail and docket HTML."""
        soup = BeautifulSoup(html_text, "html.parser")
        title = f"State vs. {case_number}"
        filing_date = None
        judge = None
        status = "ACTIVE"
        parties = []
        docket_entries = []

        # Header metadata
        for p in soup.find_all(["p", "div", "span"]):
            text = p.get_text(strip=True)
            if "Judge:" in text:
                judge = text.split("Judge:", 1)[1].strip()
            elif "Status:" in text:
                status = text.split("Status:", 1)[1].strip()
            elif "Filing Date:" in text:
                filing_date = text.split("Filing Date:", 1)[1].strip()

        # Docket table
        tables = soup.find_all("table")
        for table in tables:
            headers = [th.get_text(strip=True).upper() for th in table.find_all(["th", "td"])]
            if any(h in headers for h in ["DATE", "DOCKET", "DESCRIPTION", "ACTION"]):
                seq = 1
                for tr in table.find_all("tr")[1:]:
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
            court_name=self.court_name,
            source_url=f"{self.BASE_URL}/Default.cshtml",
            last_updated=datetime.now(timezone.utc).isoformat()
        )

    def search_by_name(self, last_name: str, first_name: str = "", captcha_token: str = "") -> List[CaseSummary]:
        """Search cases by party name on Montgomery PROv3."""
        self._ensure_session()
        url = f"{self.BASE_URL}/Helpers/generalSearchResults.aspx"
        payload = {
            "last_name": last_name,
            "first_name": first_name,
            "searchType": "name",
            "gen_case_type": "ALL",
            "captchaToken": captcha_token
        }
        try:
            resp = self.session.post(url, data=payload, verify=self.verify_ssl, timeout=12)
            if resp.status_code == 200:
                return self.parse_name_search_html(resp.text)
            elif resp.status_code == 500:
                print("[!] Montgomery PRO requires a valid reCAPTCHA v3 token for unauthenticated general search.")
                return []
        except Exception as e:
            print(f"[-] Montgomery search error: {e}")
        return []

    def search_by_case(self, case_number: str) -> Optional[CaseSummary]:
        """Lookup case details by case number on Montgomery PROv3."""
        self._ensure_session()
        url = f"{self.BASE_URL}/Helpers/caseInformation.aspx"
        payload = {
            "case_id": case_number,
            "screen": "docket"
        }
        try:
            resp = self.session.post(url, data=payload, verify=self.verify_ssl, timeout=12)
            if resp.status_code == 200:
                return self.parse_case_detail_html(resp.text, case_number)
        except Exception as e:
            print(f"[-] Montgomery case detail error: {e}")
        return None

    def get_docket(self, case_number: str) -> List[DocketEntry]:
        """Retrieve complete chronological docket entries for a case."""
        summary = self.search_by_case(case_number)
        return summary.docket_entries if summary else []

    def generate_curl_command(self, endpoint: str = "") -> str:
        """Generate curl command reproducing authenticated search."""
        cookie_header = "; ".join([f"{k}={v}" for k, v in self.session.cookies.items()])
        insecure_flag = "-k " if not self.verify_ssl else ""
        target = f"{self.BASE_URL}/{endpoint.lstrip('/')}" if endpoint else f"{self.BASE_URL}/Default.cshtml"
        return (
            f"curl -s {insecure_flag}'{target}' \\\n"
            f"  -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0' \\\n"
            f"  -H 'X-Requested-With: XMLHttpRequest' \\\n"
            f"  -H 'Cookie: {cookie_header}'"
        )
