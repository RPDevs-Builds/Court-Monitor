"""
Lorain County Common Pleas Court Adapter (Elyria, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Lorain County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class LorainCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://coc.loraincountyohio.gov/eservices"

    def __init__(
        self,
        county_id: str = "lorain_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Lorain County Common Pleas Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
