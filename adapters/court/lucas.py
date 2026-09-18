"""
Lucas County Court of Common Pleas Adapter.
Extends the generalized Tyler Technologies Odyssey Portal adapter
specifically for Lucas County Common Pleas Court (Toledo, OH).
"""

from pathlib import Path
from adapters.court.tyler_tech import TylerCourtAdapter, DEFAULT_SESSIONS_DIR


class LucasCourtAdapter(TylerCourtAdapter):
    """
    Lucas County Common Pleas Court Odyssey Portal Adapter.
    Portal: https://portal-ohlucas.tylertech.cloud/portal
    """
    def __init__(
        self,
        county_id: str = "lucas_oh",
        session_cache_dir: Path = DEFAULT_SESSIONS_DIR,
        user_agent: str = "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0"
    ):
        super().__init__(
            county_id=county_id,
            court_name="Lucas County Court of Common Pleas",
            portal_url="https://portal-ohlucas.tylertech.cloud/portal",
            session_cache_dir=session_cache_dir,
            user_agent=user_agent
        )
