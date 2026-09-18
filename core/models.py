"""
Canonical data models for Ohio Justice & Custody Monitor.
Standardizes heterogeneous county court docket and jail management system structures.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class DocketEntry(BaseModel):
    sequence_id: Optional[int] = None
    entry_date: Optional[str] = None
    description: str
    docket_type: Optional[str] = None
    amount: Optional[str] = None
    document_url: Optional[str] = None
    raw_text: Optional[str] = None


class CaseParty(BaseModel):
    role: str
    name: str
    attorney: Optional[str] = None


class CaseSummary(BaseModel):
    case_number: str
    county: str = "cuyahoga_oh"
    title: str
    case_type: str = "Criminal"
    filing_date: Optional[str] = None
    judge: Optional[str] = None
    status: Optional[str] = None
    parties: List[CaseParty] = Field(default_factory=list)
    docket_entries: List[DocketEntry] = Field(default_factory=list)
    docket_count: int = 0
    source_url: Optional[str] = None
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InmateRecord(BaseModel):
    inmate_id: str
    county: str
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    booking_date: Optional[str] = None
    release_date: Optional[str] = None
    dob: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    race: Optional[str] = None
    charges: List[str] = Field(default_factory=list)
    status: Optional[str] = "ACTIVE"
    photo_url: Optional[str] = None
    housing_facility: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class CustodyCheckResult(BaseModel):
    queried_name: str
    is_in_custody: bool
    total_matches: int
    matches: List[InmateRecord] = Field(default_factory=list)
    queried_counties: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CourtServiceConfig(BaseModel):
    adapter: Optional[str] = "none"
    base_url: Optional[str] = None
    enabled: bool = True
    notes: Optional[str] = None


class JailServiceConfig(BaseModel):
    adapter: str  # e.g., 'ocv_s3', 'ocv_rtjb', 'summit_web', 'odrc_portal'
    feed_type: str  # 'direct_s3_json', 'rtjb_feed', 'web_scrape', 'odrc_api'
    app_id: Optional[str] = None
    primary_url: Optional[str] = None
    fallback_url: Optional[str] = None
    enabled: bool = True
    notes: Optional[str] = None


class CountyConfig(BaseModel):
    id: str  # e.g., 'cuyahoga_oh', 'lake_oh', 'summit_oh'
    name: str
    county: str
    state: str = "OH"
    fips: Optional[str] = None
    court_service: Optional[CourtServiceConfig] = None
    jail_service: Optional[JailServiceConfig] = None
    active: bool = True


class WatchlistItem(BaseModel):
    case_number: str
    county: str = "cuyahoga_oh"
    target_name: Optional[str] = None
    added_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_checked: Optional[str] = None
    last_entry_count: int = 0
    active: bool = True
    notes: Optional[str] = None
