#!/usr/bin/env python3
"""
Court Monitor CLI
Unified multi-jurisdiction command line tool for searching court dockets, inspecting case charges,
monitoring activity across counties, and checking statewide jail/prison custody status.
"""

import argparse
import json
import sys
from typing import Dict, List, Optional, Any

from court_client import CuyahogaCourtClient, BASE_URL
from monitor_engine import DocketMonitorEngine
from jail_client import CuyahogaJailClient
from core.registry import get_registry
from adapters.jail import get_jail_adapter, check_custody_statewide
from adapters.court import get_court_adapter, TylerCourtAdapter
from core.db import (
    init_db,
    sync_registry_to_db,
    record_inmates_snapshot,
    record_case_docket,
    run_correlation_engine,
    get_inmate_history,
    get_subject_timeline,
    get_db_stats,
)

DEFAULT_DOCKET_URL = "https://cpdocket.cp.cuyahogacounty.gov/CR_CaseInformation_Docket.aspx?q=hRRTYX-BnjfUgnoAk-HSrQ00n6DjqAxFUzIxKeQ1ac41"


def print_table(rows, headers, title=None):
    if title:
        print(f"\n=== {title} ===")
    if not rows:
        print("No items found.")
        return
    widths = [len(h) for h in headers]
    for r in rows:
        for i, val in enumerate(r):
            widths[i] = max(widths[i], len(str(val)))
    
    hdr_str = " | ".join(f"{headers[i]:<{widths[i]}}" for i in range(len(headers)))
    sep_str = "-+-".join("-" * widths[i] for i in range(len(headers)))
    print(hdr_str)
    print(sep_str)
    for r in rows:
        row_str = " | ".join(f"{str(r[i]):<{widths[i]}}" for i in range(len(headers)))
        print(row_str)


def main():
    parser = argparse.ArgumentParser(
        description="Ohio Justice & Custody Monitor CLI (Multi-County)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # counties
    p_counties = sub.add_parser("counties", help="List all registered Ohio counties and integration capabilities")
    p_counties.add_argument("--json", action="store_true", help="Output as JSON")

    # search-name
    p_name = sub.add_parser("search-name", help="Search cases by defendant name")
    p_name.add_argument("--last", required=True, help="Last name (e.g. O'Boyle)")
    p_name.add_argument("--first", default="", help="First name (e.g. Caitlin)")
    p_name.add_argument("--year", default="", help="Birth year (e.g. 1996)")
    p_name.add_argument("--month", default="", help="Birth month (e.g. 12)")
    p_name.add_argument("--county", "-c", default="cuyahoga_oh", help="Target county / court (default: cuyahoga_oh, or cleveland_muni_oh)")
    p_name.add_argument("--waf-token", default=None, help="Optional AWS WAF token")
    p_name.add_argument("--session-id", default=None, help="Optional ASP.NET session ID")
    p_name.add_argument("--json", action="store_true", help="Output as JSON")

    # search-case
    p_case = sub.add_parser("search-case", help="Search case by case number or year/number")
    p_case.add_argument("--case", default=None, help="Full Case Number (e.g. 2026-CRB-001234 or CR-26-711470)")
    p_case.add_argument("--year", default=None, help="Case Year (e.g. 2026)")
    p_case.add_argument("--number", default=None, help="Case Number (e.g. 711470)")
    p_case.add_argument("--county", "-c", default="cuyahoga_oh", help="Target county / court (default: cuyahoga_oh, or cleveland_muni_oh)")
    p_case.add_argument("--waf-token", default=None, help="Optional AWS WAF token")
    p_case.add_argument("--session-id", default=None, help="Optional ASP.NET session ID")
    p_case.add_argument("--json", action="store_true", help="Output as JSON")

    # summary
    p_sum = sub.add_parser("summary", help="Fetch case summary, charges, actions")
    p_sum.add_argument("--case", default=None, help="Full Case Number")
    p_sum.add_argument("--year", default=None, help="Case Year")
    p_sum.add_argument("--number", default=None, help="Case Number")
    p_sum.add_argument("--county", "-c", default="cuyahoga_oh", help="Target county / court (default: cuyahoga_oh, or cleveland_muni_oh)")
    p_sum.add_argument("--waf-token", default=None, help="Optional AWS WAF token")
    p_sum.add_argument("--session-id", default=None, help="Optional ASP.NET session ID")
    p_sum.add_argument("--json", action="store_true", help="Output as JSON")

    # docket
    p_doc = sub.add_parser("docket", help="Fetch complete case docket")
    p_doc.add_argument("--case", default=None, help="Full Case Number")
    p_doc.add_argument("--url", default=None, help="Direct docket URL with token q")
    p_doc.add_argument("--year", default=None, help="Case Year")
    p_doc.add_argument("--number", default=None, help="Case Number")
    p_doc.add_argument("--county", "-c", default="cuyahoga_oh", help="Target county / court (default: cuyahoga_oh, or cleveland_muni_oh)")
    p_doc.add_argument("--waf-token", default=None, help="Optional AWS WAF token")
    p_doc.add_argument("--session-id", default=None, help="Optional ASP.NET session ID")
    p_doc.add_argument("--json", action="store_true", help="Output as JSON")

    # tyler-session-refresh
    p_tsess = sub.add_parser("tyler-session-refresh", help="Open browser on DISPLAY=:0.0 to solve Tyler Tech AWS WAF challenge and save session")
    p_tsess.add_argument("--county", "-c", default="cleveland_muni_oh", help="Target Tyler Tech court (default: cleveland_muni_oh)")
    p_tsess.add_argument("--timeout", type=int, default=60, help="Wait timeout in seconds (default: 60)")

    # curl
    p_curl = sub.add_parser("curl", help="Generate live, valid curl command with active cookies")
    p_curl.add_argument("--url", default=DEFAULT_DOCKET_URL, help="Target court URL")
    p_curl.add_argument("--county", "-c", default="cuyahoga_oh", help="Target court (default: cuyahoga_oh)")

    # watchlist
    sub.add_parser("watchlist", help="List all watched cases")

    # watch-add
    p_wadd = sub.add_parser("watch-add", help="Add a case to the watchlist")
    p_wadd.add_argument("--case", required=True, help="Case number (e.g. CR-26-711470-A)")
    p_wadd.add_argument("--county", "-c", default="cuyahoga_oh", help="County (default: cuyahoga_oh)")
    p_wadd.add_argument("--year", default="", help="Case Year")
    p_wadd.add_argument("--number", default="", help="Case Number")
    p_wadd.add_argument("--url", default="", help="Direct docket URL")
    p_wadd.add_argument("--label", default="", help="Friendly label")

    # watch-remove
    p_wrem = sub.add_parser("watch-remove", help="Remove a case from the watchlist")
    p_wrem.add_argument("--case", required=True, help="Case number to remove")
    p_wrem.add_argument("--county", "-c", default=None, help="Specific county to remove from")

    # monitor-check
    p_mcheck = sub.add_parser("monitor-check", help="Check watched cases for new docket activity")
    p_mcheck.add_argument("--case", default=None, help="Check only specific case")
    p_mcheck.add_argument("--json", action="store_true", help="Output as JSON")

    # jail-status (single county)
    p_jstat = sub.add_parser("jail-status", help="Check if individual is in custody at a specific county jail")
    p_jstat.add_argument("--name", required=True, help="Full or partial name (e.g. Caitlin O'Boyle)")
    p_jstat.add_argument("--county", "-c", default="cuyahoga_oh", help="Target county (default: cuyahoga_oh)")
    p_jstat.add_argument("--json", action="store_true", help="Output as JSON")

    # jail-statewide (all Ohio counties + ODRC)
    p_jstate = sub.add_parser("jail-statewide", help="Search for an individual across all active Ohio county jails and state prisons")
    p_jstate.add_argument("--name", required=True, help="Full name (e.g. Caitlin O'Boyle)")
    p_jstate.add_argument("--json", action="store_true", help="Output as JSON")

    # jail-search
    p_jsearch = sub.add_parser("jail-search", help="Search current county jail inmate roster")
    p_jsearch.add_argument("--name", required=True, help="Name search query")
    p_jsearch.add_argument("--county", "-c", default="cuyahoga_oh", help="Target county (default: cuyahoga_oh)")
    p_jsearch.add_argument("--json", action="store_true", help="Output as JSON")

    # serve
    p_srv = sub.add_parser("serve", help="Run the FastAPI REST server")
    p_srv.add_argument("--host", default="127.0.0.1", help="Host address")
    p_srv.add_argument("--port", type=int, default=8000, help="Port to listen on")

    # db-init
    p_dbinit = sub.add_parser("db-init", help="Initialize SQLite DB schema and import agency registry")

    # db-sync-rosters
    p_dbsync = sub.add_parser("db-sync-rosters", help="Pull live inmate rosters into SQLite historical storage")
    p_dbsync.add_argument("--counties", "-c", default=None, help="Comma-separated county IDs (default: all active)")

    # db-correlate
    p_dbcorr = sub.add_parser("db-correlate", help="Run cross-jurisdiction metadata correlation engine")
    p_dbcorr.add_argument("--name", default=None, help="Filter correlation for specific subject name")
    p_dbcorr.add_argument("--json", action="store_true", help="Output as JSON")

    # db-timeline
    p_dbtl = sub.add_parser("db-timeline", help="Unified cross-county chronological timeline for an individual")
    p_dbtl.add_argument("name", help="Full or partial person name")
    p_dbtl.add_argument("--age", type=int, default=None, help="Filter timeline to inmate with specific age")
    p_dbtl.add_argument("--dob", default=None, help="Filter timeline to inmate with specific date of birth")
    p_dbtl.add_argument("--id", dest="inmate_id", default=None, help="Filter timeline to specific Inmate or Booking ID")
    p_dbtl.add_argument("--json", action="store_true", help="Output as JSON")

    # db-inmate-history
    p_inhist = sub.add_parser("db-inmate-history", help="Query historical inmate custody snapshots by name, age, DOB, ID, or county")
    p_inhist.add_argument("--name", default=None, help="Full or partial inmate name")
    p_inhist.add_argument("--age", type=int, default=None, help="Filter by inmate age")
    p_inhist.add_argument("--dob", default=None, help="Filter by date of birth")
    p_inhist.add_argument("--id", dest="inmate_id", default=None, help="Filter by Inmate ID")
    p_inhist.add_argument("--county", "-c", default=None, help="Filter by county ID")
    p_inhist.add_argument("--limit", type=int, default=50, help="Max records to return (default: 50)")
    p_inhist.add_argument("--json", action="store_true", help="Output as JSON")

    # db-stats
    p_dbstat = sub.add_parser("db-stats", help="Display SQLite historical database metrics and counts")
    p_dbstat.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    client = CuyahogaCourtClient()
    monitor = DocketMonitorEngine(client)
    jail_client = CuyahogaJailClient()
    registry = get_registry()

    if args.command == "counties":
        counties = registry.list_counties()
        if args.json:
            print(json.dumps([c.model_dump() for c in counties], indent=2))
        else:
            rows = []
            for c in counties:
                court_st = "YES" if c.court_service and c.court_service.enabled else "NO"
                jail_st = f"YES ({c.jail_service.feed_type})" if c.jail_service and c.jail_service.enabled else "NO"
                rows.append([c.id, c.name, c.county, court_st, jail_st])
            print_table(rows, ["County ID", "Agency / Court Name", "County", "Court Active?", "Jail Active?"], title="Registered Ohio Jurisdictions")

    elif args.command == "search-name":
        court_adapter = get_court_adapter(args.county)
        if court_adapter and args.county != "cuyahoga_oh":
            if hasattr(court_adapter, "update_cookies") and (args.waf_token or args.session_id):
                new_c = {}
                if args.waf_token: new_c["aws-waf-token"] = args.waf_token
                if args.session_id: new_c["ASP.NET_SessionId"] = args.session_id
                court_adapter.update_cookies(new_c)
            print(f"[*] Searching {getattr(court_adapter, 'court_name', args.county)} for '{args.last}, {args.first}'...")
            cases = court_adapter.search_by_name(last_name=args.last, first_name=args.first)
            if args.json:
                print(json.dumps([c.model_dump() for c in cases], indent=2))
            else:
                if not cases:
                    print("[-] No cases found.")
                else:
                    rows = [
                        [c.case_number, c.title, c.case_type, c.filing_date or "N/A", c.status, c.judge or "N/A"]
                        for c in cases
                    ]
                    print_table(rows, ["Case Number", "Style / Title", "Type", "Filing Date", "Status", "Judge"], title=f"Cases: {getattr(court_adapter, 'court_name', args.county)}")
        else:
            print(f"[*] Searching for defendant: {args.last}, {args.first} (County: {args.county})...")
            results = client.search_criminal_by_name(
                last_name=args.last,
                first_name=args.first,
                dob_year=args.year or "",
                dob_month=args.month or ""
            )
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                if not results:
                    print("No defendants found.")
                else:
                    rows = [
                        [r.get("row_index"), r.get("name"), r.get("dob"), r.get("race"), r.get("sex"), r.get("pending_cases"), r.get("defendant_id")]
                        for r in results
                    ]
                    print_table(rows, ["#", "Defendant Name", "DOB", "Race", "Sex", "Pending?", "Defendant ID"], title="Matching Defendants")
                    print("\n[*] Resolving case history for primary match...")
                    cases = client.get_defendant_cases(0)
                    case_rows = [
                        [c.get("case_number"), c.get("case_status"), c.get("filing_date"), c.get("jail_bail_status")]
                        for c in cases
                    ]
                    print_table(case_rows, ["Case Number", "Status", "Filing Date", "Jail/Bail Status"], title="Case History")

    elif args.command in ["search-case", "summary"]:
        court_adapter = get_court_adapter(args.county)
        case_query = args.case or (f"{args.year}-{args.number}" if (args.year and args.number) else (args.number or args.year or ""))
        if court_adapter and args.county != "cuyahoga_oh":
            if hasattr(court_adapter, "update_cookies") and (args.waf_token or args.session_id):
                new_c = {}
                if args.waf_token: new_c["aws-waf-token"] = args.waf_token
                if args.session_id: new_c["ASP.NET_SessionId"] = args.session_id
                court_adapter.update_cookies(new_c)
            print(f"[*] Searching {getattr(court_adapter, 'court_name', args.county)} for Case '{case_query}'...")
            summary = court_adapter.search_by_case(case_query)
            if args.json:
                print(json.dumps(summary.model_dump() if summary else {}, indent=2))
            else:
                if not summary:
                    print("[-] Case not found.")
                else:
                    print(f"\n=== Case Summary: {summary.case_number} ===")
                    print(f"Title:     {summary.title}")
                    print(f"Court:     {getattr(court_adapter, 'court_name', args.county)}")
                    print(f"Type:      {summary.case_type}")
                    print(f"Status:    {summary.status}")
                    print(f"Judge:     {summary.judge or 'N/A'}")
                    print(f"Filing:    {summary.filing_date or 'N/A'}")
                    if summary.parties:
                        p_rows = [[p.name, p.role] for p in summary.parties]
                        print_table(p_rows, ["Party Name", "Role"], title="Parties")
                    if summary.docket_entries:
                        d_rows = [[d.entry_date or "N/A", d.description] for d in summary.docket_entries]
                        print_table(d_rows, ["Date", "Description"], title="Docket Entries")
        else:
            print(f"[*] Searching for case Year: {args.year}, Number: {args.number} (County: {args.county})...")
            summary = client.search_criminal_by_case(year=args.year or "", number=args.number or "")
            if args.json:
                print(json.dumps(summary, indent=2))
            else:
                if not summary or not summary.get("case_number"):
                    print("[-] Case not found.")
                else:
                    print(f"\n=== Case Summary: {summary.get('case_number')} ===")
                    print(f"Title:     {summary.get('title')}")
                    print(f"Status:    {summary.get('status')}")
                    print(f"Judge:     {summary.get('judge')}")
                    print(f"Next Evt:  {summary.get('next_event')}")
                    print(f"Agency:    {summary.get('arresting_agency')} (Report: {summary.get('arresting_agency_report')})")
                    print(f"Defendant: {summary.get('defendant', {}).get('name')} (Status: {summary.get('defendant', {}).get('status')})")
                    
                    charges = summary.get("charges", [])
                    if charges:
                        c_rows = [[c.get("type"), c.get("statute"), c.get("description"), c.get("disposition")] for c in charges]
                        print_table(c_rows, ["Type", "Statute", "Charge Description", "Disposition"], title="Charges")
                    
                    actions = summary.get("actions", [])
                    if actions:
                        a_rows = [[a.get("event_date"), a.get("event_description")] for a in actions]
                        print_table(a_rows, ["Date", "Event Description"], title="Case Actions")

    elif args.command == "docket":
        court_adapter = get_court_adapter(args.county)
        case_query = args.case or (f"{args.year}-{args.number}" if (args.year and args.number) else (args.number or args.year or ""))
        if court_adapter and args.county != "cuyahoga_oh":
            if hasattr(court_adapter, "update_cookies") and (args.waf_token or args.session_id):
                new_c = {}
                if args.waf_token: new_c["aws-waf-token"] = args.waf_token
                if args.session_id: new_c["ASP.NET_SessionId"] = args.session_id
                court_adapter.update_cookies(new_c)
            print(f"[*] Fetching docket entries for '{case_query}' from {getattr(court_adapter, 'court_name', args.county)}...")
            entries = court_adapter.get_docket(case_query)
            if args.json:
                print(json.dumps([e.model_dump() for e in entries], indent=2))
            else:
                if not entries:
                    print("[-] Docket entries not found.")
                else:
                    rows = [
                        [e.sequence_id or idx + 1, e.entry_date or "N/A", e.docket_type, e.description]
                        for idx, e in enumerate(entries)
                    ]
                    print_table(rows, ["#", "Date", "Type", "Description"], title=f"Docket: {case_query} ({len(entries)} entries)")
        else:
            target_url = args.url or (None if args.year and args.number else DEFAULT_DOCKET_URL)
            print(f"[*] Fetching docket entries (County: {args.county})...")
            docket = client.fetch_docket(docket_url=target_url, year=args.year, number=args.number)
            if args.json:
                print(json.dumps(docket, indent=2))
            else:
                if not docket or not docket.get("entries"):
                    print("[-] Docket not found.")
                else:
                    entries = docket.get("entries", [])
                    rows = [
                        [e.get("proceeding_date"), e.get("filing_date"), e.get("type"), (e.get("description")[:65] + "...") if len(e.get("description", "")) > 68 else e.get("description"), "YES" if e.get("image_url") else "---"]
                        for e in entries
                    ]
                    print_table(rows, ["Proc Date", "Filing Date", "Type", "Description", "Image"], title=f"Docket: {docket.get('case_number')} ({len(entries)} entries)")

    elif args.command == "tyler-session-refresh":
        court_adapter = get_court_adapter(args.county)
        if not court_adapter:
            print(f"[-] No court adapter found for {args.county}")
            sys.exit(1)
        if hasattr(court_adapter, "solve_waf_interactive"):
            ok = court_adapter.solve_waf_interactive(timeout_sec=args.timeout)
            if ok:
                print(f"[+] Successfully refreshed and cached session for {args.county}")
            else:
                print(f"[-] Session refresh failed or timed out for {args.county}")
        else:
            print(f"[-] Adapter for {args.county} does not support interactive WAF solving.")

    elif args.command == "curl":
        court_adapter = get_court_adapter(args.county)
        if court_adapter:
            custom_url = args.url if args.url != DEFAULT_DOCKET_URL else ""
            print(court_adapter.generate_curl_command(custom_url))
        else:
            print(client.generate_curl_command(args.url))


    elif args.command == "watchlist":
        items = monitor.get_watchlist()
        rows = [[i.get("case_number"), i.get("county", "cuyahoga_oh"), i.get("year"), i.get("number"), i.get("label"), i.get("added_at")] for i in items]
        print_table(rows, ["Case Number", "County", "Year", "Number", "Label", "Added At"], title="Monitoring Watchlist")

    elif args.command == "watch-add":
        res = monitor.add_to_watchlist(
            case_number=args.case,
            county=args.county,
            year=args.year,
            number=args.number,
            docket_url=args.url,
            label=args.label
        )
        print(f"[*] Watchlist {res.get('status')}: {args.case} ({args.county})")

    elif args.command == "watch-remove":
        ok = monitor.remove_from_watchlist(args.case, county=args.county)
        if ok:
            print(f"[*] Removed {args.case} from watchlist.")
        else:
            print(f"[-] Case {args.case} not found in watchlist.")

    elif args.command == "monitor-check":
        print("[*] Running monitoring check...")
        if args.case:
            item = next((i for i in monitor.get_watchlist() if i.get("case_number") == args.case), None)
            if not item:
                item = {"case_number": args.case, "county": "cuyahoga_oh"}
            results = [monitor.check_case(item)]
        else:
            results = monitor.check_all()

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            for r in results:
                case_num = r.get("case_number")
                county = r.get("county", "cuyahoga_oh")
                if r.get("error"):
                    print(f"[-] {case_num} ({county}): Error - {r.get('error')}")
                elif r.get("has_new_activity"):
                    print(f"[!] {case_num} ({county}): NEW ACTIVITY DETECTED! ({len(r.get('new_entries', []))} new entries)")
                    for e in r.get("new_entries", []):
                        print(f"    * {e.get('proceeding_date') or e.get('date')} [{e.get('type')}]: {e.get('description')}")
                else:
                    print(f"[✓] {case_num} ({county}): No new activity (Total entries: {r.get('total_entries')})")

    elif args.command == "jail-status":
        print(f"[*] Checking custody for '{args.name}' in {args.county}...")
        adapter = get_jail_adapter(args.county)
        if not adapter:
            print(f"[-] No active jail adapter found for {args.county}")
            sys.exit(1)
        res = adapter.check_custody(args.name)
        if args.json:
            print(json.dumps(res.model_dump(), indent=2))
        else:
            print(f"\nTarget:           {res.queried_name}")
            print(f"In Custody:       {'YES (INMATE FOUND)' if res.is_in_custody else 'NO (NOT CURRENTLY BOOKED)'}")
            print(f"Facility / Jurisdiction: {args.county}")
            print(f"Matches:          {res.total_matches}")
            if res.matches:
                rows = [[m.full_name, m.inmate_id, m.booking_date, m.housing_facility, ", ".join(m.charges[:2])] for m in res.matches]
                print_table(rows, ["Inmate Name", "Inmate ID", "Booking Date", "Facility", "Charges"], title="Inmate Details")

    elif args.command == "jail-statewide":
        print(f"[*] Executing statewide custody search for '{args.name}' across all active Ohio facilities...")
        res = check_custody_statewide(args.name)
        if args.json:
            print(json.dumps(res.model_dump(), indent=2))
        else:
            print(f"\nTarget:           {res.queried_name}")
            print(f"In Custody:       {'YES (INMATE FOUND)' if res.is_in_custody else 'NO (NOT CURRENTLY IN CUSTODY)'}")
            print(f"Queried Systems:  {', '.join(res.queried_counties)}")
            print(f"Total Matches:    {res.total_matches}")
            if res.matches:
                rows = [[m.full_name, m.county, m.inmate_id, m.housing_facility, ", ".join(m.charges[:2])] for m in res.matches]
                print_table(rows, ["Inmate Name", "County", "Inmate ID", "Facility / System", "Charges"], title="Statewide Custody Matches")

    elif args.command == "jail-search":
        print(f"[*] Searching {args.county} jail roster for '{args.name}'...")
        adapter = get_jail_adapter(args.county)
        if not adapter:
            print(f"[-] No active jail adapter found for {args.county}")
            sys.exit(1)
        matches = adapter.search_inmate(args.name)
        if args.json:
            print(json.dumps([m.model_dump() for m in matches], indent=2))
        else:
            print(f"Found {len(matches)} matching inmates in {args.county}.")
            if matches:
                rows = [[m.full_name, m.inmate_id, m.booking_date, ", ".join(m.charges[:2])] for m in matches[:25]]
                print_table(rows, ["Inmate Name", "Inmate ID", "Booking Date", "Charges"], title=f"Matching Inmates: {args.county}")

    elif args.command == "db-init":
        print("[*] Initializing SQLite schema and indexing agency registry...")
        init_db()
        with open("data/agency_registry.json") as f:
            reg_data = json.load(f)
        count = sync_registry_to_db(reg_data)
        print(f"[+] Successfully initialized database and synchronized {count} jurisdictions.")

    elif args.command == "db-sync-rosters":
        target_counties = [c.strip() for c in args.counties.split(",")] if args.counties else None
        counties_list = registry.list_counties()
        print(f"[*] Starting live roster synchronization into SQLite database...")
        total_new = 0
        total_unchanged = 0
        for c in counties_list:
            if target_counties and c.id not in target_counties:
                continue
            if not c.jail_service or not c.jail_service.enabled:
                continue
            adapter = get_jail_adapter(c.id)
            if not adapter:
                continue
            try:
                roster = adapter.fetch_roster()
                new_c, unchanged_c = record_inmates_snapshot(c.id, roster)
                total_new += new_c
                total_unchanged += unchanged_c
                print(f"  [+] {c.id:<15} ({c.name}): {len(roster)} total inmates | {new_c} new/updated | {unchanged_c} unchanged")
            except Exception as e:
                print(f"  [-] {c.id:<15} Failed to sync: {e}")
        print(f"\n[+] Roster sync complete. Total new/updated snapshots: {total_new}, Unchanged: {total_unchanged}")

    elif args.command == "db-correlate":
        print(f"[*] Running multi-jurisdiction entity correlation engine...")
        correlations = run_correlation_engine(args.name)
        if args.json:
            print(json.dumps(correlations, indent=2))
        else:
            print(f"Discovered {len(correlations)} cross-jurisdiction entity correlations:")
            if correlations:
                rows = [
                    [c["subject"], c["jail_county"], c["inmate_id"], c["court_county"], c["case_number"], f"{int(c['confidence']*100)}%"]
                    for c in correlations
                ]
                print_table(rows, ["Subject Name", "Jail County", "Inmate ID", "Court County", "Case Number", "Confidence"], title="Cross-Jurisdiction Correlations")
            else:
                print("No overlapping court cases and jail bookings found yet. Try ingesting more cases and rosters.")

    elif args.command == "db-timeline":
        filter_desc = []
        if args.age is not None:
            filter_desc.append(f"Age={args.age}")
        if args.dob:
            filter_desc.append(f"DOB={args.dob}")
        if args.inmate_id:
            filter_desc.append(f"ID={args.inmate_id}")
        fstr = f" [{', '.join(filter_desc)}]" if filter_desc else ""
        print(f"[*] Compiling historical timeline for '{args.name}'{fstr} across all jurisdictions...")
        timeline_data = get_subject_timeline(
            args.name,
            age=args.age,
            dob=args.dob,
            inmate_id=args.inmate_id
        )
        if args.json:
            print(json.dumps(timeline_data, indent=2))
        else:
            events = timeline_data.get("events", [])
            print(f"Subject: {timeline_data['subject']} (Normalized: {timeline_data['normalized']})")
            if timeline_data.get("multiple_profiles_detected") and not (args.age or args.dob or args.inmate_id):
                print(f"\n[!] NOTICE: Multiple distinct inmate profiles detected matching '{args.name}':")
                for p in timeline_data.get("profiles_detected", []):
                    id_disp = p["inmate_id"] or "NO_ID"
                    age_disp = f"Age: {p['age']}" if p["age"] is not None else "Age: N/A"
                    dob_disp = f"DOB: {p['dob']}" if p["dob"] else "DOB: N/A"
                    print(f"    - ID: {id_disp:<10} | {age_disp:<9} | {dob_disp:<15} | County: {p['county_id']:<15} ({p['record_count']} records)")
                print("    To isolate a specific person's history, re-run with: --age <age> or --id <inmate_id>\n")

            print(f"Total Events Recorded: {timeline_data['total_events']}")
            if events:
                rows = []
                for e in events:
                    etype = e["type"]
                    edate = e["date"]
                    ecounty = e["county"]
                    etitle = e["title"]
                    det = e.get("details", {})
                    ident = det.get("inmate_id") or ""
                    age_dob = f"Age: {det['age']}" if det.get("age") is not None else (f"DOB: {det['dob']}" if det.get("dob") else "")
                    id_tag = f"[{ident} | {age_dob}]" if (ident and age_dob) else (f"[{ident}]" if ident else (f"[{age_dob}]" if age_dob else ""))
                    desc = f"{etitle} {id_tag}".strip()
                    rows.append([edate, ecounty, etype, desc])
                print_table(rows, ["Date", "County", "Event Type", "Event Description"], title=f"Historical Timeline: {args.name}")
            else:
                print("No recorded court or custody events found for this subject matching the criteria.")

    elif args.command == "db-inmate-history":
        print(f"[*] Querying inmate custody history from database...")
        records = get_inmate_history(
            name=args.name,
            age=args.age,
            dob=args.dob,
            inmate_id=args.inmate_id,
            county_id=args.county,
            limit=args.limit
        )
        if args.json:
            print(json.dumps(records, indent=2))
        else:
            print(f"Found {len(records)} custody records matching query.")
            if records:
                rows = []
                for r in records:
                    age_dob = f"Age: {r['age']}" if r.get("age") is not None else (f"DOB: {r['dob']}" if r.get("dob") else "N/A")
                    ch_str = ", ".join(r["charges"][:2]) if r["charges"] else "N/A"
                    rows.append([r["full_name"], r["county_id"], r["inmate_id"] or "N/A", age_dob, r["booking_date"] or "N/A", ch_str])
                print_table(rows, ["Name", "County", "Inmate ID", "Age/DOB", "Booking Date", "Charges"], title="Inmate Custody History")

    elif args.command == "db-stats":
        stats = get_db_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("\n=== Court Monitor Database Analytics ===")
            print(f"Database Path:           {stats['database_file']}")
            print(f"Database File Size:      {stats['file_size_bytes'] / 1024:.1f} KB")
            print(f"Jurisdictions Indexed:   {stats['jurisdictions_count']}")
            print(f"Total Inmate Snapshots:  {stats['total_inmate_records']}")
            print(f"Unique Inmates Tracked:  {stats['unique_inmates_tracked']}")
            print(f"Court Cases Tracked:     {stats['court_cases_tracked']}")
            print(f"Docket Entries Tracked:  {stats['docket_entries_tracked']}")
            print(f"Cross-Entity Matches:    {stats['entity_correlations_count']}")
            print(f"Audit Scan Events:       {stats['audit_scan_events']}")

    elif args.command == "serve":
        import uvicorn
        print(f"[*] Starting Ohio Justice & Custody REST API server at http://{args.host}:{args.port}...")
        uvicorn.run("api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
