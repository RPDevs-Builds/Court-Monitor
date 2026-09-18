"""
Court Docket Adapters for Ohio Justice & Custody Monitor.
"""

from typing import Optional
from adapters.court.base import BaseCourtAdapter
from adapters.court.cuyahoga import CuyahogaCourtAdapter
from adapters.court.tyler_tech import TylerCourtAdapter
from adapters.court.cleveland_muni import ClevelandMunicipalCourtAdapter
from adapters.court.franklin import FranklinCourtAdapter
from adapters.court.courtview import CourtViewAdapter
from adapters.court.lorain import LorainCourtAdapter
from adapters.court.delaware import DelawareCourtAdapter
from core.registry import get_registry


def get_court_adapter(county_id: str = "cuyahoga_oh") -> Optional[BaseCourtAdapter]:
    """Resolve and return court adapter for the specified county."""
    reg = get_registry()
    county = reg.get_county(county_id)
    if not county or not county.court_service or not county.court_service.enabled:
        return None

    adapter_type = county.court_service.adapter.lower()
    if adapter_type == "cuyahoga":
        return CuyahogaCourtAdapter(county_id=county.id)
    elif adapter_type in ("cleveland_muni", "cleveland"):
        return ClevelandMunicipalCourtAdapter(county_id=county.id)
    elif adapter_type in ("tyler_tech", "odyssey"):
        return TylerCourtAdapter(
            county_id=county.id,
            court_name=county.name,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("franklin", "franklin_court", "cio"):
        return FranklinCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("lorain", "lorain_court"):
        return LorainCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("delaware", "delaware_court"):
        return DelawareCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("courtview", "lake_courtview", "eservices"):
        return CourtViewAdapter(
            county_id=county.id,
            court_name=county.name,
            portal_url=county.court_service.base_url or "https://court.co.delaware.oh.us/eservices"
        )

    return None


__all__ = [
    "BaseCourtAdapter",
    "CuyahogaCourtAdapter",
    "TylerCourtAdapter",
    "ClevelandMunicipalCourtAdapter",
    "FranklinCourtAdapter",
    "CourtViewAdapter",
    "LorainCourtAdapter",
    "DelawareCourtAdapter",
    "get_court_adapter",
]

