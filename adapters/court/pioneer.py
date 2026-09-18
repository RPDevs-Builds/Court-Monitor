"""
Pioneer Technology Group PublicAccess Court Records Adapter
Generic adapter for Pioneer Technology Group Benchmark / PublicAccess portals across Ohio courts.
Handles CSRF token extraction, server-side DataTables JSON queries, case/name searches,
and printable docket Register of Actions (ROA) parsing.
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


class PioneerCourtAdapter(BaseCourtAdapter):
    """
    Adapter for Pioneer Technology Group PublicAccess / Benchmark court management systems.
    Powers Wayne County Municipal & Common Pleas Courts and Benchmark portals.
    """

    DEFAULT_COURT_TYPES = "17,3,6,2,5,7,29,35,22,4"
    DEFAULT_PARTY_TYPES = "1,2,3,4,5"
    DEFAULT_DIVISIONS = "1,2,3,4,5,6,7,27,8,9,10,13,12,17,14,15,16,18,19,20,21,22,24,23"
    DEFAULT_CASE_TYPES = (
        "1317,1305,1392,1194,1330,1394,1337,1323,1148,1150,1309,1403,1417,1316,1184,"
        "1333,1331,1314,1311,1310,1313,1312,1302,1426,1318,1409,1300,1253,1413,1414,"
        "1285,1284,1423,1303,1283,1332,1425,1203,1152,1282,1192,1360,1320,1281,1151,"
        "1321,1322,1189,1280,1383,1275,1301,1274,1273,1193,19,1272,1307,1269,1268,1416,1267,1319"
    )

    def __init__(
        self,
        county_id: str,
        base_url: str,
        court_name: str = "Pioneer PublicAccess Court",
        session_cache_dir: Optional[Path] = None,
        verify_ssl: bool = False
    ):
        super().__init__(county_id)
        self.base_url = base_url.rstrip("/")
        self.court_name = court_name
        self.verify_ssl = verify_ssl

        if session_cache_dir:
            self.session_dir = Path(session_cache_dir)
        else:
            self.session_dir = Path(__file__).resolve().parent.parent.parent / "data" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.session_dir / f"pioneer_{self.county_id}.json"

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
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
                    "base_url": self.base_url,
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                    "cookies": cookies
                }, f, indent=2)
        except Exception:
            pass

    def _get_search_params(self) -> Optional[Dict[str, str]]:
        """Fetch fresh CSRF verification token and default filter IDs from Home.aspx/Search."""
        search_url = f"{self.base_url}/Home.aspx/Search"
        try:
            resp = self.session.get(search_url, verify=self.verify_ssl, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                inp_token = soup.find("input", {"name": "__RequestVerificationToken"})
                if inp_token and inp_token.get("value"):
                    self._save_session()
                    params = {"token": inp_token["value"]}
                    for field in ["courtTypes", "caseTypes", "partyTypes", "divisions"]:
                        inp = soup.find("input", {"name": field})
                        params[field] = inp.get("value", "") if inp else ""
                    return params
        except Exception:
            pass
        return None

    def search_by_name(self, last_name: str, first_name: str = "") -> List[CaseSummary]:
        """Search cases by party name."""
        params = self._get_search_params()
        if not params:
            return []

        query = f"{last_name}, {first_name}".strip(", ") if first_name else last_name

        init_payload = {
            "__RequestVerificationToken": params["token"],
            "type": "Name",
            "search": query,
            "courtTypes": params.get("courtTypes") or self.DEFAULT_COURT_TYPES,
            "caseTypes": params.get("caseTypes") or self.DEFAULT_CASE_TYPES,
            "partyTypes": params.get("partyTypes") or self.DEFAULT_PARTY_TYPES,
            "divisions": params.get("divisions") or self.DEFAULT_DIVISIONS
        }

        try:
            init_url = f"{self.base_url}/CourtCase.aspx/CaseSearch"
            self.session.post(init_url, data=init_payload, verify=self.verify_ssl, timeout=12)

            dt_url = f"{self.base_url}/Search.aspx/CaseSearch"
            dt_payload = {"draw": 1, "start": 0, "length": 50}
            dt_resp = self.session.post(dt_url, data=dt_payload, verify=self.verify_ssl, timeout=12)
            if dt_resp.status_code == 200:
                self._save_session()
                return self._parse_datatables_json(dt_resp.json())
        except Exception:
            pass
        return []

    def search_by_case(self, case_number: str) -> Optional[CaseSummary]:
        """Search case summary by official case number."""
        params = self._get_search_params()
        if not params:
            return None

        init_payload = {
            "__RequestVerificationToken": params["token"],
            "type": "CaseNumber",
            "search": case_number.strip(),
            "courtTypes": params.get("courtTypes") or self.DEFAULT_COURT_TYPES,
            "caseTypes": params.get("caseTypes") or self.DEFAULT_CASE_TYPES,
            "partyTypes": params.get("partyTypes") or self.DEFAULT_PARTY_TYPES,
            "divisions": params.get("divisions") or self.DEFAULT_DIVISIONS
        }

        try:
            init_url = f"{self.base_url}/CourtCase.aspx/CaseSearch"
            self.session.post(init_url, data=init_payload, verify=self.verify_ssl, timeout=12)

            dt_url = f"{self.base_url}/Search.aspx/CaseSearch"
            dt_payload = {"draw": 1, "start": 0, "length": 10}
            dt_resp = self.session.post(dt_url, data=dt_payload, verify=self.verify_ssl, timeout=12)
            if dt_resp.status_code == 200:
                self._save_session()
                results = self._parse_datatables_json(dt_resp.json())
                if results:
                    return results[0]
        except Exception:
            pass
        return None

    def _parse_datatables_json(self, json_data: Dict[str, Any]) -> List[CaseSummary]:
        """Convert Pioneer DataTables JSON array into CaseSummary models."""
        cases = []
        rows = json_data.get("data", [])
        for item in rows:
            if not isinstance(item, dict):
                continue

            raw_name = item.get("1", "")
            name_soup = BeautifulSoup(raw_name, "html.parser")
            party_name = name_soup.get_text(strip=True).replace("(Alias)", "").strip()

            party_type = item.get("2", "").strip()

            raw_case = item.get("3", "")
            case_soup = BeautifulSoup(raw_case, "html.parser")
            case_no = case_soup.get_text(strip=True)

            a_tag = case_soup.find("a")
            detail_path = a_tag["href"] if a_tag and a_tag.get("href") else None

            status = item.get("4", "").strip() or "UNKNOWN"

            if not case_no:
                continue

            title = f"{party_name} ({party_type})" if party_type else (party_name or case_no)

            cases.append(CaseSummary(
                case_number=case_no,
                county=self.county_id,
                title=title,
                case_type="Criminal/Traffic" if any(k in case_no.upper() for k in ["CR", "TR"]) else "Civil",
                filing_date=None,
                status=status,
                parties=[CaseParty(role=party_type or "Party", name=party_name)] if party_name else [],
                docket_entries=[],
                source_url=f"{self.base_url.replace('/publicaccess', '')}{detail_path}" if detail_path else None
            ))
        return cases

    def get_docket(self, case_number: str) -> List[DocketEntry]:
        """Retrieve complete chronological docket entries for a case."""
        case = self.search_by_case(case_number)
        if not case or not case.source_url:
            return []

        detail_url = case.source_url
        print_url = detail_url.replace("/Details/", "/DetailsPrint/")

        try:
            resp = self.session.get(print_url, verify=self.verify_ssl, timeout=12)
            if resp.status_code == 200:
                return self._parse_docket_print_html(resp.text)
        except Exception:
            pass
        return []

    def _parse_docket_print_html(self, html_text: str) -> List[DocketEntry]:
        """Parse printable HTML tables into DocketEntry models."""
        entries = []
        soup = BeautifulSoup(html_text, "html.parser")
        tables = soup.find_all("table")

        for tbl in tables:
            rows = tbl.find_all("tr")
            if len(rows) < 2:
                continue

            headers = [th.get_text(strip=True).upper() for th in rows[0].find_all(["th", "td"])]
            if "EVENT" in headers and "DATE" in headers:
                date_idx = headers.index("DATE")
                event_idx = headers.index("EVENT")
                judge_idx = headers.index("JUDGE") if "JUDGE" in headers else -1
                result_idx = headers.index("RESULT") if "RESULT" in headers else -1

                for tr in rows[1:]:
                    tds = tr.find_all(["td", "th"])
                    if len(tds) <= max(date_idx, event_idx):
                        continue
                    d_date = tds[date_idx].get_text(strip=True)
                    d_desc = tds[event_idx].get_text(strip=True)
                    judge = tds[judge_idx].get_text(strip=True) if judge_idx >= 0 and judge_idx < len(tds) else ""
                    result = tds[result_idx].get_text(strip=True) if result_idx >= 0 and result_idx < len(tds) else ""

                    if not d_desc:
                        continue

                    full_desc = d_desc
                    if result:
                        full_desc += f" [Result: {result}]"
                    if judge:
                        full_desc += f" [Judge: {judge}]"

                    entries.append(DocketEntry(
                        sequence_id=len(entries) + 1,
                        entry_date=d_date,
                        description=full_desc,
                        amount=None
                    ))
        return entries

    def generate_curl_command(self, query: str = "SMITH", search_type: str = "name") -> str:
        """Generate copy-pasteable curl command for Pioneer PublicAccess."""
        cookie_header = "; ".join([f"{k}={v}" for k, v in self.session.cookies.items()]) or "ASP.NET_SessionId=session_placeholder"
        return (
            f"curl -s -k -X POST '{self.base_url}/Search.aspx/CaseSearch' \\\n"
            f"  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)' \\\n"
            f"  -H 'Cookie: {cookie_header}' \\\n"
            f"  -H 'Referer: {self.base_url}/Home.aspx/Search' \\\n"
            f"  --data 'draw=1&start=0&length=50'"
        )


class WayneCourtAdapter(PioneerCourtAdapter):
    """
    Wayne County Municipal & Common Pleas Court Adapter (Wooster, Ohio).
    Preconfigured Pioneer Technology Group PublicAccess adapter.
    """
    DEFAULT_BASE_URL = "https://courtsweb.waynecourts.org/publicaccess"

    def __init__(
        self,
        county_id: str = "wayne_oh",
        base_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            base_url=base_url or self.DEFAULT_BASE_URL,
            court_name="Wayne County Municipal & Common Pleas Courts",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )


class ColumbianaCourtAdapter(PioneerCourtAdapter):
    """
    Columbiana County Court of Common Pleas Adapter (Lisbon, Ohio).
    Preconfigured Pioneer Technology Group Benchmark adapter.
    """
    DEFAULT_BASE_URL = "https://courts.ccclerk.org/benchmarkweb"

    def __init__(
        self,
        county_id: str = "columbiana_oh",
        base_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            base_url=base_url or self.DEFAULT_BASE_URL,
            court_name="Columbiana County Court of Common Pleas",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )

