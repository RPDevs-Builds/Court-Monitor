"""
Knox County Clerk of Courts & Common Pleas Court Adapter (Mount Vernon, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Knox County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class KnoxCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://www.clerkofcourts.co.knox.oh.us/eservices"

    def __init__(
        self,
        county_id: str = "knox_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Knox County Common Pleas Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
