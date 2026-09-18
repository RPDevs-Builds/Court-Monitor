"""
Cuyahoga County Court of Common Pleas Adapter.
Wraps the headless browser session manager and ASP.NET WebForms automation into BaseCourtAdapter.
"""

from typing import Dict, List, Optional, Any
from adapters.court.base import BaseCourtAdapter
from core.models import CaseSummary, DocketEntry, CaseParty
from court_client import CuyahogaCourtClient


class CuyahogaCourtAdapter(BaseCourtAdapter):
    def __init__(self, county_id: str = "cuyahoga_oh", browser_executable: str = "/usr/bin/chromium"):
        super().__init__(county_id)
        self.client = CuyahogaCourtClient(browser_executable=browser_executable)

    def search_by_name(self, last_name: str, first_name: str = "") -> List[CaseSummary]:
        results = self.client.search_criminal_name(last_name, first_name)
        summaries = []
        for r in results:
            summaries.append(CaseSummary(
                case_number=r.get("case_number", ""),
                county=self.county_id,
                title=f"THE STATE OF OHIO vs. {r.get('defendant', '')}".strip(),
                case_type="Criminal",
                status=r.get("status"),
                source_url=r.get("link")
            ))
        return summaries

    def search_by_case(self, case_number: str) -> Optional[CaseSummary]:
        data = self.client.get_case_summary(case_number)
        if not data:
            return None

        parties = []
        for p in data.get("parties", []):
            parties.append(CaseParty(
                role=p.get("role", "Party"),
                name=p.get("name", ""),
                attorney=p.get("attorney")
            ))

        docket_entries = []
        for d in data.get("docket_entries", []):
            docket_entries.append(DocketEntry(
                sequence_id=d.get("sequence_id"),
                entry_date=d.get("date"),
                description=d.get("description", ""),
                docket_type=d.get("type"),
                amount=d.get("amount"),
                document_url=d.get("document_url")
            ))

        return CaseSummary(
            case_number=data.get("case_number", case_number),
            county=self.county_id,
            title=data.get("case_title", ""),
            case_type="Criminal",
            filing_date=data.get("filing_date"),
            judge=data.get("judge"),
            status=data.get("status"),
            parties=parties,
            docket_entries=docket_entries,
            docket_count=len(docket_entries),
            source_url=data.get("source_url")
        )

    def get_docket(self, case_number: str) -> List[DocketEntry]:
        raw_docket = self.client.get_docket(case_number)
        entries = []
        for d in raw_docket:
            entries.append(DocketEntry(
                sequence_id=d.get("sequence_id"),
                entry_date=d.get("date"),
                description=d.get("description", ""),
                docket_type=d.get("type"),
                amount=d.get("amount"),
                document_url=d.get("document_url")
            ))
        return entries

    def generate_curl_command(self, case_number: str) -> str:
        return self.client.generate_curl_command(case_number)
