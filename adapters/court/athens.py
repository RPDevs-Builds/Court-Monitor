"""
Athens County Court of Common Pleas Adapter (Athens, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Athens County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class AthensCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://eservices.athenscommonpleas.com/eservices"

    def __init__(
        self,
        county_id: str = "athens_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Athens County Court of Common Pleas",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
