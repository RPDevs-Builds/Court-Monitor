"""
Guernsey County Common Pleas Court Adapter (Cambridge, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Guernsey County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class GuernseyCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://clerkofcourts.guernseycounty.org/eservices"

    def __init__(
        self,
        county_id: str = "guernsey_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Guernsey County Common Pleas Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
