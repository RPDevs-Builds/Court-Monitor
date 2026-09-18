"""
Jail & Custody Adapters for Ohio Justice & Custody Monitor.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from adapters.jail.base import BaseJailAdapter
from adapters.jail.ocv_s3 import OCVS3JailAdapter
from adapters.jail.ocv_rtjb import OCVRTJBJailAdapter
from adapters.jail.summit import SummitJailAdapter
from adapters.jail.odrc import ODRCJailAdapter
from adapters.jail.miami_valley import MiamiValleyJailAdapter
from core.registry import get_registry
from core.models import CustodyCheckResult, InmateRecord


def get_jail_adapter(county_id: str) -> Optional[BaseJailAdapter]:
    """Resolve and instantiate the jail adapter for a given county."""
    reg = get_registry()
    county = reg.get_county(county_id)
    if not county or not county.jail_service or not county.jail_service.enabled:
        return None

    service = county.jail_service
    adapter_name = service.adapter.lower()

    if adapter_name == "ocv_s3":
        return OCVS3JailAdapter(
            county_id=county.id,
            primary_url=service.primary_url or "",
            fallback_url=service.fallback_url
        )
    elif adapter_name == "ocv_rtjb":
        return OCVRTJBJailAdapter(
            county_id=county.id,
            app_id=service.app_id or county.id,
            primary_url=service.primary_url
        )
    elif adapter_name == "summit":
        return SummitJailAdapter(county_id=county.id)
    elif adapter_name == "odrc":
        return ODRCJailAdapter(county_id=county.id)
    elif adapter_name in ("miami_valley", "miami_valley_jail"):
        return MiamiValleyJailAdapter(
            county_id=county.id,
            subdomain=service.feed_type or None
        )
    
    return None


def check_custody_statewide(
    full_name: str,
    target_counties: Optional[List[str]] = None
) -> CustodyCheckResult:
    """
    Search for an individual across multiple Ohio county jails and the Ohio State Prison system.
    Runs queries in parallel.
    """
    reg = get_registry()
    available_counties = reg.list_jail_counties()

    if target_counties:
        queried = [cid for cid in target_counties if cid in available_counties]
    else:
        # Default priority set: Cuyahoga, Summit, and Statewide ODRC
        priority_set = ["cuyahoga_oh", "summit_oh", "odrc_statewide"]
        queried = [cid for cid in priority_set if cid in available_counties]

    all_matches: List[InmateRecord] = []
    queried_list: List[str] = []

    def query_county(cid: str):
        adapter = get_jail_adapter(cid)
        if not adapter:
            return cid, []
        try:
            res = adapter.check_custody(full_name)
            return cid, res.matches
        except Exception as e:
            print(f"[-] Error querying custody for {cid}: {e}")
            return cid, []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(query_county, cid): cid for cid in queried}
        for future in as_completed(futures):
            cid, matches = future.result()
            queried_list.append(cid)
            if matches:
                all_matches.extend(matches)

    return CustodyCheckResult(
        queried_name=full_name,
        is_in_custody=len(all_matches) > 0,
        total_matches=len(all_matches),
        matches=all_matches,
        queried_counties=queried_list
    )


__all__ = [
    "BaseJailAdapter",
    "OCVS3JailAdapter",
    "OCVRTJBJailAdapter",
    "SummitJailAdapter",
    "ODRCJailAdapter",
    "MiamiValleyJailAdapter",
    "get_jail_adapter",
    "check_custody_statewide",
]
