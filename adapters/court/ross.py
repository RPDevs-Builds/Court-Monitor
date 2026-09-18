"""
Ross County Clerk of Courts & Common Pleas Court Adapter (Chillicothe, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Ross County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class RossCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://eaccess.co.ross.oh.us/eservices"

    def __init__(
        self,
        county_id: str = "ross_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Ross County Common Pleas Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
