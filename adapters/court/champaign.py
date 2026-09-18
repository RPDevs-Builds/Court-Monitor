"""
Champaign County Court of Common Pleas Adapter (Urbana, Ohio)
Preconfigured Tyler CourtView eServices adapter for Champaign County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class ChampaignCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://eservices.champaignclerk.com/eservices"

    def __init__(
        self,
        county_id: str = "champaign_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            court_name="Champaign County Court of Common Pleas",
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
