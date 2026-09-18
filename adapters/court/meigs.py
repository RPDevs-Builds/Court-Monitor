"""
Meigs County Common Pleas Court Adapter (Pomeroy, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Meigs County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class MeigsCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://meigseaccess.com/eservices"

    def __init__(
        self,
        county_id: str = "meigs_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Meigs County Common Pleas Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
