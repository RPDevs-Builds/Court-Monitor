"""
Brown County Common Pleas Court Adapter (Georgetown, Ohio)
Preconfigured Henschen & Associates CaseLook adapter for Brown County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.caselook import HenschenCaseLookAdapter


class BrownCourtAdapter(HenschenCaseLookAdapter):
    DEFAULT_BASE_URL = "http://www.browncountyclerkofcourts.org"
    DEFAULT_AGENCY_ID = "0801"

    def __init__(
        self,
        county_id: str = "brown_oh",
        base_url: Optional[str] = None,
        agency_id: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            base_url=base_url or self.DEFAULT_BASE_URL,
            agency_id=agency_id or self.DEFAULT_AGENCY_ID,
            court_name="Brown County Court of Common Pleas",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
