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
from adapters.court.richland import RichlandCourtAdapter
from adapters.court.paulding import PauldingCourtAdapter
from adapters.court.pickaway import PickawayCourtAdapter
from adapters.court.perry import PerryCourtAdapter
from adapters.court.henry import HenryCourtAdapter
from adapters.court.coshocton import CoshoctonCourtAdapter
from adapters.court.guernsey import GuernseyCourtAdapter
from adapters.court.muskingum import MuskingumCourtAdapter
from adapters.court.meigs import MeigsCourtAdapter
from adapters.court.caselook import HenschenCaseLookAdapter
from adapters.court.fulton import FultonCourtAdapter
from adapters.court.lawrence import LawrenceCourtAdapter
from adapters.court.monroe import MonroeCourtAdapter
from adapters.court.noble import NobleCourtAdapter
from adapters.court.vinton import VintonCourtAdapter
from adapters.court.crawford import CrawfordCourtAdapter
from adapters.court.lucas import LucasCourtAdapter
from adapters.court.erie import ErieCourtAdapter
from adapters.court.athens import AthensCourtAdapter
from adapters.court.morgan import MorganCourtAdapter
from adapters.court.jackson import JacksonCourtAdapter
from adapters.court.carroll import CarrollCourtAdapter
from adapters.court.gallia import GalliaCourtAdapter
from adapters.court.harrison import HarrisonCourtAdapter
from adapters.court.marion import MarionCourtAdapter
from adapters.court.mercer import MercerCourtAdapter
from adapters.court.ottawa import OttawaCourtAdapter
from adapters.court.pike import PikeCourtAdapter
from adapters.court.washington import WashingtonCourtAdapter
from adapters.court.williams import WilliamsCourtAdapter
from adapters.court.licking import LickingCourtAdapter
from adapters.court.sandusky import SanduskyCourtAdapter
from adapters.court.fairfield import FairfieldCourtAdapter
from adapters.court.defiance import DefianceCourtAdapter
from adapters.court.clermont import ClermontCourtAdapter
from adapters.court.clinton import ClintonCourtAdapter
from adapters.court.brown import BrownCourtAdapter
from adapters.court.clark import ClarkCourtAdapter
from adapters.court.miami import MiamiCourtAdapter
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
    elif adapter_type in ("lucas", "lucas_court"):
        return LucasCourtAdapter(county_id=county.id)
    elif adapter_type in ("licking", "licking_court", "researchoh"):
        return LickingCourtAdapter(county_id=county.id)
    elif adapter_type in ("fairfield", "fairfield_court"):
        return FairfieldCourtAdapter(county_id=county.id)
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
    elif adapter_type in ("richland", "richland_court"):
        return RichlandCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("paulding", "paulding_court"):
        return PauldingCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("pickaway", "pickaway_court"):
        return PickawayCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("perry", "perry_court"):
        return PerryCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("henry", "henry_court"):
        return HenryCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("coshocton", "coshocton_court"):
        return CoshoctonCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("guernsey", "guernsey_court"):
        return GuernseyCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("muskingum", "muskingum_court"):
        return MuskingumCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("meigs", "meigs_court"):
        return MeigsCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("erie", "erie_court"):
        return ErieCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("athens", "athens_court"):
        return AthensCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("morgan", "morgan_court"):
        return MorganCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("jackson", "jackson_court"):
        return JacksonCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("defiance", "defiance_court"):
        return DefianceCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("clermont", "clermont_court"):
        return ClermontCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("clark", "clark_court"):
        return ClarkCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("miami", "miami_court"):
        return MiamiCourtAdapter(
            county_id=county.id,
            portal_url=county.court_service.base_url
        )
    elif adapter_type in ("fulton", "fulton_court", "fulton_caselook"):
        return FultonCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("lawrence", "lawrence_court", "lawrence_caselook"):
        return LawrenceCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("monroe", "monroe_court", "monroe_caselook"):
        return MonroeCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("noble", "noble_court", "noble_caselook"):
        return NobleCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("vinton", "vinton_court", "vinton_caselook"):
        return VintonCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("crawford", "crawford_court", "crawford_caselook"):
        return CrawfordCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("carroll", "carroll_court", "carroll_caselook"):
        return CarrollCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("gallia", "gallia_court", "gallia_caselook"):
        return GalliaCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("harrison", "harrison_court", "harrison_caselook"):
        return HarrisonCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("marion", "marion_court", "marion_caselook"):
        return MarionCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("mercer", "mercer_court", "mercer_caselook"):
        return MercerCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("ottawa", "ottawa_court", "ottawa_caselook"):
        return OttawaCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("pike", "pike_court", "pike_caselook"):
        return PikeCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("washington", "washington_court", "washington_caselook"):
        return WashingtonCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("williams", "williams_court", "williams_caselook"):
        return WilliamsCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("sandusky", "sandusky_court", "sandusky_caselook"):
        return SanduskyCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("clinton", "clinton_court", "clinton_caselook"):
        return ClintonCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
        )
    elif adapter_type in ("brown", "brown_court", "brown_caselook"):
        return BrownCourtAdapter(
            county_id=county.id,
            base_url=county.court_service.base_url
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
    "RichlandCourtAdapter",
    "PauldingCourtAdapter",
    "PickawayCourtAdapter",
    "PerryCourtAdapter",
    "HenryCourtAdapter",
    "CoshoctonCourtAdapter",
    "GuernseyCourtAdapter",
    "MuskingumCourtAdapter",
    "MeigsCourtAdapter",
    "ErieCourtAdapter",
    "AthensCourtAdapter",
    "MorganCourtAdapter",
    "JacksonCourtAdapter",
    "LucasCourtAdapter",
    "HenschenCaseLookAdapter",
    "FultonCourtAdapter",
    "LawrenceCourtAdapter",
    "MonroeCourtAdapter",
    "NobleCourtAdapter",
    "VintonCourtAdapter",
    "CrawfordCourtAdapter",
    "CarrollCourtAdapter",
    "GalliaCourtAdapter",
    "HarrisonCourtAdapter",
    "MarionCourtAdapter",
    "MercerCourtAdapter",
    "OttawaCourtAdapter",
    "PikeCourtAdapter",
    "WashingtonCourtAdapter",
    "WilliamsCourtAdapter",
    "LickingCourtAdapter",
    "FairfieldCourtAdapter",
    "SanduskyCourtAdapter",
    "DefianceCourtAdapter",
    "ClermontCourtAdapter",
    "ClintonCourtAdapter",
    "BrownCourtAdapter",
    "ClarkCourtAdapter",
    "MiamiCourtAdapter",
    "get_court_adapter",
]



