"""
Cleveland Municipal Court Adapter.
Extends the generalized Tyler Technologies Odyssey Portal (CMCPORTAL) adapter
specifically for Cleveland Municipal Court (General, Criminal, Traffic, Civil & Housing Divisions).
"""

from pathlib import Path
from adapters.court.tyler_tech import TylerCourtAdapter, DEFAULT_SESSIONS_DIR


class ClevelandMunicipalCourtAdapter(TylerCourtAdapter):
    """
    Cleveland Municipal Court Odyssey Portal Adapter.
    Base public access: https://clevelandmunicipalcourt.org/public-access
    Portal: https://portal-ohcleveland.tylertech.cloud/CMCPORTAL
    """
    def __init__(
        self,
        county_id: str = "cleveland_muni_oh",
        session_cache_dir: Path = DEFAULT_SESSIONS_DIR,
        user_agent: str = "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0"
    ):
        super().__init__(
            county_id=county_id,
            court_name="Cleveland Municipal Court",
            portal_url="https://portal-ohcleveland.tylertech.cloud/CMCPORTAL",
            session_cache_dir=session_cache_dir,
            user_agent=user_agent
        )
