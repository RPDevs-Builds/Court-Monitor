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
from adapters.court.butler import ButlerCourtAdapter
from adapters.court.portage import PortageCourtAdapter
from adapters.court.mahoning import MahoningCourtAdapter
from adapters.court.montgomery import MontgomeryCourtAdapter
from adapters.court.medina import MedinaCourtAdapter
from adapters.court.wood import WoodCourtAdapter
from adapters.court.union import UnionCourtAdapter
from adapters.court.ross import RossCourtAdapter
from adapters.court.allen import AllenCourtAdapter
from adapters.court.knox import KnoxCourtAdapter
from adapters.court.belmont import BelmontCourtAdapter
from adapters.court.greene import GreeneCourtAdapter
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
    elif adapter_type in ("medina", "medina_court"):
        return MedinaCourtAdapter(county_id=county.id)
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
    elif adapter_type in ("montgomery", "montgomery_court", "prov3"):
        return MontgomeryCourtAdapter(county_id=county.id)
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
    elif adapter_type in ("butler", "butler_court"):
        return ButlerCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("portage", "portage_court"):
        return PortageCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("mahoning", "mahoning_court"):
        return MahoningCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("wood", "wood_court"):
        return WoodCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("union", "union_court"):
        return UnionCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("ross", "ross_court"):
        return RossCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("allen", "allen_court"):
        return AllenCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("knox", "knox_court"):
        return KnoxCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("belmont", "belmont_court"):
        return BelmontCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("greene", "greene_court"):
        return GreeneCourtAdapter(
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
    "ButlerCourtAdapter",
    "PortageCourtAdapter",
    "MahoningCourtAdapter",
    "MontgomeryCourtAdapter",
    "MedinaCourtAdapter",
    "WoodCourtAdapter",
    "UnionCourtAdapter",
    "RossCourtAdapter",
    "AllenCourtAdapter",
    "KnoxCourtAdapter",
    "BelmontCourtAdapter",
    "GreeneCourtAdapter",
    "get_court_adapter",
]


