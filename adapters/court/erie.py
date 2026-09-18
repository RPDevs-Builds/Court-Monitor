"""
Erie County Court of Common Pleas Adapter (Sandusky, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Erie County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class ErieCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://clerkofcourts.eriecounty.oh.gov/eservices"

    def __init__(
        self,
        county_id: str = "erie_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Erie County Court of Common Pleas",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
