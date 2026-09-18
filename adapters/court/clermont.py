"""
Clermont County Common Pleas Court Adapter (Batavia, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Clermont County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class ClermontCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://eservices.clermontclerk.org/commonpleas"

    def __init__(
        self,
        county_id: str = "clermont_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Clermont County Court of Common Pleas",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
