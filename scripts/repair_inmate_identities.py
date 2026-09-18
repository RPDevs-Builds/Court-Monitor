#!/usr/bin/env python3
"""
repair_inmate_identities.py - Backfill inmate_id, dob, age from raw_payload and purge duplicates.
"""

import re
import json
import sqlite3
from pathlib import Path
from core.db import DB_PATH, init_db, compute_hash, normalize_name

def repair_database(db_path: Path = DB_PATH):
    print(f"[*] Starting identity backfill and deduplication on {db_path}...")
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Backfill records from raw_payload
    cursor.execute("SELECT id, county_id, inmate_id, full_name, dob, age, booking_date, status, charges, housing_facility, raw_payload FROM inmates_history;")
    rows = cursor.fetchall()
    print(f"[+] Loaded {len(rows)} rows to inspect and backfill...")

    updated_count = 0
    for r in rows:
        rid = r["id"]
        cid = r["county_id"]
        curr_iid = r["inmate_id"]
        curr_dob = r["dob"]
        curr_age = r["age"]
        curr_bdate = r["booking_date"]
        raw_str = r["raw_payload"]
        
        new_iid = curr_iid
        new_dob = curr_dob
        new_age = curr_age
        new_bdate = curr_bdate

        if raw_str:
            try:
                raw = json.loads(raw_str)
                # Cuyahoga JSON structure
                if "inmateId" in raw:
                    new_iid = str(raw.get("inmateId") or "")
                if "bookingDate" in raw:
                    new_bdate = raw.get("bookingDate")
                if "age" in raw and raw["age"] and str(raw["age"]).isdigit():
                    new_age = int(raw["age"])
                if "dob" in raw:
                    new_dob = str(raw["dob"])

                # Summit PDF raw structure
                if "inmate_no" in raw:
                    new_iid = str(raw.get("inmate_no") or "")
                if "dob" in raw:
                    new_dob = str(raw.get("dob") or "")

                # RTJB HTML content structure
                content = raw.get("content", "")
                if content and ("<" in content or "Inmate" in content):
                    text = re.sub(r"<[^>]+>", "\n", content)
                    for line in text.splitlines():
                        low = line.lower().strip()
                        if any(k in low for k in ["inmate id", "inmate number", "jail id", "booking number", "booking id"]):
                            parsed_id = line.split(":", 1)[-1].strip()
                            if parsed_id:
                                new_iid = parsed_id
                        elif any(k in low for k in ["booking date", "booked", "booking_date"]):
                            new_bdate = line.split(":", 1)[-1].strip()
                        elif any(k in low for k in ["dob", "birth date", "birthday"]):
                            new_dob = line.split(":", 1)[-1].strip()
                        elif low.startswith("age:") or " age: " in low:
                            val = line.split(":", 1)[-1].strip().split()[0]
                            if val.isdigit():
                                new_age = int(val)
            except Exception as e:
                pass

        # Recompute hash with exact identity
        new_hash = compute_hash({
            "county_id": cid,
            "inmate_id": new_iid,
            "full_name": r["full_name"],
            "dob": new_dob,
            "age": new_age,
            "booking_date": new_bdate,
            "status": r["status"],
            "charges": r["charges"],
            "facility": r["housing_facility"]
        })

        cursor.execute("""
            UPDATE inmates_history
            SET inmate_id = ?, dob = ?, age = ?, booking_date = ?, record_hash = ?
            WHERE id = ?
        """, (new_iid, new_dob, new_age, new_bdate, new_hash, rid))
        updated_count += 1

    conn.commit()
    print(f"[+] Successfully backfilled and rehashed {updated_count} rows.")

    # 2. Identify and purge exact duplicate snapshots (same county, inmate_id, name, hash)
    cursor.execute("""
        SELECT county_id, inmate_id, name_normalized, record_hash, MIN(id) as keep_id, COUNT(*) as cnt
        FROM inmates_history
        GROUP BY county_id, inmate_id, name_normalized, record_hash
        HAVING cnt > 1;
    """)
    dup_groups = cursor.fetchall()
    purged_total = 0

    for dg in dup_groups:
        cid = dg["county_id"]
        iid = dg["inmate_id"]
        norm = dg["name_normalized"]
        rhash = dg["record_hash"]
        keep_id = dg["keep_id"]
        cnt = dg["cnt"]

        # Delete identical subsequent records with the same hash
        del_cur = conn.execute("""
            DELETE FROM inmates_history
            WHERE county_id = ? AND inmate_id = ? AND name_normalized = ? AND record_hash = ? AND id != ?
        """, (cid, iid, norm, rhash, keep_id))
        purged_total += del_cur.rowcount

    conn.commit()
    print(f"[+] Purged {purged_total} identical duplicate snapshot rows.")

    # 3. Purge test entries if any remain
    del_test = conn.execute("""
        DELETE FROM inmates_history 
        WHERE observed_at IN ('2026-09-18T11:32:06.045186+00:00', '2026-09-18T11:32:11.505672+00:00');
    """)
    conn.commit()
    print(f"[+] Purged {del_test.rowcount} development test rows.")

    # 4. Final verification counts
    cursor.execute("SELECT COUNT(*) FROM inmates_history;")
    final_snapshots = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) as c FROM (
            SELECT county_id, 
                   COALESCE(NULLIF(inmate_id, ''), name_normalized || '_' || COALESCE(dob, age, ''))
            FROM inmates_history
            GROUP BY county_id, COALESCE(NULLIF(inmate_id, ''), name_normalized || '_' || COALESCE(dob, age, ''))
        );
    """)
    final_unique = cursor.fetchone()[0]
    print(f"[*] Final Database State -> Total Snapshots: {final_snapshots}, Unique Inmates: {final_unique}")
    conn.close()

if __name__ == "__main__":
    repair_database()
