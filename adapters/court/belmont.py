"""
Belmont County Clerk of Courts & Common Pleas Court Adapter (St. Clairsville, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Belmont County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class BelmontCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://eservices.belmontcountycourts.com/eservices"

    def __init__(
        self,
        county_id: str = "belmont_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Belmont County Common Pleas Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
