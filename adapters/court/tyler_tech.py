"""
Tyler Technologies Odyssey Portal (CMCPORTAL) Adapter.
Modular, reusable court records and docket extraction engine for any court system
utilizing Tyler Technologies Enterprise Justice / Odyssey Public Access.

Handles AWS WAF challenge detection, session management, browser-assisted CAPTCHA solving,
SmartSearch query dispatch, Kendo Grid results extraction, and Register of Actions (ROA) parsing.
"""

import os
import re
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
import requests

from adapters.court.base import BaseCourtAdapter
from core.models import CaseSummary, DocketEntry, CaseParty


DEFAULT_SESSIONS_DIR = Path("/home/llmuser/projects/court-monitor/data/sessions")


class TylerCourtAdapter(BaseCourtAdapter):
    """
    Generalized Tyler Tech Odyssey Portal (CMCPORTAL) Court Adapter.
    """
    def __init__(
        self,
        county_id: str = "cleveland_muni_oh",
        court_name: str = "Cleveland Municipal Court",
        portal_url: str = "https://portal-ohcleveland.tylertech.cloud/CMCPORTAL",
        session_cache_dir: Path = DEFAULT_SESSIONS_DIR,
        user_agent: str = "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0"
    ):
        super().__init__(county_id)
        self.court_name = court_name
        self.portal_url = portal_url.rstrip("/")
        self.session_cache_dir = Path(session_cache_dir)
        self.session_cache_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.session_cache_dir / f"{self.county_id}.json"
        
        self.user_agent = user_agent
        self.cookies: Dict[str, str] = {}
        self.http_session = requests.Session()
        
        self.load_session()

    # ------------------------------------------------------------------
    # Session, Cookie & WAF Management
    # ------------------------------------------------------------------
    def load_session(self) -> bool:
        """Load session cookies from JSON cache or environment variables."""
        loaded = False
        target_file = self.session_file
        if not target_file.exists():
            alt = self.session_cache_dir / f"{self.county_id.replace('_oh', '')}.json"
            if alt.exists():
                target_file = alt

        if target_file.exists():
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.cookies = data.get("cookies", {})
                    if data.get("user_agent"):
                        self.user_agent = data["user_agent"]
                    loaded = bool(self.cookies)
            except Exception as e:
                print(f"[-] Warning: Failed to load session cache {target_file}: {e}")

        # Check environment variable overrides
        env_waf = os.getenv(f"{self.county_id.upper()}_WAF_TOKEN") or os.getenv("TYLER_WAF_TOKEN")
        env_sess = os.getenv(f"{self.county_id.upper()}_SESSION_ID") or os.getenv("TYLER_SESSION_ID")
        if env_waf:
            self.cookies["aws-waf-token"] = env_waf
            loaded = True
        if env_sess:
            self.cookies["ASP.NET_SessionId"] = env_sess
            loaded = True

        for k, v in self.cookies.items():
            self.http_session.cookies.set(k, v)

        return loaded

    def save_session(self) -> None:
        """Persist current cookies and metadata to session cache file."""
        data = {
            "county_id": self.county_id,
            "court_name": self.court_name,
            "portal_url": self.portal_url,
            "cookies": self.cookies,
            "user_agent": self.user_agent,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")
        }
        try:
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[-] Failed to save session to {self.session_file}: {e}")

    def update_cookies(self, new_cookies: Dict[str, str]) -> None:
        """Update active cookies in memory and disk cache."""
        self.cookies.update(new_cookies)
        for k, v in self.cookies.items():
            self.http_session.cookies.set(k, v)
        self.save_session()

    def get_cookie_header(self) -> str:
        """Generate Cookie header string."""
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    def get_headers(self, is_ajax: bool = False, referer: Optional[str] = None) -> Dict[str, str]:
        """
        Construct headers adhering to Tyler UI browser requirements
        (tylerui-browser-requirements.css) and AWS WAF expectations.
        """
        ref = referer or f"{self.portal_url}/Home/WorkspaceMode?p=0"
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "*/*" if is_ajax else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": ref,
            "Sec-Fetch-Dest": "empty" if is_ajax else "document",
            "Sec-Fetch-Mode": "cors" if is_ajax else "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        }
        if is_ajax:
            headers["X-Requested-With"] = "XMLHttpRequest"
        return headers

    def is_waf_challenge(self, status_code: int, headers: Dict[str, str], text: str) -> bool:
        """Detect if AWS WAF challenge or human verification is blocking request."""
        if status_code in (202, 403):
            if "x-amzn-waf-action" in headers and headers["x-amzn-waf-action"].lower() == "challenge":
                return True
        if "<title>Human Verification</title>" in text or "challenge.js" in text:
            return True
        return False

    def solve_waf_interactive(self, timeout_sec: int = 60) -> bool:
        """
        Interactive / Headed CAPTCHA & WAF Resolution Hook.
        Launches agent-browser on DISPLAY=:0.0 so operator or automated solver can pass
        AWS WAF Human Verification, then harvests the active cookies.
        """
        print(f"[*] Launching browser session to resolve AWS WAF for {self.court_name}...")
        env = os.environ.copy()
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":0.0"

        cmd_open = ["agent-browser", "open", f"{self.portal_url}/Home/Dashboard/29"]
        try:
            subprocess.run(cmd_open, env=env, timeout=15, capture_output=True)
        except Exception as e:
            print(f"[-] Error opening browser: {e}")
            return False

        start_t = time.time()
        print(f"[*] Waiting up to {timeout_sec}s for AWS WAF challenge completion...")
        while time.time() - start_t < timeout_sec:
            time.sleep(3)
            # Query active cookies from agent-browser
            cmd_cookies = ["agent-browser", "cookies", "get"]
            res = subprocess.run(cmd_cookies, env=env, capture_output=True, text=True)
            raw = res.stdout.strip()
            
            fresh_cookies = {}
            for line in raw.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    fresh_cookies[k.strip()] = v.strip()

            if "aws-waf-token" in fresh_cookies:
                print(f"[+] Successfully harvested fresh aws-waf-token from browser!")
                self.update_cookies(fresh_cookies)
                return True

        print("[-] Timeout waiting for AWS WAF token resolution.")
        return False

    # ------------------------------------------------------------------
    # SmartSearch Dispatch & Retrieval
    # ------------------------------------------------------------------
    def submit_smart_search(
        self,
        search_query: str,
        search_by: str = "SmartSearch",
        search_cases: bool = True,
        search_warrants: bool = True,
        use_soundex: bool = True
    ) -> bool:
        """
        Submit criteria form to /SmartSearch/SmartSearch/SmartSearch.
        Returns True if criteria cookie was established.
        """
        url = f"{self.portal_url}/SmartSearch/SmartSearch/SmartSearch"
        payload = {
            "caseCriteria.SearchCriteria": search_query,
            "caseCriteria.AdvancedSearchOptionsOpen": "true",
            "caseCriteria.CourtLocation_input": "All Locations",
            "caseCriteria.CourtLocation": "All Locations",
            "caseCriteria.SearchBy_input": search_by,
            "caseCriteria.SearchBy": search_by,
            "caseCriteria.SearchCases": "true" if search_cases else "false",
            "caseCriteria.SearchWarrants": "true" if search_warrants else "false",
            "caseCriteria.SearchByPartyName": "true",
            "caseCriteria.SearchByNickName": "true",
            "caseCriteria.SearchByBusinessName": "true",
            "caseCriteria.UseSoundex": "true" if use_soundex else "false",
            "caseCriteria.DOBFrom": "",
            "caseCriteria.DOBTo": "",
            "caseCriteria.FBINumber": "",
            "caseCriteria.SONumber": "",
            "caseCriteria.BookingNumber": "",
            "caseCriteria.CaseType_input": "",
            "caseCriteria.CaseType": "",
            "caseCriteria.CaseStatus_input": "",
            "caseCriteria.CaseStatus": "",
            "caseCriteria.FileDateStart": "",
            "caseCriteria.FileDateEnd": "",
            "caseCriteria.JudicialOfficer_input": "",
            "caseCriteria.JudicialOfficer": "",
            "Search": "Submit"
        }

        headers = self.get_headers(is_ajax=False, referer=f"{self.portal_url}/Home/WorkspaceMode?p=0")
        try:
            resp = self.http_session.post(url, data=payload, headers=headers, timeout=20)
            if self.is_waf_challenge(resp.status_code, resp.headers, resp.text):
                print("[-] AWS WAF challenge intercepted SmartSearch POST.")
                return False

            # Update cookies with response set-cookie
            for k, v in resp.cookies.items():
                self.cookies[k] = v
            self.save_session()
            return "SmartSearchCriteria" in self.cookies or resp.status_code in (200, 302)
        except Exception as e:
            print(f"[-] SmartSearch submit error: {e}")
            return False

    def fetch_smart_search_results(self) -> Optional[str]:
        """Fetch results HTML partial from /SmartSearch/SmartSearchResults."""
        url = f"{self.portal_url}/SmartSearch/SmartSearchResults?_={int(time.time() * 1000)}"
        headers = self.get_headers(is_ajax=True, referer=f"{self.portal_url}/Home/WorkspaceMode?p=0")
        try:
            resp = self.http_session.get(url, headers=headers, timeout=25)
            if self.is_waf_challenge(resp.status_code, resp.headers, resp.text):
                print("[-] AWS WAF challenge intercepted SmartSearchResults GET.")
                return None
            return resp.text
        except Exception as e:
            print(f"[-] SmartSearchResults fetch error: {e}")
            return None

    # ------------------------------------------------------------------
    # HTML Parsing Engine (Kendo Grids & Register of Actions)
    # ------------------------------------------------------------------
    def parse_smart_search_results_html(self, html: str) -> List[CaseSummary]:
        """
        Parse Kendo Grid search results table into canonical CaseSummary objects.
        """
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        cases: List[CaseSummary] = []

        # Find results table / rows
        rows = soup.find_all("tr")
        for row in rows:
            tds = row.find_all("td")
            if not tds or len(tds) < 3:
                continue

            row_text = [td.get_text(strip=True) for td in tds]
            
            # Case link or identifier
            case_link = row.find("a", href=lambda h: h and ("CaseDetail" in h or "caseId" in h))
            case_num = ""
            if case_link:
                case_num = case_link.get_text(strip=True)
            elif tds[0].find("a"):
                case_num = tds[0].find("a").get_text(strip=True)
            else:
                # Try finding case number pattern (e.g. 2026 CR 12345 or 26-CRB-1234)
                for t in row_text:
                    if re.search(r"\b\d{2,4}[-\s]?[A-Z]{2,4}[-\s]?\d{3,7}\b", t, re.IGNORECASE):
                        case_num = t
                        break

            if not case_num:
                continue

            # Extract fields by column heuristics
            style_title = ""
            status = ""
            case_type = "Criminal"
            filing_date = None
            judge = None

            for t in row_text:
                if " vs " in t.lower() or " v. " in t.lower() or "city of" in t.lower() or "state of" in t.lower():
                    style_title = t
                elif re.search(r"^\d{1,2}/\d{1,2}/\d{4}$", t):
                    filing_date = t
                elif t.lower() in ("open", "closed", "inactive", "pending", "adjudicated", "active"):
                    status = t
                elif "judge" in t.lower() or "magistrate" in t.lower() or "honorable" in t.lower():
                    judge = t

            cases.append(CaseSummary(
                case_number=case_num,
                county=self.county_id,
                title=style_title or f"Case {case_num}",
                case_type=case_type,
                filing_date=filing_date,
                judge=judge,
                status=status or "Active",
                source_url=f"{self.portal_url}/Case/CaseDetail?caseNumber={case_num}"
            ))

        return cases

    def parse_case_detail_html(self, html: str, fallback_case_number: str) -> Optional[CaseSummary]:
        """
        Parse Register of Actions (ROA) / CaseDetail HTML into full CaseSummary with dockets.
        """
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        
        # Header case info
        case_num = fallback_case_number
        case_header = soup.find(class_=lambda c: c and ("case-header" in c or "portlet-summary" in c))
        if case_header:
            found_num = re.search(r"Case\s*#?:\s*([A-Z0-9-]+)", case_header.get_text(), re.IGNORECASE)
            if found_num:
                case_num = found_num.group(1).strip()

        # Title / Style
        title = ""
        style_elem = soup.find(class_=lambda c: c and ("case-title" in c or "style" in c))
        if style_elem:
            title = style_elem.get_text(strip=True)
        else:
            title = f"{self.court_name} vs. Record {case_num}"

        # Parties
        parties: List[CaseParty] = []
        party_sec = soup.find(class_=lambda c: c and "party" in c.lower())
        if party_sec:
            for p_div in party_sec.find_all(class_=lambda c: c and "party-info" in c.lower()):
                p_text = p_div.get_text(separator=" | ", strip=True)
                parties.append(CaseParty(
                    role="Defendant" if "defendant" in p_text.lower() else "Party",
                    name=p_text.split("|")[0].strip()
                ))

        # Docket entries (Register of Actions table)
        dockets: List[DocketEntry] = []
        roa_table = soup.find("table", class_=lambda c: c and ("roa" in c.lower() or "docket" in c.lower() or "events" in c.lower()))
        if roa_table:
            rows = roa_table.find_all("tr")[1:]
            for idx, r in enumerate(rows):
                tds = [td.get_text(strip=True) for td in r.find_all("td")]
                if not tds:
                    continue
                edate = tds[0] if len(tds) > 0 else None
                desc = " | ".join(tds[1:]) if len(tds) > 1 else ""
                dockets.append(DocketEntry(
                    sequence_id=idx + 1,
                    entry_date=edate,
                    description=desc,
                    docket_type="Event"
                ))

        return CaseSummary(
            case_number=case_num,
            county=self.county_id,
            title=title,
            case_type="Criminal",
            status="Active",
            parties=parties,
            docket_entries=dockets,
            docket_count=len(dockets),
            source_url=f"{self.portal_url}/Case/CaseDetail"
        )

    # ------------------------------------------------------------------
    # BaseCourtAdapter Implementation
    # ------------------------------------------------------------------
    def search_by_name(self, last_name: str, first_name: str = "") -> List[CaseSummary]:
        """Search cases by party name."""
        full_query = f"{last_name}, {first_name}".strip(", ")
        success = self.submit_smart_search(full_query, search_by="PartyName")
        if not success:
            # If WAF failed, try to load/refresh
            if not self.cookies.get("aws-waf-token"):
                self.solve_waf_interactive()
                self.submit_smart_search(full_query, search_by="PartyName")

        html = self.fetch_smart_search_results()
        if not html:
            return []
        return self.parse_smart_search_results_html(html)

    def search_by_case(self, case_number: str) -> Optional[CaseSummary]:
        """Lookup case summary by official case number."""
        success = self.submit_smart_search(case_number, search_by="SmartSearch")
        if not success:
            if not self.cookies.get("aws-waf-token"):
                self.solve_waf_interactive()
                self.submit_smart_search(case_number, search_by="SmartSearch")

        html = self.fetch_smart_search_results()
        if not html:
            return None
        cases = self.parse_smart_search_results_html(html)
        if cases:
            return cases[0]
        return None

    def get_docket(self, case_number: str) -> List[DocketEntry]:
        """Retrieve complete chronological docket entries for a case."""
        case = self.search_by_case(case_number)
        if case and case.docket_entries:
            return case.docket_entries
        return []

    def generate_curl_command(self, case_number: Optional[str] = None) -> str:
        """Generate reproducible curl command with active cookies and headers."""
        cookie_hdr = self.get_cookie_header()
        target_url = f"{self.portal_url}/SmartSearch/SmartSearchResults?_={int(time.time() * 1000)}"
        return (
            f"curl -s '{target_url}' \\\n"
            f"  -H 'User-Agent: {self.user_agent}' \\\n"
            f"  -H 'Accept: */*' \\\n"
            f"  -H 'X-Requested-With: XMLHttpRequest' \\\n"
            f"  -H 'Referer: {self.portal_url}/Home/WorkspaceMode?p=0' \\\n"
            f"  -H 'Cookie: {cookie_hdr}'"
        )
