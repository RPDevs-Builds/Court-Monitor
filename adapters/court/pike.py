"""
Pike County Court Adapter (Waverly, Ohio)
Preconfigured Henschen & Associates CaseLook adapter for Pike County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.caselook import HenschenCaseLookAdapter


class PikeCourtAdapter(HenschenCaseLookAdapter):
    DEFAULT_BASE_URL = "https://pikecountycourt.org"
    DEFAULT_AGENCY_ID = "6610"

    def __init__(
        self,
        county_id: str = "pike_oh",
        base_url: Optional[str] = None,
        agency_id: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            base_url=base_url or self.DEFAULT_BASE_URL,
            agency_id=agency_id or self.DEFAULT_AGENCY_ID,
            court_name="Pike County Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
