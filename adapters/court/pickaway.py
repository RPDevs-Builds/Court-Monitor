"""
Pickaway County Courts & Common Pleas Court Adapter (Circleville, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Pickaway County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class PickawayCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://eservices.pickawaycountycourts.com/eservices"

    def __init__(
        self,
        county_id: str = "pickaway_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Pickaway County Courts",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
