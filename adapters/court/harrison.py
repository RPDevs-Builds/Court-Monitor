"""
Harrison County Common Pleas Court Adapter (Cadiz, Ohio)
Preconfigured Henschen & Associates CaseLook adapter for Harrison County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.caselook import HenschenCaseLookAdapter


class HarrisonCourtAdapter(HenschenCaseLookAdapter):
    DEFAULT_BASE_URL = "http://137.83.109.6:8889"
    DEFAULT_AGENCY_ID = "3404"

    def __init__(
        self,
        county_id: str = "harrison_oh",
        base_url: Optional[str] = None,
        agency_id: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            base_url=base_url or self.DEFAULT_BASE_URL,
            agency_id=agency_id or self.DEFAULT_AGENCY_ID,
            court_name="Harrison County Common Pleas Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
