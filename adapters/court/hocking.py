"""
Hocking County Municipal Court Adapter (Logan, Ohio)
Preconfigured Pioneer Technology Group Benchmark adapter for Hocking County.
"""

from typing import Optional
from pathlib import Path
from adapters.court.pioneer import PioneerCourtAdapter


class HockingCourtAdapter(PioneerCourtAdapter):
    DEFAULT_BASE_URL = "https://municipal.hocking.oh.gov"

    def __init__(
        self,
        county_id: str = "hocking_oh",
        base_url: Optional[str] = None,
        session_cache_dir: Optional[Path] = None
    ):
        super().__init__(
            county_id=county_id,
            base_url=base_url or self.DEFAULT_BASE_URL,
            court_name="Hocking County Municipal Court",
            session_cache_dir=session_cache_dir,
            verify_ssl=False
        )
