"""
Henry County Common Pleas Court Adapter (Napoleon, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Henry County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class HenryCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://eservices.henrycountyohio.gov/eservices"

    def __init__(
        self,
        county_id: str = "henry_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Henry County Common Pleas Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
