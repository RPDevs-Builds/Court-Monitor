"""
Base interface for Court Docket adapters across Ohio counties.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from core.models import CaseSummary, DocketEntry, CaseParty


class BaseCourtAdapter(ABC):
    def __init__(self, county_id: str):
        self.county_id = county_id

    @abstractmethod
    def search_by_name(self, last_name: str, first_name: str = "") -> List[CaseSummary]:
        """Search criminal and civil case filings by party name."""
        pass

    @abstractmethod
    def search_by_case(self, case_number: str) -> Optional[CaseSummary]:
        """Lookup case summary by official case number."""
        pass

    @abstractmethod
    def get_docket(self, case_number: str) -> List[DocketEntry]:
        """Retrieve complete chronological docket entries for a case."""
        pass
