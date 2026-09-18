"""
Medina County Court of Common Pleas Adapter.
Extends the generalized Tyler Technologies Odyssey Portal adapter
specifically for Medina County Common Pleas Court (General, Criminal & Civil Divisions).
"""

from pathlib import Path
from adapters.court.tyler_tech import TylerCourtAdapter, DEFAULT_SESSIONS_DIR


class MedinaCourtAdapter(TylerCourtAdapter):
    """
    Medina County Common Pleas Court Odyssey Portal Adapter.
    Portal: https://portal-ohmedina.tylertech.cloud/Portal
    """
    def __init__(
        self,
        county_id: str = "medina_oh",
        session_cache_dir: Path = DEFAULT_SESSIONS_DIR,
        user_agent: str = "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0"
    ):
        super().__init__(
            county_id=county_id,
            court_name="Medina County Common Pleas Court",
            portal_url="https://portal-ohmedina.tylertech.cloud/Portal",
            session_cache_dir=session_cache_dir,
            user_agent=user_agent
        )
