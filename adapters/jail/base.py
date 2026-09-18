"""
Base interface for Jail & Inmate Custody adapters.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from core.models import InmateRecord, CustodyCheckResult


class BaseJailAdapter(ABC):
    def __init__(self, county_id: str):
        self.county_id = county_id

    @abstractmethod
    def fetch_roster(self) -> List[InmateRecord]:
        """Fetch all currently booked inmates."""
        pass

    def search_inmate(self, name_query: str) -> List[InmateRecord]:
        """Search current jail roster for matching name."""
        roster = self.fetch_roster()
        query = name_query.strip().upper()
        matches = []
        for inmate in roster:
            if query in inmate.full_name.upper():
                matches.append(inmate)
        return matches

    def check_custody(self, full_name: str) -> CustodyCheckResult:
        """Check if a specific person is currently in custody in this facility."""
        parts = [p.strip().upper() for p in full_name.replace(",", " ").split() if p.strip()]
        roster = self.fetch_roster()
        matches = []
        
        for inmate in roster:
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
