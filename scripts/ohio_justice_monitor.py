#!/usr/bin/env python3
"""
Ohio Justice & Custody Monitor CLI
Unified multi-county command line tool for searching court dockets, inspecting case charges,
monitoring activity across Ohio counties, and checking statewide jail/prison custody status.
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
from adapters.court import get_court_adapter

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
    p_name.add_argument("--county", "-c", default="cuyahoga_oh", help="Target county (default: cuyahoga_oh)")
    p_name.add_argument("--json", action="store_true", help="Output as JSON")

    # search-case
    p_case = sub.add_parser("search-case", help="Search case by year and number")
    p_case.add_argument("--year", required=True, help="Case Year (e.g. 2026)")
    p_case.add_argument("--number", required=True, help="Case Number (e.g. 711470)")
    p_case.add_argument("--county", "-c", default="cuyahoga_oh", help="Target county (default: cuyahoga_oh)")
    p_case.add_argument("--json", action="store_true", help="Output as JSON")

    # summary
    p_sum = sub.add_parser("summary", help="Fetch case summary, charges, actions")
    p_sum.add_argument("--year", required=True, help="Case Year")
    p_sum.add_argument("--number", required=True, help="Case Number")
    p_sum.add_argument("--county", "-c", default="cuyahoga_oh", help="Target county (default: cuyahoga_oh)")
    p_sum.add_argument("--json", action="store_true", help="Output as JSON")

    # docket
    p_doc = sub.add_parser("docket", help="Fetch complete case docket")
    p_doc.add_argument("--url", default=None, help="Direct docket URL with token q")
    p_doc.add_argument("--year", default=None, help="Case Year")
    p_doc.add_argument("--number", default=None, help="Case Number")
    p_doc.add_argument("--county", "-c", default="cuyahoga_oh", help="Target county (default: cuyahoga_oh)")
    p_doc.add_argument("--json", action="store_true", help="Output as JSON")

    # curl
    p_curl = sub.add_parser("curl", help="Generate live, valid curl command with active cookies")
    p_curl.add_argument("--url", default=DEFAULT_DOCKET_URL, help="Target court URL")

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
        print(f"[*] Searching for defendant: {args.last}, {args.first} (County: {args.county})...")
        results = client.search_criminal_by_name(
            last_name=args.last,
            first_name=args.first,
            dob_year=args.year,
            dob_month=args.month
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
        print(f"[*] Searching for case Year: {args.year}, Number: {args.number} (County: {args.county})...")
        summary = client.search_criminal_by_case(year=args.year, number=args.number)
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

    elif args.command == "curl":
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

    elif args.command == "serve":
        import uvicorn
        print(f"[*] Starting Ohio Justice & Custody REST API server at http://{args.host}:{args.port}...")
        uvicorn.run("api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
