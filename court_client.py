#!/usr/bin/env python3
"""
Cuyahoga County Court of Common Pleas Client
Automates session initialization, terms of service handling, case search,
docket extraction, and live curl command generation.
"""

import json
import os
import subprocess
import time
from typing import Dict, List, Optional, Any

BASE_URL = "https://cpdocket.cp.cuyahogacounty.gov"

class CuyahogaCourtClient:
    def __init__(self, browser_executable: str = "/usr/bin/chromium"):
        self.browser_executable = browser_executable
        self.env = os.environ.copy()
        self.env["AGENT_BROWSER_EXECUTABLE_PATH"] = self.browser_executable

    def _run_browser(self, args: List[str], timeout: int = 25) -> str:
        cmd = ["agent-browser"] + args
        try:
            res = subprocess.run(cmd, env=self.env, capture_output=True, text=True, timeout=timeout)
            return res.stdout.strip()
        except subprocess.TimeoutExpired:
            return ""

    def ensure_session(self) -> bool:
        """
        Verify that the session is valid and TOS is accepted.
        If expired or blocked (Unavailable.aspx), clears cookies and starts fresh.
        """
        # Open root
        self._run_browser(["open", f"{BASE_URL}/"])
        self._run_browser(["wait", "1000"])
        
        current_url = self._run_browser(["eval", "window.location.href"])
        if "Unavailable.aspx" in current_url:
            print("[*] Session expired or invalid; resetting cookies...")
            self._run_browser(["cookies", "clear"])
            self._run_browser(["open", f"{BASE_URL}/"])
            self._run_browser(["wait", "1500"])
        
        check_tos = "document.querySelector('#SheetContentPlaceHolder_btnYes') ? 'tos' : 'ok'"
        status = self._run_browser(["eval", check_tos])
        if "tos" in status:
            print("[*] Accepting Terms of Service (btnYes)...")
            self._run_browser(["eval", "document.querySelector('#SheetContentPlaceHolder_btnYes').click()"])
            self._run_browser(["wait", "2000"])

        landing_url = self._run_browser(["eval", "window.location.href"])
        return "Search.aspx" in landing_url or "CR_Case" in landing_url or "CaseInfo" in landing_url

    def get_cookies(self) -> Dict[str, str]:
        """Retrieve all active cookies as a dictionary."""
        self.ensure_session()
        raw = self._run_browser(["cookies", "get"])
        cookies = {}
        for line in raw.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                cookies[k.strip()] = v.strip()
        return cookies

    def get_cookie_header(self) -> str:
        """Retrieve active cookies as a Cookie header string."""
        cookies = self.get_cookies()
        return "; ".join(f"{k}={v}" for k, v in cookies.items())

    def generate_curl_command(self, url: str) -> str:
        """Generate a working curl command with active cookies."""
        cookie_hdr = self.get_cookie_header()
        return (
            f"curl -s '{url}' \\\n"
            f"  -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0' \\\n"
            f"  -H 'Cookie: {cookie_hdr}'"
        )

    def search_criminal_by_name(self, last_name: str, first_name: str = "", dob_year: str = "", dob_month: str = "") -> List[Dict[str, Any]]:
        """
        Search criminal docket by defendant name.
        Returns list of matching defendants and their case history.
        """
        self.ensure_session()
        self._run_browser(["open", f"{BASE_URL}/Search.aspx"])
        self._run_browser(["wait", "1200"])

        # Switch to Criminal Name Search (rbCrName)
        self._run_browser(["eval", "document.querySelector('#SheetContentPlaceHolder_rbCrName')?.click()"])
        self._run_browser(["wait", "2000"])

        # Fill form fields
        js_fill = f"""
        (() => {{
            const last = document.querySelector('#SheetContentPlaceHolder_criminalNameSearch_txtLastName');
            if (last) {{ last.value = "{last_name}"; last.dispatchEvent(new Event('input', {{ bubbles: true }})); }}
            const first = document.querySelector('#SheetContentPlaceHolder_criminalNameSearch_txtFirstName');
            if (first) {{ first.value = "{first_name}"; first.dispatchEvent(new Event('input', {{ bubbles: true }})); }}
            const yr = document.querySelector('#SheetContentPlaceHolder_criminalNameSearch_ddlDOBYear');
            if (yr && "{dob_year}") {{ yr.value = "{dob_year}"; yr.dispatchEvent(new Event('change', {{ bubbles: true }})); }}
            const mo = document.querySelector('#SheetContentPlaceHolder_criminalNameSearch_ddlDOBMonth');
            if (mo && "{dob_month}") {{ mo.value = "{dob_month}"; mo.dispatchEvent(new Event('change', {{ bubbles: true }})); }}
            const btn = document.querySelector('#SheetContentPlaceHolder_criminalNameSearch_btnSubmitName');
            if (btn) btn.click();
        }})()
        """
        self._run_browser(["eval", js_fill])
        self._run_browser(["wait", "2500"])

        current_url = self._run_browser(["eval", "window.location.href"])

        # Check if we landed on NameSearchResults.aspx
        if "NameSearchResults.aspx" in current_url:
            js_extract_defendants = """
            (() => {
                const table = document.querySelector('.gridview');
                if (!table) return [];
                const rows = Array.from(table.querySelectorAll('tr')).slice(1);
                return rows.map((r, index) => {
                    const cells = Array.from(r.querySelectorAll('td')).map(c => c.innerText.trim());
                    const link = r.querySelector('a');
                    return {
                        row_index: index,
                        name: cells[0] || '',
                        dob: cells[1] || '',
                        race: cells[2] || '',
                        sex: cells[3] || '',
                        pending_cases: cells[4] || '',
                        defendant_id: cells[5] || '',
                        link_id: link ? link.id : null
                    };
                });
            })()
            """
            out = self._run_browser(["eval", js_extract_defendants])
            try:
                defendants = json.loads(out)
            except Exception:
                defendants = []
            return defendants
        
        # Or if landed directly on CaseInfoByName.aspx
        elif "CaseInfoByName.aspx" in current_url:
            return self._extract_cases_from_name_page()

        return []

    def get_defendant_cases(self, defendant_row_index: int = 0) -> List[Dict[str, Any]]:
        """
        From NameSearchResults.aspx, click a defendant to get their cases on CaseInfoByName.aspx.
        """
        js_click = f"""
        (() => {{
            const table = document.querySelector('.gridview');
            if (!table) return false;
            const rows = Array.from(table.querySelectorAll('tr')).slice(1);
            if (rows[{defendant_row_index}]) {{
                const link = rows[{defendant_row_index}].querySelector('a');
                if (link) {{ link.click(); return true; }}
            }}
            return false;
        }})()
        """
        self._run_browser(["eval", js_click])
        self._run_browser(["wait", "2500"])
        return self._extract_cases_from_name_page()

    def _extract_cases_from_name_page(self) -> List[Dict[str, Any]]:
        """Extract cases from CaseInfoByName.aspx table."""
        js_cases = """
        (() => {
            const table = document.querySelector('#SheetContentPlaceHolder_info_gvCaseResults');
            if (!table) return [];
            const defendantHeader = document.querySelector('#SheetContentPlaceHolder_info_lblResults')?.innerText || '';
            const rows = Array.from(table.querySelectorAll('tr')).slice(1);
            return rows.map((r, index) => {
                const cells = Array.from(r.querySelectorAll('td')).map(c => c.innerText.trim());
                const link = r.querySelector('a');
                return {
                    row_index: index,
                    defendant_header: defendantHeader,
                    case_number: cells[0] || '',
                    case_status: cells[1] || '',
                    filing_date: cells[2] || '',
                    jail_bail_status: cells[3] || '',
                    link_id: link ? link.id : null
                };
            });
        })()
        """
        out = self._run_browser(["eval", js_cases])
        try:
            return json.loads(out)
        except Exception:
            return []

    def search_criminal_by_case(self, year: str, number: str) -> Dict[str, Any]:
        """
        Search criminal docket directly by Year and Case Number.
        Returns Case Summary and Docket URL.
        """
        self.ensure_session()
        self._run_browser(["open", f"{BASE_URL}/Search.aspx"])
        self._run_browser(["wait", "1200"])

        # Switch to Criminal Case Search (rbCrCase)
        self._run_browser(["eval", "document.querySelector('#SheetContentPlaceHolder_rbCrCase')?.click()"])
        self._run_browser(["wait", "2000"])

        js_fill = f"""
        (() => {{
            const yr = document.querySelector('#SheetContentPlaceHolder_criminalCaseSearch_ddlYear');
            if (yr) {{ yr.value = '{year}'; yr.dispatchEvent(new Event('change', {{ bubbles: true }})); }}
            const num = document.querySelector('#SheetContentPlaceHolder_criminalCaseSearch_txtCaseNumber');
            if (num) {{ num.value = '{number}'; num.dispatchEvent(new Event('input', {{ bubbles: true }})); }}
            const btn = document.querySelector('#SheetContentPlaceHolder_criminalCaseSearch_btnSubmitCase');
            if (btn) btn.click();
        }})()
        """
        self._run_browser(["eval", js_fill])
        self._run_browser(["wait", "2500"])

        return self.extract_case_summary()

    def extract_case_summary(self) -> Dict[str, Any]:
        """Extract full case summary from current open summary page."""
        js_extract = """
        (() => {
            const caseNum = document.querySelector('#SheetContentPlaceHolder_caseHeader_lblCaseNumHeader')?.innerText || '';
            const title = document.querySelector('#SheetContentPlaceHolder_caseHeader_lblCaseTitleHeader')?.innerText || '';
            const status = document.querySelector('#SheetContentPlaceHolder_caseSummary_lblCaseStatus')?.innerText || '';
            const judge = document.querySelector('#SheetContentPlaceHolder_caseSummary_lblJudgeName')?.innerText || '';
            const nextEvent = document.querySelector('#SheetContentPlaceHolder_caseSummary_lblNextEvent')?.innerText || '';
            const arrestedDate = document.querySelector('#SheetContentPlaceHolder_caseSummary_lblArrested')?.innerText || '';
            const arrestingAgency = document.querySelector('#SheetContentPlaceHolder_caseSummary_lblArrestingAgency')?.innerText || '';
            const agencyReport = document.querySelector('#SheetContentPlaceHolder_caseSummary_lblArestingAgencyReport')?.innerText || '';
            
            // Defendant info
            const defNum = document.querySelector('#SheetContentPlaceHolder_caseSummary_lblNumber')?.innerText || '';
            const defName = document.querySelector('#SheetContentPlaceHolder_caseSummary_lblName')?.innerText || '';
            const defStatus = document.querySelector('#SheetContentPlaceHolder_caseSummary_defStatus_lblDefStatus')?.innerText || '';
            const dob = document.querySelector('#SheetContentPlaceHolder_caseSummary_lblDOB')?.innerText || '';
            const race = document.querySelector('#SheetContentPlaceHolder_caseSummary_lblRace')?.innerText || '';
            const sex = document.querySelector('#SheetContentPlaceHolder_caseSummary_lblSex')?.innerText || '';
            
            // Charges table
            const chargesTable = document.querySelector('#SheetContentPlaceHolder_caseCharges_gvCharges');
            const charges = [];
            if (chargesTable) {
                const rows = Array.from(chargesTable.querySelectorAll('tr')).slice(1);
                rows.forEach(r => {
                    const c = Array.from(r.querySelectorAll('td')).map(td => td.innerText.trim());
                    charges.append ? null : charges.push({
                        type: c[0] || '',
                        statute: c[1] || '',
                        description: c[2] || '',
                        disposition: c[3] || ''
                    });
                });
            }

            // Case Actions table
            const actionsTable = document.querySelector('#SheetContentPlaceHolder_caseActions_gvActions');
            const actions = [];
            if (actionsTable) {
                const rows = Array.from(actionsTable.querySelectorAll('tr')).slice(1);
                rows.forEach(r => {
                    const c = Array.from(r.querySelectorAll('td')).map(td => td.innerText.trim());
                    actions.push({
                        event_date: c[0] || '',
                        event_description: c[1] || ''
                    });
                });
            }

            return {
                url: window.location.href,
                case_number: caseNum,
                title: title,
                status: status,
                judge: judge,
                next_event: nextEvent,
                arrested_date: arrestedDate,
                arresting_agency: arrestingAgency,
                arresting_agency_report: agencyReport,
                defendant: {
                    number: defNum,
                    name: defName,
                    status: defStatus,
                    dob: dob,
                    race: race,
                    sex: sex
                },
                charges: charges,
                actions: actions
            };
        })()
        """
        out = self._run_browser(["eval", js_extract])
        try:
            return json.loads(out)
        except Exception:
            return {}

    def fetch_docket(self, docket_url: Optional[str] = None, year: Optional[str] = None, number: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch structured docket entries.
        Can load directly from docket_url or by searching year & number.
        """
        self.ensure_session()
        if docket_url:
            self._run_browser(["open", docket_url])
            self._run_browser(["wait", "2000"])
        elif year and number:
            self.search_criminal_by_case(year, number)
            # Click Docket link from summary
            self._run_browser(["eval", "document.querySelector('#SheetContentPlaceHolder_caseHeader_lbDocket')?.click()"])
            self._run_browser(["wait", "2000"])

        js_docket = """
        (() => {
            const table = document.querySelector('#SheetContentPlaceHolder_caseDocket_gvDocketInformation');
            if (!table) return null;
            const caseHeader = document.querySelector('#SheetContentPlaceHolder_caseHeader_lblCaseNumHeader')?.innerText || '';
            const caseTitle = document.querySelector('#SheetContentPlaceHolder_caseHeader_lblCaseTitleHeader')?.innerText || '';
            const rows = Array.from(table.querySelectorAll('tr')).slice(1);
            const entries = rows.map(r => {
                const cells = Array.from(r.querySelectorAll('td')).map(c => c.innerText.trim());
                const img = r.querySelector('a[title="View Docket Image"]');
                return {
                    proceeding_date: cells[0] || '',
                    filing_date: cells[1] || '',
                    party: cells[2] || '',
                    type: cells[3] || '',
                    description: cells[4] || '',
                    image_url: img ? img.href : null
                };
            });
            return {
                url: window.location.href,
                case_number: caseHeader,
                title: caseTitle,
                entries: entries
            };
        })()
        """
        out = self._run_browser(["eval", js_docket])
        try:
            return json.loads(out)
        except Exception:
            return {}
