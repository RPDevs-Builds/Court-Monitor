"""
Henschen & Associates CaseLook Court Records Adapter
Generic base adapter for Henschen CaseLook portals across Ohio courts.
Handles disclaimer acceptance, session persistence, CAPTCHA detection,
case/name searches, and docket parsing.
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


class HenschenCaseLookAdapter(BaseCourtAdapter):
    """
    Adapter for Henschen & Associates CaseLook court management systems.
    Powers Fulton, Lawrence, Monroe, Noble, Vinton, and Crawford county courts.
    """

    def __init__(
        self,
        county_id: str,
        base_url: str,
        agency_id: str,
        court_name: str = "Henschen CaseLook Court",
        session_cache_dir: Optional[Path] = None,
        verify_ssl: bool = False
    ):
        super().__init__(county_id)
        self.base_url = base_url.rstrip("/")
        self.agency_id = str(agency_id)
        self.court_name = court_name
        self.verify_ssl = verify_ssl

        if session_cache_dir:
            self.session_dir = Path(session_cache_dir)
        else:
            self.session_dir = Path(__file__).resolve().parent.parent.parent / "data" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.session_dir / f"caselook_{self.county_id}.json"

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self._load_cached_session()

    def _load_cached_session(self) -> None:
        """Load session cookies from cache if available."""
        if self.session_file.exists():
            try:
                with open(self.session_file, "r") as f:
                    data = json.load(f)
                    cookies = data.get("cookies", {})
                    for k, v in cookies.items():
                        self.session.cookies.set(k, v)
            except Exception:
                pass

    def _save_session(self) -> None:
        """Save session cookies to cache."""
        try:
            cookies = requests.utils.dict_from_cookiejar(self.session.cookies)
            with open(self.session_file, "w") as f:
                json.dump({
                    "county_id": self.county_id,
                    "agency_id": self.agency_id,
                    "base_url": self.base_url,
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                    "cookies": cookies
                }, f, indent=2)
        except Exception:
            pass

    def _is_captcha_challenge(self, html_text: str) -> bool:
        """Check if response contains Henschen CAPTCHA challenge."""
        return "showCaptcha.php" in html_text or "captchaResponse" in html_text

    def _ensure_session(self, force_refresh: bool = False) -> bool:
        """
        Ensures active session with disclaimer acceptance completed.
        Supports both classic /recordSearch.php and modern /search/{agency_id} portals.
        """
        if not force_refresh and "PHPSESSID" in self.session.cookies:
            return True

        search_urls = [
            f"{self.base_url}/recordSearch.php?searchForm={self.agency_id}",
            f"{self.base_url}/recordSearch.php?k=searchForm{self.agency_id}",
            f"{self.base_url}/search/{self.agency_id}",
            f"{self.base_url}/disclaimer/{self.agency_id}"
        ]
        
        for search_url in search_urls:
            try:
                resp = self.session.get(search_url, verify=self.verify_ssl, timeout=12)
                if resp.status_code in (200, 302):
                    # Check for disclaimer continue / accept button
                    continue_match = re.search(r'href=[\"\x27](/?(?:recordSearch\.php)?[^\"\x27]*acceptAgreement[^\"\x27]*)[\"\x27]', resp.text, re.IGNORECASE)
                    if not continue_match:
                        continue_match = re.search(r'href=[\"\x27](/?(?:recordSearch\.php)?[^\"\x27]*accept=[^\"\x27]*)[\"\x27]', resp.text, re.IGNORECASE)
                    if not continue_match:
                        continue_match = re.search(r'href=[\"\x27](/(?:search|disclaimer)/[^\"\x27]*accept[^\"\x27]*)[\"\x27]', resp.text, re.IGNORECASE)

                    if continue_match:
                        target = continue_match.group(1)
                        if target.startswith("http://") or target.startswith("https://"):
                            accept_url = target
                        else:
                            accept_url = f"{self.base_url}/{target.lstrip('/')}"
                        r2 = self.session.get(accept_url, verify=self.verify_ssl, timeout=12)
                        if r2.status_code == 200:
                            self._save_session()
                            return True
                    self._save_session()
                    return True
            except Exception:
                pass
        return False

    def parse_search_results_html(self, html_text: str) -> List[CaseSummary]:
        """Parse CaseLook search results table into CaseSummary models."""
        cases = []
        soup = BeautifulSoup(html_text, "html.parser")
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            header_ths = [th.get_text(strip=True).upper() for th in rows[0].find_all(["th", "td"])]
            if not any("CASE" in h for h in header_ths):
                continue

            case_idx = 0
            name_idx = 1
            filed_idx = -1
            status_idx = -1

            for i, h in enumerate(header_ths):
                if "CASE" in h:
                    case_idx = i
                elif "NAME" in h or "PARTY" in h or "DEFENDANT" in h:
                    name_idx = i
                elif "DATE" in h or "FILED" in h:
                    filed_idx = i
                elif "STATUS" in h:
                    status_idx = i

            for tr in rows[1:]:
                cols = tr.find_all(["td", "th"])
                if len(cols) <= max(case_idx, name_idx):
                    continue

                case_no = cols[case_idx].get_text(strip=True)
                party_name = cols[name_idx].get_text(strip=True)
                if not case_no or len(case_no) < 3:
                    continue

                filed_date = cols[filed_idx].get_text(strip=True) if filed_idx >= 0 and filed_idx < len(cols) else None
                status = cols[status_idx].get_text(strip=True) if status_idx >= 0 and status_idx < len(cols) else "OPEN"

                cases.append(CaseSummary(
                    case_number=case_no,
                    county=self.county_id,
                    title=f"{party_name} ({self.court_name})",
                    filing_date=filed_date,
                    status=status,
                    case_type="Criminal/Traffic" if any(c in case_no for c in ["CR", "TR"]) else "Civil",
                    parties=[CaseParty(role="Defendant", name=party_name)] if party_name else [],
                    source_url=f"{self.base_url}/recordSearch.php",
                    last_updated=datetime.now(timezone.utc).isoformat()
                ))

        if cases:
            return cases

        # Check for modern CaseLook card layout (card-header + card-body)
        for header in soup.find_all(class_=re.compile(r"card-header")):
            h4 = header.find("h4")
            if not h4:
                continue
            badge = h4.find(class_=re.compile(r"badge"))
            if badge:
                badge.decompose()
            case_no = h4.get_text(strip=True)
            if not case_no or any(x in case_no.upper() for x in ["MATCHES", "SIGN IN", "CRITERIA", "NOTICE", "DISCLAIMER"]):
                continue

            body = header.find_next_sibling(class_=re.compile(r"card-body"))
            if not body:
                continue

            lines = [line.strip() for line in body.get_text("\n", strip=True).splitlines() if line.strip()]
            party = "Unknown Party"
            filed = None
            ctype = "Criminal/Traffic" if any(k in case_no.upper() for k in ["CR", "TR"]) else "Civil"
            status = "OPEN"
            charge = None

            for i, line in enumerate(lines):
                if line.startswith("Concerning:") and i + 1 < len(lines):
                    party = lines[i+1]
                elif line.startswith("Date Filed:") and i + 1 < len(lines):
                    filed = lines[i+1]
                elif line.startswith("Case Type:") and i + 1 < len(lines):
                    ctype = lines[i+1]
                elif line.startswith("Case Status:") and i + 1 < len(lines):
                    status = lines[i+1]
                elif (line.startswith("Violation:") or line.startswith("Cause of Action:")) and i + 1 < len(lines):
                    charge = lines[i+1]

            title = f"{party} - {charge}" if charge else party
            detail_link = header.find("a", href=re.compile(r"/record/|/docket/"))
            source_url = detail_link["href"] if detail_link else f"{self.base_url}/records/{self.agency_id}"

            cases.append(CaseSummary(
                case_number=case_no,
                county=self.county_id,
                title=title,
                case_type=ctype,
                filing_date=filed,
                status=status,
                parties=[CaseParty(role="Defendant", name=party)] if party != "Unknown Party" else [],
                source_url=source_url,
                last_updated=datetime.now(timezone.utc).isoformat()
            ))

        return cases

    def search_by_name(self, last_name: str, first_name: str = "") -> List[CaseSummary]:
        """Search cases by party name across legacy or modern RESTful portals."""
        self._ensure_session()
        query = f"{last_name}, {first_name}".strip(", ") if first_name else last_name

        # 1. Try modern RESTful portal endpoint (/records/{agency})
        modern_url = f"{self.base_url}/records/{self.agency_id}"
        modern_params = [
            ("searchType-case", "11"),
            ("fullName", query),
            ("caseTypes[]", '["TRC","TRD"]'),
            ("caseTypes[]", '["CRA","CRB"]'),
            ("caseTypes[]", '["CVE","CVF","CVG","CVH","CVT"]'),
            ("caseTypes[]", '["CVI"]'),
            ("caseTypes[]", '["PRK"]'),
            ("perPage", "50")
        ]
        try:
            resp = self.session.get(modern_url, params=modern_params, verify=self.verify_ssl, timeout=12)
            if resp.status_code == 200:
                results = self.parse_search_results_html(resp.text)
                if results:
                    return results
        except Exception:
            pass

        # 2. Try classic /recordSearch.php POST endpoint
        search_url = f"{self.base_url}/recordSearch.php"
        post_data = [
            ("searchName", query),
            ("searchAgency[]", self.agency_id),
            ("searchCaseType[]", "TR"),
            ("searchCaseType[]", "CR"),
            ("searchCaseType[]", "CV"),
            ("searchCaseType[]", "SM"),
            ("searchBlock", "50"),
            ("searchType", "mainSearch"),
            ("submit", "Begin Search")
        ]

        try:
            resp = self.session.post(
                search_url,
                data=post_data,
                verify=self.verify_ssl,
                timeout=12,
                headers={"Referer": f"{self.base_url}/recordSearch.php?searchForm={self.agency_id}"}
            )
            if resp.status_code == 200:
                if self._is_captcha_challenge(resp.text):
                    return []
                return self.parse_search_results_html(resp.text)
        except Exception:
            pass
        return []

    def search_by_case(self, case_number: str) -> Optional[CaseSummary]:
        """Search case summary by case number."""
        self._ensure_session()

        # 1. Try modern RESTful portal
        clean_num = "".join(filter(str.isdigit, case_number)) or case_number
        modern_url = f"{self.base_url}/records/{self.agency_id}"
        modern_params = [
            ("searchType-case", "11"),
            ("agencyId", self.agency_id),
            ("caseNumber", clean_num),
            ("caseTypes[]", '["TRC","TRD"]'),
            ("caseTypes[]", '["CRA","CRB"]'),
            ("caseTypes[]", '["CVE","CVF","CVG","CVH","CVT"]'),
            ("caseTypes[]", '["CVI"]'),
            ("caseTypes[]", '["PRK"]'),
            ("perPage", "10")
        ]
        try:
            resp = self.session.get(modern_url, params=modern_params, verify=self.verify_ssl, timeout=12)
            if resp.status_code == 200:
                results = self.parse_search_results_html(resp.text)
                for r in results:
                    if r.case_number.upper() == case_number.upper() or clean_num in r.case_number:
                        return r
                if results:
                    return results[0]
        except Exception:
            pass

        # 2. Try classic /recordSearch.php POST endpoint
        search_url = f"{self.base_url}/recordSearch.php"
        post_data = [
            ("searchCase", case_number),
            ("searchAgency[]", self.agency_id),
            ("searchCaseType[]", "TR"),
            ("searchCaseType[]", "CR"),
            ("searchCaseType[]", "CV"),
            ("searchCaseType[]", "SM"),
            ("searchBlock", "25"),
            ("searchType", "mainSearch"),
            ("submit", "Begin Search")
        ]

        try:
            resp = self.session.post(
                search_url,
                data=post_data,
                verify=self.verify_ssl,
                timeout=12,
                headers={"Referer": f"{self.base_url}/recordSearch.php?searchForm={self.agency_id}"}
            )
            if resp.status_code == 200:
                if self._is_captcha_challenge(resp.text):
                    return None
                results = self.parse_search_results_html(resp.text)
                if results:
                    return results[0]
        except Exception:
            pass
        return None

    def get_docket(self, case_number: str) -> List[DocketEntry]:
        """Fetch chronological docket entries for a case."""
        case = self.search_by_case(case_number)
        if not case or not case.source_url:
            return []

        docket_url = case.source_url.replace("/record/", "/docket/")
        try:
            resp = self.session.get(docket_url, verify=self.verify_ssl, timeout=12)
            if resp.status_code == 200:
                entries = []
                soup = BeautifulSoup(resp.text, "html.parser")
                for card in soup.find_all(class_=re.compile(r"card")):
                    header = card.find(class_=re.compile(r"card-header"))
                    if header and any(k in header.get_text().upper() for k in ["DOCKET", "ENTRIES"]):
                        body = card.find(class_=re.compile(r"card-body"))
                        if body:
                            lines = [l.strip() for l in body.get_text("\n", strip=True).splitlines() if l.strip()]
                            seq = 1
                            curr_date = None
                            for line in lines:
                                if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", line):
                                    curr_date = line
                                elif curr_date:
                                    entries.append(DocketEntry(
                                        sequence_id=seq,
                                        entry_date=curr_date,
                                        description=line,
                                        raw_text=f"{curr_date} - {line}"
                                    ))
                                    seq += 1
                                    curr_date = None
                return entries
        except Exception:
            pass
        return []

    def generate_curl_command(self, query: str = "SMITH", search_type: str = "name") -> str:
        """Generate copy-pasteable curl command for manual inspection."""
        cookie_header = "; ".join([f"{k}={v}" for k, v in self.session.cookies.items()]) or "PHPSESSID=session_placeholder"
        data_arg = f"--data 'searchName={query}&searchAgency[]={self.agency_id}&searchType=mainSearch&submit=Begin+Search'"
        return (
            f"curl -s -k -X POST '{self.base_url}/recordSearch.php' \\\n"
            f"  -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64)' \\\n"
            f"  -H 'Cookie: {cookie_header}' \\\n"
            f"  -H 'Referer: {self.base_url}/recordSearch.php?searchForm={self.agency_id}' \\\n"
            f"  {data_arg}"
        )

    def check_session_status(self) -> Dict[str, Any]:
        """Check status of session and disclaimer state."""
        has_cookie = "PHPSESSID" in self.session.cookies
        return {
            "county_id": self.county_id,
            "agency_id": self.agency_id,
            "portal_url": self.base_url,
            "has_session_cookie": has_cookie,
            "session_file": str(self.session_file),
            "cookies": list(self.session.cookies.keys())
        }
