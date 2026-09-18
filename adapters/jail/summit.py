"""
Summit County Sheriff Jail Adapter (Akron, Ohio).
Extracts live active inmate records from the official Sheriff Head Count Report.
"""

import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Any

from adapters.jail.base import BaseJailAdapter
from core.models import InmateRecord


REPORT_URL = "https://sheriff.summitoh.net/files/31565/file/activeoffenderreport.pdf"
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache"


class SummitJailAdapter(BaseJailAdapter):
    def __init__(
        self,
        county_id: str = "summit_oh",
        report_url: str = REPORT_URL,
        cache_ttl_seconds: int = 1800  # 30 minutes
    ):
        super().__init__(county_id)
        self.report_url = report_url
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cache_file = CACHE_DIR / "summit_roster.pdf"
        self._cached_roster: Optional[List[InmateRecord]] = None
        self._last_fetch_time: float = 0.0

    def fetch_roster(self, force_refresh: bool = False) -> List[InmateRecord]:
        now = time.time()
        if not force_refresh and self._cached_roster is not None:
            if now - self._last_fetch_time < self.cache_ttl_seconds:
                return self._cached_roster

        # Ensure cache dir exists
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Download or use cached PDF
        should_download = True
        if self.cache_file.exists() and not force_refresh:
            file_age = now - self.cache_file.stat().st_mtime
            if file_age < self.cache_ttl_seconds:
                should_download = False

        if should_download:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept": "application/pdf"
            }
            req = urllib.request.Request(self.report_url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    with open(self.cache_file, "wb") as f:
                        f.write(resp.read())
            except Exception as e:
                print(f"[-] Error downloading Summit County roster PDF: {e}")
                if not self.cache_file.exists():
                    return []

        # Parse PDF using pdftotext
        records = self._parse_pdf_file(self.cache_file)
        self._cached_roster = records
        self._last_fetch_time = now
        return records

    def _parse_pdf_file(self, pdf_path: Path) -> List[InmateRecord]:
        try:
            res = subprocess.run(
                ["pdftotext", str(pdf_path), "-"],
                capture_output=True,
                text=True,
                check=True
            )
            text = res.stdout
        except Exception as e:
            print(f"[-] Failed to run pdftotext on {pdf_path}: {e}")
            return []

        return self._parse_text(text)

    def _parse_text(self, text: str) -> List[InmateRecord]:
        records: List[InmateRecord] = []
        
        # Inmate blocks:
        # Inmate No (5-7 digits)
        # Inmate Name (e.g. ABSTON, DANISHA La-Shawn)
        # DOB (MM/DD/YYYY)
        # Race (e.g. B, W, H)
        # Sex (e.g. M, F)
        entry_pattern = re.compile(
            r"(?:\n|^)(\d{5,7})\s*\n+([A-Za-z\s\-\',]+)\s*\n+(\d{2}/\d{2}/\d{4})\s*\n+([A-Za-z])\s*\n+([MF])",
            re.MULTILINE
        )

        matches = list(entry_pattern.finditer(text))
        for i, match in enumerate(matches):
            inmate_no = match.group(1).strip()
            name_raw = match.group(2).strip()
            # Clean newlines inside name
            full_name = " ".join(name_raw.split())
            dob = match.group(3).strip()
            race = match.group(4).strip()
            sex = match.group(5).strip()

            # The text between this match and next match contains the charges/statutes
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            block_text = text[start_pos:end_pos]

            charges = []
            statute_desc_lines = re.findall(r"([A-Z0-9\s\-]+(?:\s*-\s*\d+\.\d+)?)", block_text)
            for line in block_text.splitlines():
                line_s = line.strip()
                if any(kw in line_s for kw in ["- 29", "MURDER", "ASSAULT", "THEFT", "BURGLARY", "OVI", "TRAFFICKING", "CONTEMPT", "WARRANT", "DRUG"]):
                    if line_s not in charges and len(line_s) > 3:
                        charges.append(line_s)

            records.append(InmateRecord(
                inmate_id=inmate_no,
                county=self.county_id,
                full_name=full_name,
                dob=dob,
                sex=sex,
                race=race,
                charges=charges[:5],
                housing_facility="Summit County Jail (Akron, OH)",
                raw_data={"dob": dob, "inmate_no": inmate_no}
            ))

        return records
