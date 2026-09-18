"""
Court Monitor - SQLite Database Persistence & Correlation Engine
Provides thread-safe relational storage for multi-jurisdiction court dockets,
jail inmate custody snapshots, agency vendor metadata, and cross-county entity correlation.
"""

import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = Path("/home/llmuser/projects/court-monitor/data/court_monitor.db")


def normalize_name(name: str) -> str:
    """Normalize a person's name for robust cross-jurisdiction matching."""
    if not name:
        return ""
    clean = re.sub(r"[^A-Za-z0-9 ]+", " ", name).upper()
    tokens = sorted([t for t in clean.split() if len(t) > 1])
    return " ".join(tokens)


def compute_hash(data: Any) -> str:
    """Compute SHA256 hex digest of a JSON-serializable structure."""
    s = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@contextmanager
def get_db(db_path: Path = DB_PATH):
    """Context manager for SQLite connections with WAL mode and row factory."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    """Initialize database schema with tables, foreign keys, and indexes."""
    with get_db(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS jurisdictions (
            county_id TEXT PRIMARY KEY,
            county TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'OH',
            name TEXT NOT NULL,
            fips TEXT,
            court_adapter TEXT,
            court_base_url TEXT,
            court_enabled INTEGER DEFAULT 0,
            jail_adapter TEXT,
            jail_feed_type TEXT,
            jail_app_id TEXT,
            jail_primary_url TEXT,
            jail_enabled INTEGER DEFAULT 0,
            raw_metadata TEXT,
            created_at TEXT NOT NULL,
            last_scanned_at TEXT
        );

        CREATE TABLE IF NOT EXISTS inmates_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            county_id TEXT NOT NULL,
            inmate_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            name_normalized TEXT NOT NULL,
            dob TEXT,
            age INTEGER,
            booking_date TEXT,
            release_date TEXT,
            status TEXT DEFAULT 'ACTIVE',
            charges TEXT,
            housing_facility TEXT,
            record_hash TEXT NOT NULL,
            raw_payload TEXT,
            observed_at TEXT NOT NULL,
            FOREIGN KEY (county_id) REFERENCES jurisdictions(county_id)
        );

        CREATE TABLE IF NOT EXISTS court_cases (
            case_id TEXT PRIMARY KEY,
            county_id TEXT NOT NULL,
            case_number TEXT NOT NULL,
            case_title TEXT,
            case_type TEXT,
            filing_date TEXT,
            judge TEXT,
            status TEXT,
            parties TEXT,
            first_observed_at TEXT NOT NULL,
            last_updated_at TEXT NOT NULL,
            FOREIGN KEY (county_id) REFERENCES jurisdictions(county_id)
        );

        CREATE TABLE IF NOT EXISTS docket_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL,
            sequence_id TEXT,
            entry_date TEXT,
            description TEXT NOT NULL,
            docket_type TEXT,
            document_url TEXT,
            entry_hash TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            FOREIGN KEY (case_id) REFERENCES court_cases(case_id),
            UNIQUE(case_id, entry_hash)
        );

        CREATE TABLE IF NOT EXISTS metadata_correlations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correlation_key TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            county_id TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            rule_evidence TEXT NOT NULL,
            matched_at TEXT NOT NULL,
            FOREIGN KEY (county_id) REFERENCES jurisdictions(county_id),
            UNIQUE(correlation_key, entity_type, entity_id)
        );

        CREATE TABLE IF NOT EXISTS scan_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            county_id TEXT NOT NULL,
            service_type TEXT NOT NULL,
            status TEXT NOT NULL,
            records_discovered INTEGER DEFAULT 0,
            records_changed INTEGER DEFAULT 0,
            duration_ms REAL,
            details TEXT,
            scanned_at TEXT NOT NULL,
            FOREIGN KEY (county_id) REFERENCES jurisdictions(county_id)
        );

        CREATE INDEX IF NOT EXISTS idx_inmates_normalized ON inmates_history(name_normalized);
        CREATE INDEX IF NOT EXISTS idx_inmates_county ON inmates_history(county_id);
        CREATE INDEX IF NOT EXISTS idx_inmates_hash ON inmates_history(record_hash);
        CREATE INDEX IF NOT EXISTS idx_inmates_inmate_id ON inmates_history(inmate_id);
        CREATE INDEX IF NOT EXISTS idx_inmates_age ON inmates_history(age);
        CREATE INDEX IF NOT EXISTS idx_inmates_dob ON inmates_history(dob);
        CREATE INDEX IF NOT EXISTS idx_cases_county ON court_cases(county_id);
        CREATE INDEX IF NOT EXISTS idx_cases_number ON court_cases(case_number);
        CREATE INDEX IF NOT EXISTS idx_docket_case ON docket_entries(case_id);
        CREATE INDEX IF NOT EXISTS idx_correlations_key ON metadata_correlations(correlation_key);
        CREATE INDEX IF NOT EXISTS idx_scan_county ON scan_events(county_id);
        """)

        # Migration check for existing databases
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(inmates_history)")
        existing_cols = {col[1] for col in cursor.fetchall()}
        if "dob" not in existing_cols:
            cursor.execute("ALTER TABLE inmates_history ADD COLUMN dob TEXT")
        if "age" not in existing_cols:
            cursor.execute("ALTER TABLE inmates_history ADD COLUMN age INTEGER")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inmates_inmate_id ON inmates_history(inmate_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inmates_age ON inmates_history(age)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inmates_dob ON inmates_history(dob)")



def sync_registry_to_db(registry_data: Dict[str, Any], db_path: Path = DB_PATH) -> int:
    """Upsert all jurisdictions from agency_registry.json into SQLite."""
    count = 0
    now = datetime.now(timezone.utc).isoformat()
    with get_db(db_path) as conn:
        for cid, data in registry_data.get("counties", {}).items():
            c_srv = data.get("court_service") or {}
            j_srv = data.get("jail_service") or {}
            conn.execute("""
            INSERT INTO jurisdictions (
                county_id, county, state, name, fips,
                court_adapter, court_base_url, court_enabled,
                jail_adapter, jail_feed_type, jail_app_id, jail_primary_url, jail_enabled,
                raw_metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(county_id) DO UPDATE SET
                county = excluded.county,
                state = excluded.state,
                name = excluded.name,
                fips = excluded.fips,
                court_adapter = excluded.court_adapter,
                court_base_url = excluded.court_base_url,
                court_enabled = excluded.court_enabled,
                jail_adapter = excluded.jail_adapter,
                jail_feed_type = excluded.jail_feed_type,
                jail_app_id = excluded.jail_app_id,
                jail_primary_url = excluded.jail_primary_url,
                jail_enabled = excluded.jail_enabled,
                raw_metadata = excluded.raw_metadata
            """, (
                cid,
                data.get("county", ""),
                data.get("state", "OH"),
                data.get("name", ""),
                data.get("fips", ""),
                c_srv.get("adapter", "none"),
                c_srv.get("base_url"),
                1 if c_srv.get("enabled", False) else 0,
                j_srv.get("adapter", "none"),
                j_srv.get("feed_type"),
                j_srv.get("app_id"),
                j_srv.get("primary_url"),
                1 if j_srv.get("enabled", False) else 0,
                json.dumps(data),
                now
            ))
            count += 1
    return count


def record_inmates_snapshot(
    county_id: str,
    records: List[Any],
    db_path: Path = DB_PATH
) -> Tuple[int, int]:
    """
    Commit an inmate custody snapshot for a jurisdiction.
    Returns (new_or_changed_count, unchanged_count).
    """
    now = datetime.now(timezone.utc).isoformat()
    new_or_changed = 0
    unchanged = 0

    with get_db(db_path) as conn:
        for r in records:
            if hasattr(r, "inmate_id"):
                iid = r.inmate_id
                fname = r.full_name
                bdate = r.booking_date
                dob = getattr(r, "dob", None)
                age = getattr(r, "age", None)
                status = getattr(r, "status", "ACTIVE") or "ACTIVE"
                charges = json.dumps(r.charges) if isinstance(r.charges, list) else str(r.charges)
                facility = r.housing_facility
                raw = json.dumps(r.raw_data) if r.raw_data else None
            else:
                iid = str(r.get("inmate_id") or r.get("inmateId") or r.get("id") or "")
                fname = str(r.get("full_name") or r.get("name") or "")
                bdate = r.get("booking_date") or r.get("bookingDate")
                dob = r.get("dob") or r.get("DOB") or r.get("dateOfBirth")
                age_val = r.get("age") or r.get("Age")
                age = int(age_val) if age_val and str(age_val).isdigit() else None
                status = r.get("status", "ACTIVE")
                charges = json.dumps(r.get("charges", []))
                facility = r.get("housing_facility")
                raw = json.dumps(r.get("raw_data") or r)

            norm_name = normalize_name(fname)
            rec_hash = compute_hash({
                "county_id": county_id,
                "inmate_id": iid,
                "full_name": fname,
                "dob": dob,
                "age": age,
                "booking_date": bdate,
                "status": status,
                "charges": charges,
                "facility": facility
            })

            # Strict identity check: match by unique inmate_id if present,
            # or by name + DOB/age. Unless the inmate name AND birthday/age are the same, they are NOT the same.
            if iid and iid.strip():
                latest = conn.execute("""
                    SELECT record_hash FROM inmates_history
                    WHERE county_id = ? AND inmate_id = ?
                    ORDER BY id DESC LIMIT 1
                """, (county_id, iid.strip())).fetchone()
            elif dob and dob.strip():
                latest = conn.execute("""
                    SELECT record_hash FROM inmates_history
                    WHERE county_id = ? AND name_normalized = ? AND dob = ?
                    ORDER BY id DESC LIMIT 1
                """, (county_id, norm_name, dob.strip())).fetchone()
            elif age is not None:
                latest = conn.execute("""
                    SELECT record_hash FROM inmates_history
                    WHERE county_id = ? AND name_normalized = ? AND age = ?
                    ORDER BY id DESC LIMIT 1
                """, (county_id, norm_name, age)).fetchone()
            else:
                latest = conn.execute("""
                    SELECT record_hash FROM inmates_history
                    WHERE county_id = ? AND name_normalized = ? AND (dob IS NULL OR dob = '') AND age IS NULL
                    ORDER BY id DESC LIMIT 1
                """, (county_id, norm_name)).fetchone()

            if latest and latest["record_hash"] == rec_hash:
                unchanged += 1
                continue

            conn.execute("""
                INSERT INTO inmates_history (
                    county_id, inmate_id, full_name, name_normalized,
                    dob, age, booking_date, status, charges, housing_facility,
                    record_hash, raw_payload, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                county_id, iid, fname, norm_name,
                dob, age, bdate, status, charges, facility,
                rec_hash, raw, now
            ))
            new_or_changed += 1

        conn.execute(
            "UPDATE jurisdictions SET last_scanned_at = ? WHERE county_id = ?",
            (now, county_id)
        )

    return new_or_changed, unchanged


def record_case_docket(
    county_id: str,
    case_summary: Any,
    dockets: List[Any],
    db_path: Path = DB_PATH
) -> int:
    """Upsert court case and insert new chronological docket entries. Returns new docket entries count."""
    now = datetime.now(timezone.utc).isoformat()
    if hasattr(case_summary, "case_number"):
        cnum = case_summary.case_number
        ctitle = case_summary.title
        ctype = getattr(case_summary, "case_type", None)
        fdate = getattr(case_summary, "filing_date", None)
        judge = getattr(case_summary, "judge", None)
        cstatus = getattr(case_summary, "status", None)
        parties_data = [p.dict() if hasattr(p, "dict") else p for p in getattr(case_summary, "parties", [])]
    else:
        cnum = case_summary.get("case_number", "")
        ctitle = case_summary.get("title", "")
        ctype = case_summary.get("case_type")
        fdate = case_summary.get("filing_date")
        judge = case_summary.get("judge")
        cstatus = case_summary.get("status")
        parties_data = case_summary.get("parties", [])

    # If parties empty, extract defendant from dict or title
    if not parties_data:
        def_obj = case_summary.get("defendant") if isinstance(case_summary, dict) else getattr(case_summary, "defendant", None)
        if isinstance(def_obj, dict) and def_obj.get("name"):
            parties_data = [{"name": def_obj["name"], "role": "DEFENDANT", "status": def_obj.get("status")}]
        elif def_obj and hasattr(def_obj, "name"):
            parties_data = [{"name": def_obj.name, "role": "DEFENDANT"}]
        elif ctitle and " vs. " in ctitle:
            def_part = ctitle.split(" vs. ", 1)[1].strip()
            parties_data = [{"name": def_part, "role": "DEFENDANT"}]
        elif ctitle and " VS " in ctitle.upper():
            parts = re.split(r"\s+VS\.?\s+", ctitle, flags=re.IGNORECASE)
            if len(parts) > 1:
                parties_data = [{"name": parts[1].strip(), "role": "DEFENDANT"}]

    parties = json.dumps(parties_data)
    case_id = f"{county_id}_{cnum}"
    new_entries = 0

    with get_db(db_path) as conn:
        conn.execute("""
            INSERT INTO court_cases (
                case_id, county_id, case_number, case_title, case_type,
                filing_date, judge, status, parties, first_observed_at, last_updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id) DO UPDATE SET
                case_title = excluded.case_title,
                case_type = excluded.case_type,
                judge = excluded.judge,
                status = excluded.status,
                parties = excluded.parties,
                last_updated_at = excluded.last_updated_at
        """, (
            case_id, county_id, cnum, ctitle, ctype,
            fdate, judge, cstatus, parties, now, now
        ))

        for d in dockets:
            if hasattr(d, "description"):
                seq = getattr(d, "sequence_id", None) or getattr(d, "row_index", None)
                edate = getattr(d, "entry_date", None) or getattr(d, "proceeding_date", None) or getattr(d, "filing_date", None)
                desc = getattr(d, "description", "") or ""
                dtype = getattr(d, "docket_type", None) or getattr(d, "type", None)
                doc_url = getattr(d, "document_url", None) or getattr(d, "image_url", None)
            else:
                seq = d.get("sequence_id") or d.get("row_index")
                edate = d.get("entry_date") or d.get("proceeding_date") or d.get("filing_date")
                desc = d.get("description") or ""
                dtype = d.get("docket_type") or d.get("type")
                doc_url = d.get("document_url") or d.get("image_url")

            ehash = compute_hash({"seq": seq, "date": edate, "desc": desc})
            try:
                conn.execute("""
                    INSERT INTO docket_entries (
                        case_id, sequence_id, entry_date, description,
                        docket_type, document_url, entry_hash, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (case_id, seq, edate, desc, dtype, doc_url, ehash, now))
                new_entries += 1
            except sqlite3.IntegrityError:
                pass

    return new_entries


def log_scan_event(
    county_id: str,
    service_type: str,
    status: str,
    discovered: int = 0,
    changed: int = 0,
    duration_ms: float = 0.0,
    details: Optional[str] = None,
    db_path: Path = DB_PATH
) -> None:
    """Log an operational audit scan event."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db(db_path) as conn:
        conn.execute("""
            INSERT INTO scan_events (
                county_id, service_type, status, records_discovered,
                records_changed, duration_ms, details, scanned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (county_id, service_type, status, discovered, changed, duration_ms, details, now))


def run_correlation_engine(name: Optional[str] = None, db_path: Path = DB_PATH) -> List[Dict[str, Any]]:
    """
    Cross-reference inmates and court cases across all jurisdictions.
    Links persons who have both active/historical jail bookings and court filings.
    Uses token-set similarity and normalized name alignment.
    """
    now = datetime.now(timezone.utc).isoformat()
    correlations = []

    with get_db(db_path) as conn:
        cases_rows = conn.execute("""
            SELECT case_id, county_id as court_county, case_number, case_title, parties
            FROM court_cases
        """).fetchall()

        if not cases_rows:
            return []

        # Parse cases candidate tokens
        cases = []
        for c in cases_rows:
            party_names = []
            try:
                plist = json.loads(c["parties"] or "[]")
                for p in plist:
                    if isinstance(p, dict) and p.get("name"):
                        party_names.append(p["name"])
            except Exception:
                pass

            # Also check case_title
            title = c["case_title"] or ""
            if " vs. " in title:
                party_names.append(title.split(" vs. ", 1)[1].strip())
            elif " VS " in title.upper():
                pts = re.split(r"\s+VS\.?\s+", title, flags=re.IGNORECASE)
                if len(pts) > 1:
                    party_names.append(pts[1].strip())

            norm_targets = [normalize_name(pn) for pn in party_names if pn]
            cases.append({
                "case_id": c["case_id"],
                "court_county": c["court_county"],
                "case_number": c["case_number"],
                "case_title": c["case_title"],
                "norm_targets": [t for t in norm_targets if t]
            })

        # Fetch inmates
        inmate_query = """
            SELECT DISTINCT name_normalized, full_name, inmate_id, county_id as jail_county
            FROM inmates_history
        """
        params = []
        if name:
            norm = normalize_name(name)
            inmate_query += " WHERE name_normalized = ? OR UPPER(full_name) LIKE ?"
            params = [norm, f"%{name.upper()}%"]

        inmate_rows = conn.execute(inmate_query, params).fetchall()

        for i in inmate_rows:
            i_norm = i["name_normalized"]
            i_tokens = set(i_norm.split())
            if not i_tokens:
                continue

            for c in cases:
                matched = False
                conf = 0.0

                for t in c["norm_targets"]:
                    t_tokens = set(t.split())
                    if not t_tokens:
                        continue
                    if i_norm == t:
                        matched = True
                        conf = 0.98 if i["jail_county"] == c["court_county"] else 0.88
                        break
                    elif len(i_tokens.intersection(t_tokens)) >= 2:
                        matched = True
                        conf = 0.90 if i["jail_county"] == c["court_county"] else 0.78
                        break

                if matched:
                    ckey = i_norm
                    evidence = {
                        "matched_name": i["full_name"],
                        "jail_county": i["jail_county"],
                        "inmate_id": i["inmate_id"],
                        "court_county": c["court_county"],
                        "case_number": c["case_number"],
                        "case_title": c["case_title"]
                    }
                    inmate_entity_id = i["inmate_id"] if (i["inmate_id"] and i["inmate_id"].strip()) else f"{i['jail_county']}_{i_norm}"

                    conn.execute("""
                        INSERT INTO metadata_correlations (
                            correlation_key, entity_type, entity_id, county_id,
                            confidence_score, rule_evidence, matched_at
                        ) VALUES (?, 'inmate', ?, ?, ?, ?, ?)
                        ON CONFLICT(correlation_key, entity_type, entity_id) DO UPDATE SET
                            confidence_score = excluded.confidence_score,
                            rule_evidence = excluded.rule_evidence,
                            matched_at = excluded.matched_at
                    """, (ckey, inmate_entity_id, i["jail_county"], conf, json.dumps(evidence), now))

                    conn.execute("""
                        INSERT INTO metadata_correlations (
                            correlation_key, entity_type, entity_id, county_id,
                            confidence_score, rule_evidence, matched_at
                        ) VALUES (?, 'case', ?, ?, ?, ?, ?)
                        ON CONFLICT(correlation_key, entity_type, entity_id) DO UPDATE SET
                            confidence_score = excluded.confidence_score,
                            rule_evidence = excluded.rule_evidence,
                            matched_at = excluded.matched_at
                    """, (ckey, c["case_id"], c["court_county"], conf, json.dumps(evidence), now))

                    correlations.append({
                        "subject": i["full_name"],
                        "correlation_key": ckey,
                        "jail_county": i["jail_county"],
                        "inmate_id": i["inmate_id"],
                        "court_county": c["court_county"],
                        "case_number": c["case_number"],
                        "confidence": conf
                    })

    return correlations


def get_inmate_history(
    name: Optional[str] = None,
    age: Optional[int] = None,
    dob: Optional[str] = None,
    inmate_id: Optional[str] = None,
    county_id: Optional[str] = None,
    limit: int = 50,
    db_path: Path = DB_PATH
) -> List[Dict[str, Any]]:
    """
    Query historical inmate custody snapshots with disambiguation filters
    (name, age, dob, inmate_id, county_id).
    """
    query = """
        SELECT county_id, inmate_id, full_name, name_normalized, dob, age,
               booking_date, release_date, status, charges, housing_facility,
               record_hash, observed_at
        FROM inmates_history
        WHERE 1=1
    """
    params: List[Any] = []
    if name:
        query += " AND (name_normalized = ? OR UPPER(full_name) LIKE ?)"
        params.extend([normalize_name(name), f"%{name.upper()}%"])
    if age is not None:
        query += " AND age = ?"
        params.append(age)
    if dob:
        query += " AND (dob = ? OR dob LIKE ?)"
        params.extend([dob.strip(), f"%{dob.strip()}%"])
    if inmate_id:
        query += " AND (inmate_id = ? OR inmate_id LIKE ?)"
        params.extend([inmate_id.strip(), f"%{inmate_id.strip()}%"])
    if county_id:
        query += " AND county_id = ?"
        params.append(county_id.strip())

    query += " ORDER BY booking_date DESC, observed_at DESC, id DESC LIMIT ?"
    params.append(limit)

    results = []
    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        for r in rows:
            charges_list = []
            if r["charges"]:
                try:
                    charges_list = json.loads(r["charges"])
                except Exception:
                    charges_list = [r["charges"]]
            results.append({
                "county_id": r["county_id"],
                "inmate_id": r["inmate_id"],
                "full_name": r["full_name"],
                "name_normalized": r["name_normalized"],
                "dob": r["dob"],
                "age": r["age"],
                "booking_date": r["booking_date"],
                "release_date": r["release_date"],
                "status": r["status"],
                "charges": charges_list,
                "facility": r["housing_facility"],
                "record_hash": r["record_hash"],
                "observed_at": r["observed_at"],
            })
    return results


def get_subject_timeline(
    name: str,
    age: Optional[int] = None,
    dob: Optional[str] = None,
    inmate_id: Optional[str] = None,
    db_path: Path = DB_PATH
) -> Dict[str, Any]:
    """Retrieve full unified timeline of jail bookings and court filings for a person,
    with age/dob/inmate_id disambiguation to prevent false-positive name collisions.
    """
    norm = normalize_name(name)
    timeline: List[Dict[str, Any]] = []

    with get_db(db_path) as conn:
        inmate_query = """
            SELECT county_id, inmate_id, full_name, name_normalized, dob, age,
                   booking_date, release_date, status, charges, housing_facility, observed_at
            FROM inmates_history
            WHERE name_normalized = ? OR UPPER(full_name) LIKE ?
            ORDER BY booking_date DESC, observed_at DESC
        """
        all_inmates = conn.execute(inmate_query, (norm, f"%{name.upper()}%")).fetchall()

        # Group into distinct person profiles
        profiles_map: Dict[str, Dict[str, Any]] = {}
        for r in all_inmates:
            iid = (r["inmate_id"] or "").strip()
            cid = r["county_id"]
            rag = r["age"]
            rdob = (r["dob"] or "").strip()
            prof_key = f"{cid}_{iid}" if iid else f"{cid}_{r['name_normalized']}_{rdob or rag or 'unknown'}"
            if prof_key not in profiles_map:
                profiles_map[prof_key] = {
                    "county_id": cid,
                    "inmate_id": iid or None,
                    "full_name": r["full_name"],
                    "age": rag,
                    "dob": rdob or None,
                    "record_count": 0,
                    "latest_booking": r["booking_date"] or r["observed_at"][:10],
                    "status": r["status"]
                }
            profiles_map[prof_key]["record_count"] += 1

        profiles_detected = list(profiles_map.values())

        # Filter inmates by user disambiguation parameters
        filtered_inmates = []
        for i in all_inmates:
            if inmate_id and (not i["inmate_id"] or inmate_id.lower() not in i["inmate_id"].lower()):
                continue
            if age is not None and i["age"] != age:
                continue
            if dob and (not i["dob"] or dob.lower() not in i["dob"].lower()):
                continue
            filtered_inmates.append(i)

        for i in filtered_inmates:
            charges_list = []
            if i["charges"]:
                try:
                    charges_list = json.loads(i["charges"])
                except Exception:
                    charges_list = [i["charges"]]
            timeline.append({
                "type": "jail_booking",
                "date": i["booking_date"] or i["observed_at"][:10],
                "county": i["county_id"],
                "title": f"Inmate Custody Record ({i['county_id']})",
                "details": {
                    "inmate_id": i["inmate_id"],
                    "dob": i["dob"],
                    "age": i["age"],
                    "status": i["status"],
                    "charges": charges_list,
                    "facility": i["housing_facility"]
                }
            })

        # Fetch court cases
        cases = conn.execute("""
            SELECT c.case_id, c.county_id, c.case_number, c.case_title,
                   c.filing_date, c.judge, c.status,
                   d.sequence_id, d.entry_date, d.description, d.docket_type, d.document_url
            FROM court_cases c
            LEFT JOIN docket_entries d ON c.case_id = d.case_id
            WHERE UPPER(c.case_title) LIKE ? OR UPPER(c.parties) LIKE ?
            ORDER BY COALESCE(d.entry_date, c.filing_date) DESC
        """, (f"%{name.upper()}%", f"%{name.upper()}%")).fetchall()

        # If filtered by inmate_id or age, exclude cases correlated with a DIFFERENT profile
        excluded_case_ids = set()
        if (inmate_id or age is not None) and len(profiles_detected) > 1:
            corr_rows = conn.execute("""
                SELECT entity_id, rule_evidence FROM metadata_correlations WHERE entity_type = 'case'
            """).fetchall()
            for cr in corr_rows:
                try:
                    ev = json.loads(cr["rule_evidence"])
                    ev_iid = ev.get("inmate_id")
                    if inmate_id and ev_iid and ev_iid != inmate_id:
                        excluded_case_ids.add(cr["entity_id"])
                except Exception:
                    pass

        for c in cases:
            if c["case_id"] in excluded_case_ids:
                continue
            timeline.append({
                "type": "court_docket" if c["description"] else "case_filing",
                "date": c["entry_date"] or c["filing_date"] or "N/A",
                "county": c["county_id"],
                "title": f"Case {c['case_number']} ({c['county_id']}): {c['case_title']}",
                "details": {
                    "docket_sequence": c["sequence_id"],
                    "description": c["description"],
                    "docket_type": c["docket_type"],
                    "document_url": c["document_url"],
                    "judge": c["judge"],
                    "case_status": c["status"]
                }
            })

    timeline.sort(key=lambda x: str(x.get("date", "")), reverse=True)
    return {
        "subject": name,
        "normalized": norm,
        "filter_applied": {
            "age": age,
            "dob": dob,
            "inmate_id": inmate_id
        },
        "multiple_profiles_detected": len(profiles_detected) > 1,
        "profiles_detected": profiles_detected,
        "total_events": len(timeline),
        "events": timeline
    }


def get_db_stats(db_path: Path = DB_PATH) -> Dict[str, Any]:
    """Get system-wide historical metrics from the database."""
    with get_db(db_path) as conn:
        jurisdictions = conn.execute("SELECT COUNT(*) as c FROM jurisdictions").fetchone()["c"]
        inmates_total = conn.execute("SELECT COUNT(*) as c FROM inmates_history").fetchone()["c"]
        inmates_unique = conn.execute("""
            SELECT COUNT(*) as c FROM (
                SELECT county_id, 
                       COALESCE(NULLIF(inmate_id, ''), name_normalized || '_' || COALESCE(dob, age, ''))
                FROM inmates_history
                GROUP BY county_id, COALESCE(NULLIF(inmate_id, ''), name_normalized || '_' || COALESCE(dob, age, ''))
            )
        """).fetchone()["c"]
        cases_total = conn.execute("SELECT COUNT(*) as c FROM court_cases").fetchone()["c"]
        dockets_total = conn.execute("SELECT COUNT(*) as c FROM docket_entries").fetchone()["c"]
        correlations_total = conn.execute("SELECT COUNT(DISTINCT correlation_key) as c FROM metadata_correlations").fetchone()["c"]
        scan_events_total = conn.execute("SELECT COUNT(*) as c FROM scan_events").fetchone()["c"]

    return {
        "jurisdictions_count": jurisdictions,
        "total_inmate_records": inmates_total,
        "unique_inmates_tracked": inmates_unique,
        "court_cases_tracked": cases_total,
        "docket_entries_tracked": dockets_total,
        "entity_correlations_count": correlations_total,
        "audit_scan_events": scan_events_total,
        "database_file": str(db_path),
        "file_size_bytes": db_path.stat().st_size if db_path.exists() else 0
    }
