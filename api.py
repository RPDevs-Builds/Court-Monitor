#!/usr/bin/env python3
"""
Ohio Justice & Custody Monitor REST API Service
FastAPI-powered REST API for searching multi-county court records, case lookup,
docket activity monitoring, and statewide jail & prison custody status.
"""

from typing import Dict, List, Optional, Any
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from court_client import CuyahogaCourtClient, BASE_URL
from monitor_engine import DocketMonitorEngine
from jail_client import CuyahogaJailClient
from core.registry import get_registry
from adapters.court import get_court_adapter
from adapters.jail import get_jail_adapter, check_custody_statewide
from core.db import (
    get_db_stats,
    get_inmate_history,
    get_subject_timeline,
    run_correlation_engine,
    record_inmates_snapshot,
    get_db,
    normalize_name,
    get_ohio_coverage_summary,
    get_remaining_counties,
)

app = FastAPI(
    title="Court Monitor API",
    description="Multi-jurisdiction REST API to search court records, inspect criminal case summaries/charges, extract full dockets, monitor court activity, and verify county jail & state prison custody status across multiple counties and states.",
    version="2.0.0"
)

client = CuyahogaCourtClient()
monitor = DocketMonitorEngine(client)
jail_client = CuyahogaJailClient()
registry = get_registry()


# Pydantic Request Models
class NameSearchRequest(BaseModel):
    last_name: str = Field(..., description="Defendant last name (min 2 chars)", example="O'Boyle")
    first_name: str = Field("", description="Defendant first name", example="Caitlin")
    dob_year: str = Field("", description="4-digit birth year", example="1996")
    dob_month: str = Field("", description="2-digit birth month", example="12")


class CaseSearchRequest(BaseModel):
    year: str = Field(..., description="4-digit case year", example="2026")
    number: str = Field(..., description="Case number", example="711470")
    category: str = Field("CR", description="Case category (CR for Criminal)", example="CR")


class WatchRequest(BaseModel):
    case_number: str = Field(..., description="Case Number (e.g. CR-26-711470-A)", example="CR-26-711470-A")
    county: str = Field("cuyahoga_oh", description="County ID", example="cuyahoga_oh")
    year: str = Field("", description="Case year", example="2026")
    number: str = Field("", description="Case number", example="711470")
    docket_url: str = Field("", description="Direct docket URL", example="")
    label: str = Field("", description="Friendly label", example="THE STATE OF OHIO vs. CAITLIN O'BOYLE")


@app.get("/")
def root():
    return {
        "service": "Ohio Justice & Custody Monitor API",
        "docs": "/docs",
        "status": "ready",
        "indexed_counties": len(registry.counties),
        "version": "2.0.0"
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


# -------------------------------------------------------------
# Multi-County Registry & Metadata Endpoints
# -------------------------------------------------------------
@app.get("/api/counties")
def list_counties(active_only: bool = True):
    """List all registered Ohio counties, court adapters, and jail services."""
    return [c.model_dump() for c in registry.list_counties(active_only=active_only)]


@app.get("/api/counties/coverage")
@app.get("/api/counties/coverage/summary")
def get_counties_coverage_summary():
    """Get instant coverage statistics across all 88 Ohio counties directly from SQLite."""
    return get_ohio_coverage_summary()


@app.get("/api/counties/remaining")
@app.get("/api/counties/coverage/remaining")
def get_counties_remaining(
    type: str = Query("neither", description="Filter type: neither (default), court, jail, all")
):
    """Instantly query remaining uncovered counties from SQLite."""
    summary = get_ohio_coverage_summary()
    remaining = get_remaining_counties(type)
    return {
        "summary": summary,
        "filter": type,
        "count": len(remaining),
        "remaining_counties": remaining
    }


@app.get("/api/counties/{county_id}")

def get_county_details(county_id: str):
    """Get integration details for a specific county."""
    county = registry.get_county(county_id)
    if not county:
        raise HTTPException(status_code=404, detail=f"County {county_id} not found in registry")
    return county.model_dump()


# -------------------------------------------------------------
# Jail & Custody Endpoints (Multi-County & Statewide)
# -------------------------------------------------------------
@app.get("/api/jail/statewide/status")
def get_statewide_custody(name: str = Query(..., description="Full or partial name to check statewide")):
    """Check custody across all enabled Ohio county jails and the Ohio State Prison system (ODRC)."""
    res = check_custody_statewide(name)
    return res.model_dump()


@app.get("/api/jail/{county_id}/status")
def get_county_jail_status(county_id: str, name: str = Query(..., description="Full or partial name")):
    """Check custody status in a specific county jail facility."""
    adapter = get_jail_adapter(county_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"No active jail adapter found for {county_id}")
    res = adapter.check_custody(name)
    return res.model_dump()


@app.get("/api/jail/{county_id}/roster")
def get_county_jail_roster(county_id: str, limit: int = Query(50, ge=1, le=500)):
    """Fetch recent inmate roster from a specific county facility."""
    adapter = get_jail_adapter(county_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"No active jail adapter found for {county_id}")
    roster = adapter.fetch_roster()
    return {
        "county": county_id,
        "total_inmates": len(roster),
        "limit": limit,
        "inmates": [inmate.model_dump() for inmate in roster[:limit]]
    }


# -------------------------------------------------------------
# Court Docket Endpoints (Multi-County)
# -------------------------------------------------------------
@app.get("/api/court/{county_id}/search/name")
def search_court_by_name(county_id: str, last_name: str = Query(...), first_name: str = Query("")):
    """Search court case records by party name in a specific county."""
    adapter = get_court_adapter(county_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"No active court adapter found for {county_id}")
    results = adapter.search_by_name(last_name, first_name)
    return {
        "county": county_id,
        "query": {"last_name": last_name, "first_name": first_name},
        "count": len(results),
        "results": [r.model_dump() for r in results]
    }


@app.get("/api/court/{county_id}/docket/{case_number}")
def get_court_docket(county_id: str, case_number: str):
    """Fetch complete chronological docket entries from a specific county."""
    adapter = get_court_adapter(county_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"No active court adapter found for {county_id}")
    entries = adapter.get_docket(case_number)
    return {
        "county": county_id,
        "case_number": case_number,
        "count": len(entries),
        "entries": [e.model_dump() for e in entries]
    }


# -------------------------------------------------------------
# Legacy Cuyahoga Routes (100% Backwards Compatible)
# -------------------------------------------------------------
@app.get("/api/curl")
def get_curl(url: str = Query("https://cpdocket.cp.cuyahogacounty.gov/CR_CaseInformation_Docket.aspx?q=hRRTYX-BnjfUgnoAk-HSrQ00n6DjqAxFUzIxKeQ1ac41")):
    """Generate a live, valid curl command with active session cookies."""
    curl_cmd = client.generate_curl_command(url)
    cookies = client.get_cookies()
    return {
        "target_url": url,
        "curl_command": curl_cmd,
        "cookies": cookies
    }


@app.get("/api/cookies")
def get_cookies():
    """Retrieve freshly validated session and security cookies."""
    cookies = client.get_cookies()
    return {"cookies": cookies}


@app.get("/api/search/name")
def search_by_name_get(
    last_name: str = Query(..., min_length=2, description="Last name"),
    first_name: str = Query("", description="First name"),
    dob_year: str = Query("", description="4-digit birth year"),
    dob_month: str = Query("", description="2-digit birth month"),
    county: str = Query("cuyahoga_oh", description="Target county / court (e.g. cuyahoga_oh, cleveland_muni_oh)")
):
    """Search court records by party/defendant name across supported courts."""
    court_adapter = get_court_adapter(county)
    if court_adapter and county != "cuyahoga_oh":
        cases = court_adapter.search_by_name(last_name, first_name)
        return {
            "query": {"last_name": last_name, "first_name": first_name, "county": county},
            "court": getattr(court_adapter, "court_name", county),
            "count": len(cases),
            "results": [c.model_dump() for c in cases]
        }

    results = client.search_criminal_name(last_name, first_name, dob_year, dob_month)
    return {
        "query": {
            "last_name": last_name,
            "first_name": first_name,
            "dob_year": dob_year,
            "dob_month": dob_month,
            "county": county
        },
        "count": len(results),
        "results": results
    }


@app.post("/api/search/name")
def search_by_name_post(req: NameSearchRequest):
    results = client.search_criminal_name(req.last_name, req.first_name, req.dob_year, req.dob_month)
    return {
        "query": req.model_dump(),
        "count": len(results),
        "results": results
    }


@app.get("/api/search/case")
def search_by_case_get(
    year: Optional[str] = Query(None, description="4-digit case year"),
    number: Optional[str] = Query(None, description="Case number"),
    case: Optional[str] = Query(None, description="Full case number (e.g. 2026-CRB-001234)"),
    category: str = Query("CR", description="Case category"),
    county: str = Query("cuyahoga_oh", description="Target county / court")
):
    """Search case by number across supported courts."""
    case_query = case or (f"{year}-{number}" if (year and number) else (number or year or ""))
    court_adapter = get_court_adapter(county)
    if court_adapter and county != "cuyahoga_oh":
        summary = court_adapter.search_by_case(case_query)
        return {
            "query": {"case": case_query, "county": county},
            "court": getattr(court_adapter, "court_name", county),
            "count": 1 if summary else 0,
            "results": [summary.model_dump()] if summary else []
        }

    if category.upper() == "CR" and year and number:
        results = client.search_criminal_case(year, number)
        return {
            "query": {"year": year, "number": number, "category": category, "county": county},
            "count": len(results),
            "results": results
        }
    raise HTTPException(status_code=400, detail="Year and number required for Cuyahoga search")


@app.get("/api/summary/{case_number}")
def get_summary(
    case_number: str,
    county: str = Query("cuyahoga_oh", description="Target county / court")
):
    """Get full case details including parties and initial docket entries."""
    court_adapter = get_court_adapter(county)
    if court_adapter and county != "cuyahoga_oh":
        summary = court_adapter.search_by_case(case_number)
        if not summary:
            raise HTTPException(status_code=404, detail=f"Case {case_number} not found in {county}")
        return summary.model_dump()

    data = client.get_case_summary(case_number)
    if not data:
        raise HTTPException(status_code=404, detail=f"Case {case_number} not found or failed to load")
    return data


@app.get("/api/docket/{case_number}")
def get_docket(
    case_number: str,
    county: str = Query("cuyahoga_oh", description="Target county / court")
):
    """Get complete chronological docket for a case."""
    court_adapter = get_court_adapter(county)
    if court_adapter and county != "cuyahoga_oh":
        entries = court_adapter.get_docket(case_number)
        return {
            "case_number": case_number,
            "county": county,
            "court": getattr(court_adapter, "court_name", county),
            "count": len(entries),
            "entries": [e.model_dump() for e in entries]
        }

    entries = client.get_docket(case_number)
    return {
        "case_number": case_number,
        "county": county,
        "count": len(entries),
        "entries": entries
    }


@app.get("/api/court/session/{county_id}")
def get_court_session_status(county_id: str):
    """Inspect active session status and WAF token state for a court."""
    adapter = get_court_adapter(county_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"No court adapter registered for {county_id}")
    cookies = getattr(adapter, "cookies", {})
    return {
        "county_id": county_id,
        "court_name": getattr(adapter, "court_name", county_id),
        "has_waf_token": "aws-waf-token" in cookies,
        "has_session_id": "ASP.NET_SessionId" in cookies,
        "cookie_count": len(cookies),
        "cookies": {k: ("***" if "token" in k or "Session" in k else v) for k, v in cookies.items()}
    }


@app.get("/api/jail/status")
def check_jail_status(name: str = Query("Caitlin O'Boyle", description="Full name")):
    """Check Cuyahoga County Jail custody status."""
    return jail_client.check_custody_status(name)


@app.get("/api/jail/search")
def search_jail_roster(query: str = Query(..., description="Name query")):
    """Search Cuyahoga County Jail inmate roster."""
    matches = jail_client.search_inmate(query)
    return {
        "query": query,
        "count": len(matches),
        "matches": matches
    }


# -------------------------------------------------------------
# Watchlist & Monitor Endpoints
# -------------------------------------------------------------
@app.get("/api/watchlist")
def get_watchlist():
    return monitor.get_watchlist()


@app.post("/api/watchlist")
def add_to_watchlist(req: WatchRequest):
    return monitor.add_to_watchlist(
        case_number=req.case_number,
        county=req.county,
        year=req.year,
        number=req.number,
        docket_url=req.docket_url,
        label=req.label
    )


@app.delete("/api/watchlist/{case_number}")
def remove_from_watchlist(case_number: str, county: Optional[str] = None):
    success = monitor.remove_from_watchlist(case_number, county=county)
    if success:
        return {"status": "removed", "case_number": case_number}
    raise HTTPException(status_code=404, detail=f"Case {case_number} not found in watchlist")


@app.post("/api/monitor/check")
def run_monitor_check():
    """Trigger a fresh check across all watchlisted cases."""
    results = monitor.check_all()
    has_activity = any(r.get("has_new_activity") for r in results)
    return {
        "has_new_activity": has_activity,
        "results": results
    }


# -------------------------------------------------------------
# SQLite Historical & Correlation Analytics Endpoints
# -------------------------------------------------------------
@app.get("/api/db/stats")
def get_database_statistics():
    """Retrieve database metrics, record counts, and storage status."""
    return get_db_stats()


@app.get("/api/db/correlations")
def get_entity_correlations(name: Optional[str] = Query(None, description="Optional subject name to filter")):
    """Run/retrieve cross-jurisdiction entity correlations connecting jail bookings and court filings."""
    correlations = run_correlation_engine(name=name)
    return {
        "count": len(correlations),
        "correlations": correlations
    }


@app.get("/api/db/timeline/{name}")
def get_individual_timeline(
    name: str,
    age: Optional[int] = Query(None, description="Filter timeline to inmate with specific age"),
    dob: Optional[str] = Query(None, description="Filter timeline to inmate with specific date of birth"),
    inmate_id: Optional[str] = Query(None, description="Filter timeline to specific Inmate or Booking ID")
):
    """Generate a unified chronological cross-jurisdiction timeline for an individual with age/id disambiguation."""
    tl = get_subject_timeline(name, age=age, dob=dob, inmate_id=inmate_id)
    if not tl.get("events") and not tl.get("profiles_detected"):
        raise HTTPException(status_code=404, detail=f"No historical records found for subject '{name}'")
    return tl


@app.get("/api/history/inmates")
def query_inmate_history(
    name: Optional[str] = Query(None, description="Subject name"),
    age: Optional[int] = Query(None, description="Inmate age"),
    dob: Optional[str] = Query(None, description="Date of birth"),
    inmate_id: Optional[str] = Query(None, description="Inmate ID"),
    county: Optional[str] = Query(None, description="County ID filter"),
    limit: int = Query(50, ge=1, le=500)
):
    """Search historical inmate custody snapshots with age, DOB, and ID disambiguation."""
    return get_inmate_history(
        name=name,
        age=age,
        dob=dob,
        inmate_id=inmate_id,
        county_id=county,
        limit=limit
    )


def _background_roster_sync(counties: Optional[List[str]] = None):
    reg = get_registry()
    targets = counties or [c.county_id for c in reg.list_counties() if c.jail_service and c.jail_service.enabled]
    for cid in targets:
        adapter = get_jail_adapter(cid)
        if not adapter:
            continue
        try:
            records = adapter.fetch_roster()
            if records:
                record_inmates_snapshot(cid, records)
        except Exception:
            pass


@app.post("/api/db/sync-rosters")
def trigger_roster_sync(background_tasks: BackgroundTasks, counties: Optional[str] = Query(None, description="Comma-separated county IDs")):
    """Trigger background synchronization of live county jail rosters into SQLite."""
    target_list = [c.strip() for c in counties.split(",") if c.strip()] if counties else None
    background_tasks.add_task(_background_roster_sync, target_list)
    return {"status": "scheduled", "message": "Roster synchronization task scheduled in background"}

