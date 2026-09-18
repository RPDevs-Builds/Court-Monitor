"""
Lawrence County Municipal Court Adapter (Ironton, Ohio)
Preconfigured Henschen & Associates CaseLook adapter for Lawrence County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.caselook import HenschenCaseLookAdapter


class LawrenceCourtAdapter(HenschenCaseLookAdapter):
    DEFAULT_BASE_URL = "https://www.lawcomunicourt.com"
    DEFAULT_AGENCY_ID = "4410"

    def __init__(
        self,
        county_id: str = "lawrence_oh",
        base_url: Optional[str] = None,
        agency_id: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            base_url=base_url or self.DEFAULT_BASE_URL,
            agency_id=agency_id or self.DEFAULT_AGENCY_ID,
            court_name="Lawrence County Municipal Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
