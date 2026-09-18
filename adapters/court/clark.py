"""
Clark County Court of Common Pleas Adapter (Springfield, Ohio)
Preconfigured CourtView / Equivant Odyssey eServices adapter for Clark County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class ClarkCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://eservices.clarkcountyohiocourt.com/eservices"

    def __init__(
        self,
        county_id: str = "clark_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Clark County Court of Common Pleas",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
