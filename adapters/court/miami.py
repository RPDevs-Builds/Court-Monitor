"""
Miami County Municipal & Common Pleas Court Adapter (Troy, Ohio)
Preconfigured CourtView / Equivant eServices adapter for Miami County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class MiamiCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://courts.miamicountyohio.gov/eservices"

    def __init__(
        self,
        county_id: str = "miami_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Miami County Courts",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
