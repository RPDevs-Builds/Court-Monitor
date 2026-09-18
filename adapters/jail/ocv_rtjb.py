"""
OCV Real-Time Jail Booking (RTJB) Adapter.
Connects to https://apps.myocv.com/feed/rtjb/{appID}/Inmates used by OCV Sheriff apps.
"""

import json
import re
import time
import urllib.request
from typing import Dict, List, Optional, Any

from adapters.jail.base import BaseJailAdapter
from core.models import InmateRecord


class OCVRTJBJailAdapter(BaseJailAdapter):
    def __init__(
        self,
        county_id: str,
        app_id: str,
        primary_url: Optional[str] = None,
        cache_ttl_seconds: int = 300
    ):
        super().__init__(county_id)
        self.app_id = app_id
        self.primary_url = primary_url or f"https://apps.myocv.com/feed/rtjb/{app_id}/Inmates"
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cached_roster: Optional[List[InmateRecord]] = None
        self._last_fetch_time: float = 0.0

    def fetch_roster(self, force_refresh: bool = False) -> List[InmateRecord]:
        now = time.time()
        if not force_refresh and self._cached_roster is not None:
            if now - self._last_fetch_time < self.cache_ttl_seconds:
                return self._cached_roster

        headers = {
            "User-Agent": "OCVApp/Android",
            "Accept": "application/json, text/html, */*"
        }
        req = urllib.request.Request(self.primary_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw_bytes = resp.read()
                try:
                    data = json.loads(raw_bytes.decode("utf-8"))
                except Exception:
                    # In case of non-JSON response
                    data = []
                
                records = self._parse_feed_items(data)
                self._cached_roster = records
                self._last_fetch_time = now
                return records
        except Exception as e:
            print(f"[-] Error fetching RTJB roster for {self.county_id} ({e})")
            return self._cached_roster or []

    def _parse_feed_items(self, raw_items: Any) -> List[InmateRecord]:
        records: List[InmateRecord] = []
        if not isinstance(raw_items, list):
            return records

        for item in raw_items:
            inmate_id = str(item.get("id", item.get("ID", item.get("inmate_id", ""))))
            title = item.get("title", item.get("name", "")).strip()
            content = item.get("content", item.get("description", ""))
            
            # Extract photo URL if available
            photo_url = None
            images = item.get("images", [])
            if isinstance(images, list) and len(images) > 0:
                first_img = images[0]
                if isinstance(first_img, dict):
                    photo_url = first_img.get("url") or first_img.get("image")
                elif isinstance(first_img, str):
                    photo_url = first_img

            # Extract fields from HTML content if present
            booking_date = None
            dob = None
            age = None
            charges = []
            if content:
                # Strip HTML tags
                text = re.sub(r"<[^>]+>", "\n", content)
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                for line in lines:
                    low = line.lower()
                    if any(k in low for k in ["inmate id", "inmate number", "jail id", "booking number", "booking id"]):
                        parsed_id = line.split(":", 1)[-1].strip()
                        if parsed_id and (not inmate_id or inmate_id == title):
                            inmate_id = parsed_id
                    elif any(k in low for k in ["booking date", "booked", "booking_date"]):
                        booking_date = line.split(":", 1)[-1].strip()
                    elif any(k in low for k in ["dob", "birth date", "birthday"]):
                        dob = line.split(":", 1)[-1].strip()
                    elif low.startswith("age:") or " age: " in low:
                        val = line.split(":", 1)[-1].strip().split()[0]
                        if val.isdigit():
                            age = int(val)
                    elif any(k in low for k in ["charge", "statute", "offense", "orc"]):
                        charges.append(line)
                if not charges and lines:
                    charges = lines[:3]

            records.append(InmateRecord(
                inmate_id=inmate_id or title,
                county=self.county_id,
                full_name=title,
                booking_date=booking_date,
                dob=dob,
                age=age,
                charges=charges,
                photo_url=photo_url,
                housing_facility=f"{self.county_id.replace('_oh', '').title()} County Jail",
                raw_data=item
            ))

        return records
