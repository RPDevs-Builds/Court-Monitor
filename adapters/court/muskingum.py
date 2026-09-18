"""
Muskingum County Common Pleas Court Adapter (Zanesville, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Muskingum County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class MuskingumCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://clerkofcourts.muskingumcounty.org/eservices"

    def __init__(
        self,
        county_id: str = "muskingum_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Muskingum County Common Pleas Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
