"""
Franklin County Municipal & Common Pleas Court Adapter (Columbus, Ohio)
Interacts with Franklin County Case Information Online (CIO) powered by IBM WebSphere / Java EE Servlet 3.1.
"""

import json
import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

from adapters.court.base import BaseCourtAdapter
from core.models import CaseSummary, DocketEntry, CaseParty


class FranklinCourtAdapter(BaseCourtAdapter):
    """
    Adapter for Franklin County Case Information Online (CIO).
    Handles dynamic disclaimer session acceptance, criminal name search,
    case number search, and full chronological docket / charges extraction.
    """

    DEFAULT_BASE_URL = "https://fcdcfcjs.co.franklin.oh.us/CaseInformationOnline"

    def __init__(
        self,
        county_id: str = "franklin_oh",
        base_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(county_id)
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.court_name = "Franklin County Municipal & Common Pleas Court"
        
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

    def _ensure_session(self, force_refresh: bool = False) -> bool:
        """
        Accepts terms of service/disclaimer and establishes active JSESSIONID.
        """
        if not force_refresh and "JSESSIONID" in self.session.cookies:
            return True

        try:
            landing_url = f"{self.base_url}/"
            resp = self.session.get(landing_url, timeout=12)
            if resp.status_code != 200:
                return False

            soup = BeautifulSoup(resp.text, "html.parser")
            form = soup.find("form", id="search") or soup.find("form")
            if not form:
                return False

            action = form.get("action", "")
            if not action:
                return False

            if action.startswith("/"):
                post_url = f"https://fcdcfcjs.co.franklin.oh.us{action}"
            else:
                post_url = f"{self.base_url}/{action}"

            disclaimer_data = {
                "fromPage": "index",
                "Accept": "ACCEPT"
            }
            accept_resp = self.session.post(post_url, data=disclaimer_data, timeout=12)
            if accept_resp.status_code == 200:
                self._save_session()
                return True
        except Exception:
            pass
        return False

    def parse_name_search_html(self, html_text: str) -> List[CaseSummary]:
        """Parse Case Listing HTML table into CaseSummary objects."""
        cases = []
        soup = BeautifulSoup(html_text, "html.parser")
        table = soup.find("table")
        if not table:
            return cases

        rows = table.find_all("tr")
        for tr in rows[1:]:
            cols = tr.find_all(["td", "th"])
            if len(cols) < 5:
                continue

            # Col 0: CASE (input submit or text)
            case_input = cols[0].find("input", {"name": "alinkvalue"}) or cols[0].find("input")
            if case_input and case_input.get("value"):
                case_number = case_input.get("value").strip()
            else:
                case_link = cols[0].find("a")
                case_number = case_link.get_text(strip=True) if case_link else cols[0].get_text(strip=True)

            if not case_number or case_number.upper() == "CASE":
                continue

            case_type = cols[1].get_text(strip=True) if len(cols) > 1 else "Criminal"
            party_name = cols[2].get_text(strip=True) if len(cols) > 2 else ""
            dob = cols[6].get_text(strip=True) if len(cols) > 6 else ""
            case_desc = cols[7].get_text(strip=True) if len(cols) > 7 else ""
            filing_date = cols[8].get_text(strip=True) if len(cols) > 8 else ""
            status = cols[9].get_text(strip=True) if len(cols) > 9 else "CLOSED"

            title = case_desc if case_desc else f"STATE OF OHIO vs. {party_name}"

            parties = []
            if party_name:
                parties.append(CaseParty(role="Defendant", name=party_name))

            summary = CaseSummary(
                case_number=case_number,
                county=self.county_id,
                title=title,
                case_type=case_type,
                filing_date=filing_date,
                status=status,
                parties=parties,
                source_url=f"{self.base_url}/caseSearch",
                last_updated=datetime.now(timezone.utc).isoformat()
            )
            cases.append(summary)

        return cases

    def parse_case_detail_html(self, html_text: str, queried_case: str) -> Optional[CaseSummary]:
        """Parse Criminal Case Detail page HTML into structured CaseSummary."""
        soup = BeautifulSoup(html_text, "html.parser")
        tables = soup.find_all("table")
        if not tables:
            return None

        case_number = queried_case
        filing_date = None
        status = "ACTIVE"
        judge = None
        parties = []
        docket_entries = []

        # Table 0: Metadata (Case Number, Date Filed, Status)
        # TR 0: ['CASE NUMBER', 'HOW FILED', 'DATE FILED', 'MUNICIPALITY', 'COMP', 'ARREST DATE', 'STATUS']
        # TR 1: ['', '24 CR 001000', 'INDICTMENT', '02/22/2024', 'CPD', '24CRA2492', '02/13/2024', 'CLOSED']
        if len(tables) > 0:
            tr_rows = tables[0].find_all("tr")
            if len(tr_rows) > 1:
                tds = [td.get_text(strip=True) for td in tr_rows[1].find_all(["td", "th"])]
                non_empty = [t for t in tds if t]
                if len(non_empty) >= 4:
                    case_number = non_empty[0]
                    filing_date = non_empty[2]
                    status = non_empty[-1]

        # Table 1: Judge, Courtroom, Prosecutor
        # TR 1: ['', 'MARK A SERROTT', 'COURTROOM 6E...', '...']
        if len(tables) > 1:
            tr_rows = tables[1].find_all("tr")
            if len(tr_rows) > 1:
                tds = [td.get_text(strip=True) for td in tr_rows[1].find_all(["td", "th"])]
                non_empty = [t for t in tds if t]
                if non_empty:
                    judge = non_empty[0]

        # Table 2: Name & Attorney
        # TR 1: ['', 'DORIAN C HIGHT', 'JACOB B WILLIAMS', ...]
        if len(tables) > 2:
            tr_rows = tables[2].find_all("tr")
            if len(tr_rows) > 1:
                tds = [td.get_text(strip=True) for td in tr_rows[1].find_all(["td", "th"])]
                non_empty = [t for t in tds if t]
                if non_empty:
                    def_name = non_empty[0]
                    atty_name = non_empty[1] if len(non_empty) > 1 else None
                    parties.append(CaseParty(role="Defendant", name=def_name, attorney=atty_name))

        # Table 5: Chronological Docket Entries
        # Row format: ['Date', 'Charge Level', 'Description', 'Image', 'Fiche', 'Frame', 'Pages']
        if len(tables) > 5:
            docket_table = tables[5]
            seq = 1
            for tr in docket_table.find_all("tr"):
                tds = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if not tds:
                    continue
                # Skip header row or detail sub-rows
                if "Date" in tds or "REASON FAIL DESC:" in tds:
                    continue
                # A primary docket row has filing date in column 1
                if len(tds) >= 4 and re.match(r"\d{2}/\d{2}/\d{2,4}", tds[1]):
                    entry_date = tds[1]
                    desc = tds[3]
                    if len(tds) > 4 and tds[4]:
                        desc += f" (Fiche: {tds[4]})"
                    docket_entries.append(DocketEntry(
                        sequence_id=seq,
                        entry_date=entry_date,
                        description=desc,
                        docket_type=tds[2] if len(tds) > 2 else None,
                        raw_text=" | ".join([t for t in tds if t])
                    ))
                    seq += 1

        title = f"STATE OF OHIO vs. {parties[0].name}" if parties else f"State vs. Case {case_number}"

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
            source_url=f"{self.base_url}/caseSearch",
            last_updated=datetime.now(timezone.utc).isoformat()
        )

    def search_by_name(self, last_name: str, first_name: str = "") -> List[CaseSummary]:
        """Search criminal cases by defendant last and first name."""
        self._ensure_session()
        search_url = f"{self.base_url}/nameSearch"
        payload = {
            "attyIdx": "",
            "advFlag": "",
            "reallySubmit": "true",
            "lname": last_name.strip(),
            "fname": first_name.strip(),
            "mint": "",
            "selType": "Criminal",
            "caseYear": "",
            "caseYear_h": "",
            "caseType": "",
            "caseType_h": "",
            "caseSeq": "",
            "caseSeq_h": "",
            "personType": "P",
            "attyNum": "",
            "txtCalendar1": "",
            "txtCalendar2": "",
            "recs": "50"
        }

        try:
            resp = self.session.post(search_url, data=payload, timeout=15)
            # If session timed out (redirected to index or 500), refresh session and retry once
            if resp.status_code == 500 or "acceptDisclaimer" in resp.text:
                self._ensure_session(force_refresh=True)
                resp = self.session.post(search_url, data=payload, timeout=15)

            if resp.status_code == 200:
                return self.parse_name_search_html(resp.text)
        except Exception:
            pass
        return []

    def _normalize_case_number(self, case_number: str) -> Optional[Dict[str, str]]:
        """
        Parse common Ohio case numbers into Franklin County CIO format:
        e.g., '24 CR 001000', '2024-CR-001000', '24CR001000' ->
        {'year': '24', 'type': 'CR', 'seq': '001000'}
        """
        clean = case_number.strip().upper()
        m = re.search(r"(\d{2,4})\s*[-/ ]?\s*([A-Za-z]{2})\s*[-/ ]?\s*(\d{1,6})", clean)
        if m:
            year = m.group(1)[-2:]
            case_type = m.group(2)
            seq = m.group(3).zfill(6)
            return {"year": year, "type": case_type, "seq": seq}
        return None

    def search_by_case(self, case_number: str) -> Optional[CaseSummary]:
        """Lookup full criminal case summary and docket by case number."""
        parsed = self._normalize_case_number(case_number)
        if not parsed:
            return None

        self._ensure_session()
        case_search_url = f"{self.base_url}/caseSearch"
        payload = {
            "attyIdx": "",
            "advFlag": "",
            "reallySubmit": "true",
            "lname": "",
            "fname": "",
            "mint": "",
            "selType": "Criminal",
            "caseYear": parsed["year"],
            "caseYear_h": parsed["year"],
            "caseType": parsed["type"],
            "caseType_h": parsed["type"],
            "caseSeq": parsed["seq"],
            "caseSeq_h": parsed["seq"],
            "personType": "P",
            "attyNum": "",
            "txtCalendar1": "",
            "txtCalendar2": "",
            "recs": "25"
        }

        try:
            resp = self.session.post(case_search_url, data=payload, timeout=15)
            if resp.status_code == 500 or "acceptDisclaimer" in resp.text:
                self._ensure_session(force_refresh=True)
                resp = self.session.post(case_search_url, data=payload, timeout=15)

            if resp.status_code == 200:
                formatted_case = f"{parsed['year']} {parsed['type']} {parsed['seq']}"
                return self.parse_case_detail_html(resp.text, formatted_case)
        except Exception:
            pass
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
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
        else:
            url = f"{self.base_url}/nameSearch"
        cookie_header = "; ".join([f"{k}={v}" for k, v in self.session.cookies.items()])
        return (
            f"curl -s '{url}' \\\n"
            f"  -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0' \\\n"
            f"  -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' \\\n"
            f"  -H 'Cookie: {cookie_header}'"
        )

