"""
Agency Registry for Ohio Justice & Custody Monitor.
Manages configured Ohio county integrations, endpoint resolutions, and adapter instantiation.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from core.models import CountyConfig


REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data" / "agency_registry.json"


class AgencyRegistry:
    def __init__(self, registry_file: Optional[Path] = None):
        self.registry_file = registry_file or REGISTRY_PATH
        self.counties: Dict[str, CountyConfig] = {}
        self.load()

    def load(self) -> None:
        """Load registry from JSON file."""
        if not self.registry_file.exists():
            raise FileNotFoundError(f"Registry file not found at {self.registry_file}")
        with open(self.registry_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
        
        counties_data = raw.get("counties", {})
        self.counties = {
            cid: CountyConfig(**cdata) for cid, cdata in counties_data.items()
        }

    def list_counties(self, active_only: bool = True) -> List[CountyConfig]:
        """Return list of registered counties."""
        if active_only:
            return [c for c in self.counties.values() if c.active]
        return list(self.counties.values())

    def get_county(self, county_id: str) -> Optional[CountyConfig]:
        """Retrieve county by ID (with fuzzy fallback)."""
        cid = county_id.lower().strip()
        if cid in self.counties:
            return self.counties[cid]
        # Match without _oh suffix if provided
        if not cid.endswith("_oh"):
            cid_with_oh = f"{cid}_oh"
            if cid_with_oh in self.counties:
                return self.counties[cid_with_oh]
        # Match by county name
        for c in self.counties.values():
            if c.county.lower() == cid or c.name.lower() == cid:
                return c
        return None

    def list_jail_counties(self) -> List[str]:
        """Return IDs of all counties with active jail services."""
        return [
            cid for cid, c in self.counties.items()
            if c.active and c.jail_service and c.jail_service.enabled
        ]

    def list_court_counties(self) -> List[str]:
        """Return IDs of all counties with active court services."""
        return [
            cid for cid, c in self.counties.items()
            if c.active and c.court_service and c.court_service.enabled
        ]


_GLOBAL_REGISTRY: Optional[AgencyRegistry] = None


def get_registry() -> AgencyRegistry:
    """Singleton getter for agency registry."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = AgencyRegistry()
    return _GLOBAL_REGISTRY
