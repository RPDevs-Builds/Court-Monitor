#!/usr/bin/env python3
"""
Ohio Multi-County Court Docket Monitoring Engine
Maintains multi-county watchlist, caches snapshots, detects new activity, and formats diffs.
"""

import datetime
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from court_client import CuyahogaCourtClient
from adapters.court import get_court_adapter
from core.db import record_case_docket

DATA_DIR = Path(__file__).resolve().parent / "data"
CASES_DIR = DATA_DIR / "cases"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"


class DocketMonitorEngine:
    def __init__(self, client: Optional[CuyahogaCourtClient] = None):
        self.client = client or CuyahogaCourtClient()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CASES_DIR.mkdir(parents=True, exist_ok=True)
        if not WATCHLIST_FILE.exists():
            # Seed default case
            initial_watchlist = [
                {
                    "case_number": "CR-26-711470-A",
                    "county": "cuyahoga_oh",
                    "year": "2026",
                    "number": "711470",
                    "docket_url": "https://cpdocket.cp.cuyahogacounty.gov/CR_CaseInformation_Docket.aspx?q=hRRTYX-BnjfUgnoAk-HSrQ00n6DjqAxFUzIxKeQ1ac41",
                    "label": "THE STATE OF OHIO vs. CAITLIN O'BOYLE",
                    "added_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
            ]
            with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
                json.dump(initial_watchlist, f, indent=2)

    def get_watchlist(self) -> List[Dict[str, Any]]:
        if WATCHLIST_FILE.exists():
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
                # Ensure each item has county
                for it in items:
                    if "county" not in it:
                        it["county"] = "cuyahoga_oh"
                return items
        return []

    def save_watchlist(self, watchlist: List[Dict[str, Any]]) -> None:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, indent=2)

    def add_to_watchlist(
        self,
        case_number: str,
        county: str = "cuyahoga_oh",
        year: str = "",
        number: str = "",
        docket_url: str = "",
        label: str = ""
    ) -> Dict[str, Any]:
        case_number = case_number.strip().upper()
        county = county.strip().lower()
        if not county.endswith("_oh") and county != "odrc_statewide":
            county = f"{county}_oh"

        watchlist = self.get_watchlist()
        for item in watchlist:
            if item.get("case_number") == case_number and item.get("county", "cuyahoga_oh") == county:
                item["year"] = year or item.get("year", "")
                item["number"] = number or item.get("number", "")
                item["docket_url"] = docket_url or item.get("docket_url", "")
                item["label"] = label or item.get("label", "")
                self.save_watchlist(watchlist)
                return {"status": "updated", "item": item}

        new_item = {
            "case_number": case_number,
            "county": county,
            "year": year,
            "number": number,
            "docket_url": docket_url,
            "label": label,
            "added_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        watchlist.append(new_item)
        self.save_watchlist(watchlist)
        return {"status": "added", "item": new_item}

    def remove_from_watchlist(self, case_number: str, county: Optional[str] = None) -> bool:
        case_number = case_number.strip().upper()
        watchlist = self.get_watchlist()
        if county:
            target_county = county.strip().lower()
            if not target_county.endswith("_oh"):
                target_county = f"{target_county}_oh"
            filtered = [
                w for w in watchlist
                if not (w.get("case_number") == case_number and w.get("county") == target_county)
            ]
        else:
            filtered = [w for w in watchlist if w.get("case_number") != case_number]

        if len(filtered) != len(watchlist):
            self.save_watchlist(filtered)
            return True
        return False

    def load_case_cache(self, case_number: str, county: str = "cuyahoga_oh") -> Optional[Dict[str, Any]]:
        safe_num = case_number.replace("/", "_").replace("\\", "_")
        cache_path = CASES_DIR / f"{county}_{safe_num}.json"
        # Fallback to legacy path without county prefix
        if not cache_path.exists():
            legacy_path = CASES_DIR / f"{safe_num}.json"
            if legacy_path.exists():
                with open(legacy_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_case_cache(self, case_number: str, county: str, data: Dict[str, Any]) -> None:
        safe_num = case_number.replace("/", "_").replace("\\", "_")
        cache_path = CASES_DIR / f"{county}_{safe_num}.json"
        data["county"] = county
        data["last_checked"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def check_case(self, case_item: Dict[str, Any]) -> Dict[str, Any]:
        case_number = case_item.get("case_number", "")
        county = case_item.get("county", "cuyahoga_oh")
        docket_url = case_item.get("docket_url", "")
        year = case_item.get("year", "")
        number = case_item.get("number", "")

        # Use county court adapter if not Cuyahoga or fallback to Cuyahoga client
        if county == "cuyahoga_oh":
            if docket_url:
                latest = self.client.fetch_docket(docket_url=docket_url)
            elif year and number:
                latest = self.client.fetch_docket(year=year, number=number)
            else:
                parts = case_number.split("-")
                if len(parts) >= 3 and parts[0] == "CR":
                    parsed_year = f"20{parts[1]}" if len(parts[1]) == 2 else parts[1]
                    parsed_num = parts[2]
                    latest = self.client.fetch_docket(year=parsed_year, number=parsed_num)
                else:
                    return {"case_number": case_number, "county": county, "error": "Insufficient parameters to locate docket"}
        else:
            adapter = get_court_adapter(county)
            if not adapter:
                return {"case_number": case_number, "county": county, "error": f"No active court adapter for {county}"}
            summary = adapter.search_by_case(case_number)
            if not summary:
                return {"case_number": case_number, "county": county, "error": "Case not found"}
            latest = summary.model_dump()
            latest["entries"] = latest.get("docket_entries", [])

        if not latest or not latest.get("entries"):
            return {"case_number": case_number, "county": county, "error": "Failed to fetch docket from court portal"}

        current_entries = latest.get("entries", [])
        cached = self.load_case_cache(case_number, county=county)

        new_entries = []
        if cached:
            cached_entries = cached.get("entries", [])
            cached_sigs = set(
                f"{e.get('filing_date') or e.get('date')}|{e.get('type')}|{e.get('description')}"
                for e in cached_entries
            )
            for e in current_entries:
                sig = f"{e.get('filing_date') or e.get('date')}|{e.get('type')}|{e.get('description')}"
                if sig not in cached_sigs:
                    new_entries.append(e)

        # Update cache and persist to SQLite historical DB
        self.save_case_cache(case_number, county, latest)
        try:
            record_case_docket(
                county_id=county,
                case_summary=latest,
                dockets=current_entries
            )
        except Exception as e:
            pass

        return {
            "case_number": case_number,
            "county": county,
            "title": latest.get("title", ""),
            "url": latest.get("url", ""),
            "total_entries": len(current_entries),
            "new_entries": new_entries,
            "has_new_activity": len(new_entries) > 0,
            "latest_event": current_entries[0] if current_entries else None,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

    def check_all(self) -> List[Dict[str, Any]]:
        watchlist = self.get_watchlist()
        results = []
        for item in watchlist:
            res = self.check_case(item)
            results.append(res)
        return results
