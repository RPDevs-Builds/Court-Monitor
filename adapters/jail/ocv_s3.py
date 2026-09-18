"""
OCV Direct S3 JSON Jail Adapter (e.g. Cuyahoga County Sheriff).
Fetches raw JMS JSON export from public S3/CloudFront bucket with local memory TTL caching.
"""

import datetime
import json
import time
import urllib.request
from typing import Dict, List, Optional, Any

from adapters.jail.base import BaseJailAdapter
from core.models import InmateRecord


class OCVS3JailAdapter(BaseJailAdapter):
    def __init__(
        self,
        county_id: str = "cuyahoga_oh",
        primary_url: str = "https://myocv.s3.us-east-1.amazonaws.com/ocvapps/a26544113/Cuyahogainmates.json",
        fallback_url: Optional[str] = "https://apps.myocv.com/feed/rtjb/a26544113/Inmates",
        cache_ttl_seconds: int = 300
    ):
        super().__init__(county_id)
        self.primary_url = primary_url
        self.fallback_url = fallback_url
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cached_roster: Optional[List[InmateRecord]] = None
        self._last_fetch_time: float = 0.0
        self._etag: Optional[str] = None

    def fetch_roster(self, force_refresh: bool = False) -> List[InmateRecord]:
        now = time.time()
        if not force_refresh and self._cached_roster is not None:
            if now - self._last_fetch_time < self.cache_ttl_seconds:
                return self._cached_roster

        headers = {
            "User-Agent": "CuyahogaSheriffApp/Android",
            "Accept": "application/json"
        }
        if self._etag and not force_refresh:
            headers["If-None-Match"] = self._etag

        req = urllib.request.Request(self.primary_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status == 304 and self._cached_roster is not None:
                    self._last_fetch_time = now
                    return self._cached_roster

                etag = resp.headers.get("ETag")
                if etag:
                    self._etag = etag

                raw = json.loads(resp.read().decode("utf-8"))
                records = self._normalize_s3_roster(raw)
                self._cached_roster = records
                self._last_fetch_time = now
                return records
        except urllib.error.HTTPError as e:
            if e.code == 304 and self._cached_roster is not None:
                self._last_fetch_time = now
                return self._cached_roster
            print(f"[-] Primary S3 fetch failed ({e}), attempting fallback...")
            return self._fetch_fallback()
        except Exception as e:
            print(f"[-] Error fetching primary roster ({e}), trying fallback...")
            return self._fetch_fallback()

    def _fetch_fallback(self) -> List[InmateRecord]:
        if not self.fallback_url:
            return []
        headers = {
            "User-Agent": "CuyahogaSheriffApp/Android",
            "Accept": "application/json"
        }
        req = urllib.request.Request(self.fallback_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                records = []
                for item in raw:
                    name = item.get("title", "").strip()
                    desc = item.get("content", "")
                    inmate_id = str(item.get("id", item.get("ID", "")))
                    imgs = item.get("images", [])
                    photo = imgs[0].get("url") if imgs else None
                    records.append(InmateRecord(
                        inmate_id=inmate_id,
                        county=self.county_id,
                        full_name=name,
                        charges=[desc] if desc else [],
                        photo_url=photo,
                        raw_data=item
                    ))
                self._cached_roster = records
                self._last_fetch_time = time.time()
                return records
        except Exception as e:
            print(f"[-] Fallback fetch error: {e}")
            return self._cached_roster or []

    def _normalize_s3_roster(self, raw_data: Any) -> List[InmateRecord]:
        records: List[InmateRecord] = []
        if not isinstance(raw_data, list):
            return records

        for item in raw_data:
            inmate_id = str(item.get("inmateId") or item.get("InmateID") or item.get("inmate_id") or item.get("id") or "")
            first = item.get("FirstName", item.get("first_name", ""))
            last = item.get("LastName", item.get("last_name", ""))
            middle = item.get("MiddleName", item.get("middle_name", ""))
            name = item.get("name")
            if not name:
                parts = [p for p in [last, first, middle] if p]
                name = " ".join(parts) if parts else "UNKNOWN"

            booking_date = item.get("bookingDate") or item.get("BookingDate") or item.get("booking_date")
            release_date = item.get("releasedDate") or item.get("ReleasedDate") or item.get("release_date")
            age_val = item.get("age") or item.get("Age")
            age = int(age_val) if age_val and str(age_val).isdigit() else None
            dob = item.get("dob") or item.get("DOB") or item.get("dateOfBirth")
            sex = item.get("gender") or item.get("Sex") or item.get("sex")
            race = item.get("race") or item.get("Race")
            photo = item.get("imageURL") or item.get("PhotoURL") or item.get("photo_url")
            
            raw_charges = item.get("charges") or item.get("Charges", [])
            charges: List[str] = []
            if isinstance(raw_charges, list):
                charges = [str(c) for c in raw_charges if c]
            elif isinstance(raw_charges, str) and raw_charges:
                charges = [raw_charges]

            records.append(InmateRecord(
                inmate_id=inmate_id,
                county=self.county_id,
                full_name=name,
                first_name=first,
                last_name=last,
                middle_name=middle,
                booking_date=booking_date,
                release_date=release_date,
                dob=dob,
                age=age,
                sex=sex,
                race=race,
                charges=charges,
                photo_url=photo,
                housing_facility="Cuyahoga County Corrections Center",
                raw_data=item
            ))

        return records
