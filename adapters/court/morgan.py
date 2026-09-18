"""
Morgan County Court of Common Pleas Adapter (McConnelsville, Ohio)
Preconfigured CourtView / Tyler Odyssey eServices adapter for Morgan County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.courtview import CourtViewAdapter


class MorganCourtAdapter(CourtViewAdapter):
    DEFAULT_PORTAL_URL = "https://cpccourtview.morgancountyohio.gov/eservices"

    def __init__(
        self,
        county_id: str = "morgan_oh",
        portal_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            portal_url=portal_url or self.DEFAULT_PORTAL_URL,
            court_name="Morgan County Court of Common Pleas",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
