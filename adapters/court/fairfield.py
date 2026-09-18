"""
Fairfield County Court of Common Pleas Adapter (Lancaster, Ohio)
Preconfigured Tyler Technologies Odyssey Portal adapter for Fairfield County.
"""

from pathlib import Path
from adapters.court.tyler_tech import TylerCourtAdapter, DEFAULT_SESSIONS_DIR


class FairfieldCourtAdapter(TylerCourtAdapter):
    """
    Fairfield County Common Pleas Court Odyssey Portal Adapter.
    Portal: https://portal-ohfairfield.tylertech.cloud/portal
    """
    DEFAULT_PORTAL_URL = "https://portal-ohfairfield.tylertech.cloud/portal"

    def __init__(
        self,
        county_id: str = "fairfield_oh",
        session_cache_dir: Path = DEFAULT_SESSIONS_DIR,
        user_agent: str = "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0"
    ):
        super().__init__(
            county_id=county_id,
            court_name="Fairfield County Court of Common Pleas",
            portal_url=self.DEFAULT_PORTAL_URL,
            session_cache_dir=session_cache_dir,
            user_agent=user_agent
        )
