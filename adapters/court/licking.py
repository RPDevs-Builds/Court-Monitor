"""
Licking County Court of Common Pleas Adapter (Newark, Ohio)
Preconfigured Tyler Technologies re:SearchOH / Enterprise Justice adapter for Licking County.
"""

from pathlib import Path
from adapters.court.tyler_tech import TylerCourtAdapter, DEFAULT_SESSIONS_DIR


class LickingCourtAdapter(TylerCourtAdapter):
    """
    Licking County Common Pleas Court re:SearchOH Portal Adapter.
    Portal: https://researchoh.tylerhost.net/CourtRecordsSearch/ui/county/LickingCaseSearch
    """
    DEFAULT_PORTAL_URL = "https://researchoh.tylerhost.net/CourtRecordsSearch/ui/county/LickingCaseSearch"

    def __init__(
        self,
        county_id: str = "licking_oh",
        session_cache_dir: Path = DEFAULT_SESSIONS_DIR,
        user_agent: str = "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0"
    ):
        super().__init__(
            county_id=county_id,
            court_name="Licking County Court of Common Pleas",
            portal_url=self.DEFAULT_PORTAL_URL,
            session_cache_dir=session_cache_dir,
            user_agent=user_agent
        )
