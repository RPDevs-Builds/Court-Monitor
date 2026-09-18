"""
Williams County Municipal Court Adapter (Bryan, Ohio)
Preconfigured Henschen & Associates CaseLook adapter for Williams County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.caselook import HenschenCaseLookAdapter


class WilliamsCourtAdapter(HenschenCaseLookAdapter):
    DEFAULT_BASE_URL = "https://bryanmunicipalcourt.com"
    DEFAULT_AGENCY_ID = "8620"

    def __init__(
        self,
        county_id: str = "williams_oh",
        base_url: Optional[str] = None,
        agency_id: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            base_url=base_url or self.DEFAULT_BASE_URL,
            agency_id=agency_id or self.DEFAULT_AGENCY_ID,
            court_name="Bryan Municipal Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
