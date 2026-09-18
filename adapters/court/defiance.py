"""
Defiance County Common Pleas & Municipal Court Adapter (Defiance, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Defiance County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class DefianceCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://eservices.defianceohcountycourts.org/eservices"

    def __init__(
        self,
        county_id: str = "defiance_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Defiance County Courts",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
