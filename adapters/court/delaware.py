"""
Delaware County Common Pleas Court Adapter (Delaware, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Delaware County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class DelawareCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://court.co.delaware.oh.us/eservices"

    def __init__(
        self,
        county_id: str = "delaware_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Delaware County Common Pleas Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
