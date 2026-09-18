#!/usr/bin/env python3
"""
Cuyahoga County Common Pleas Court Docket Monitor
Monitors case docket activity, detects new entries, and generates live curl commands.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_CASE_URL = "https://cpdocket.cp.cuyahogacounty.gov/CR_CaseInformation_Docket.aspx?q=hRRTYX-BnjfUgnoAk-HSrQ00n6DjqAxFUzIxKeQ1ac41"
DEFAULT_CASE_NUM = "CR-26-711470-A"
BASE_URL = "https://cpdocket.cp.cuyahogacounty.gov"
DATA_DIR = Path(__file__).resolve().parent / "data"

def run_agent_browser(args, timeout=25):
    env = os.environ.copy()
    env["AGENT_BROWSER_EXECUTABLE_PATH"] = "/usr/bin/chromium"
    cmd = ["agent-browser"] + args
    try:
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
        return res.stdout.strip(), res.stderr.strip(), res.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1

def ensure_session():
    """Ensure the user session has accepted the Terms of Service."""
    out, _, _ = run_agent_browser(["open", f"{BASE_URL}/"])
    run_agent_browser(["wait", "1000"])
    check_js = "document.querySelector('#SheetContentPlaceHolder_btnYes') ? 'tos' : 'ok'"
    status, _, _ = run_agent_browser(["eval", check_js])
    if "tos" in status:
        print("[*] Accepting Terms of Service...")
        run_agent_browser(["eval", "document.querySelector('#SheetContentPlaceHolder_btnYes').click()"])
        run_agent_browser(["wait", "2000"])
    return True

def get_live_cookies():
    """Get cookie string from the active session."""
    ensure_session()
    stdout, _, _ = run_agent_browser(["cookies", "get"])
    cookies = []
    for line in stdout.strip().splitlines():
        if "=" in line:
            cookies.append(line.strip())
    return "; ".join(cookies)

def extract_docket_from_page():
    """Extract docket table from current open page in browser."""
    js_extract = """
    (() => {
        const table = document.querySelector('#SheetContentPlaceHolder_caseDocket_gvDocketInformation');
        if (!table) return null;
        const caseHeader = document.querySelector('#SheetContentPlaceHolder_caseHeader_lblCaseNumHeader')?.innerText || '';
        const caseTitle = document.querySelector('#SheetContentPlaceHolder_caseHeader_lblCaseTitleHeader')?.innerText || '';
        const rows = Array.from(table.querySelectorAll('tr')).slice(1);
        const entries = rows.map(r => {
            const cells = Array.from(r.querySelectorAll('td')).map(c => c.innerText.trim());
            const img = r.querySelector('a[title="View Docket Image"]');
            return {
                proceeding_date: cells[0] || '',
                filing_date: cells[1] || '',
                party: cells[2] || '',
                type: cells[3] || '',
                description: cells[4] || '',
                image_url: img ? img.href : null
            };
        });
        return {
            case_number: caseHeader,
            title: caseTitle,
            entries: entries,
            url: window.location.href
        };
    })()
    """
    out, _, rc = run_agent_browser(["eval", js_extract])
    if rc != 0 or not out or out == "null":
        return None
    try:
        return json.loads(out)
    except Exception as e:
        print(f"[-] Error parsing JSON: {e}, raw: {out}")
        return None

def fetch_by_url(docket_url):
    """Navigate to a docket URL directly."""
    ensure_session()
    print(f"[*] Loading docket URL: {docket_url}")
    run_agent_browser(["open", docket_url])
    run_agent_browser(["wait", "2000"])
    return extract_docket_from_page()

def fetch_by_case_number(year, number):
    """Open Search.aspx, search by Year & Case Number, and navigate to Docket."""
    ensure_session()
    print(f"[*] Searching for case Year: {year}, Number: {number}...")
    run_agent_browser(["open", f"{BASE_URL}/Search.aspx"])
    run_agent_browser(["wait", "1500"])
    
    # Click Criminal Search by Case
    run_agent_browser(["eval", "document.querySelector('#SheetContentPlaceHolder_rbCrCase').click()"])
    run_agent_browser(["wait", "2000"])

    # Fill year & number
    js_fill = f"""
    (() => {{
        const yr = document.querySelector('#SheetContentPlaceHolder_criminalCaseSearch_ddlYear');
        if (yr) {{ yr.value = '{year}'; yr.dispatchEvent(new Event('change', {{ bubbles: true }})); }}
        const num = document.querySelector('#SheetContentPlaceHolder_criminalCaseSearch_txtCaseNumber');
        if (num) {{ num.value = '{number}'; num.dispatchEvent(new Event('input', {{ bubbles: true }})); }}
        const btn = document.querySelector('#SheetContentPlaceHolder_criminalCaseSearch_btnSubmitCase');
        if (btn) btn.click();
    }})()
    """
    run_agent_browser(["eval", js_fill])
    run_agent_browser(["wait", "2500"])

    # On summary page, click Docket link
    run_agent_browser(["eval", "document.querySelector('#SheetContentPlaceHolder_caseHeader_lbDocket')?.click()"])
    run_agent_browser(["wait", "2500"])

    return extract_docket_from_page()

def load_previous_data(case_num):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = DATA_DIR / f"{case_num}.json"
    if cache_file.exists():
        with open(cache_file, "r") as f:
            return json.load(f)
    return None

def save_current_data(case_num, data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = DATA_DIR / f"{case_num}.json"
    data["last_checked"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[+] Saved snapshot to {cache_file}")

def print_entries_table(entries, title="Docket Entries", highlight_count=0):
    print(f"\n=== {title} ({len(entries)} items) ===")
    header = f"{'Proc Date':<12} {'Filed':<12} {'Type':<6} {'Description':<65} {'Doc Image'}"
    print(header)
    print("-" * len(header))
    for idx, e in enumerate(entries):
        prefix = ">> [NEW] " if idx < highlight_count else "   "
        p_date = e.get('proceeding_date', '')
        f_date = e.get('filing_date', '')
        e_type = e.get('type', '')
        desc = (e.get('description', '')[:62] + '...') if len(e.get('description', '')) > 65 else e.get('description', '')
        has_img = "YES" if e.get('image_url') else "---"
        line = f"{prefix}{p_date:<10} {f_date:<10} {e_type:<6} {desc:<65} {has_img}"
        print(line)

def monitor_case(docket_url=None, case_year=None, case_num=None):
    if docket_url:
        data = fetch_by_url(docket_url)
    elif case_year and case_num:
        data = fetch_by_case_number(case_year, case_num)
    else:
        data = fetch_by_url(DEFAULT_CASE_URL)

    if not data or not data.get("entries"):
        print("[-] Failed to retrieve docket entries.")
        return

    case_number = data.get("case_number") or DEFAULT_CASE_NUM
    case_title = data.get("title", "")
    current_entries = data.get("entries", [])
    print(f"\n[+] Case: {case_number} | {case_title}")
    print(f"[+] URL:  {data.get('url')}")
    print(f"[+] Total entries found: {len(current_entries)}")

    # Check against cache
    cached = load_previous_data(case_number)
    if cached:
        cached_entries = cached.get("entries", [])
        # Build signatures for comparison
        cached_sigs = set(f"{e.get('filing_date')}|{e.get('type')}|{e.get('description')}" for e in cached_entries)
        new_entries = []
        for e in current_entries:
            sig = f"{e.get('filing_date')}|{e.get('type')}|{e.get('description')}"
            if sig not in cached_sigs:
                new_entries.append(e)

        if new_entries:
            print(f"\n🚨 ALERT: {len(new_entries)} NEW DOCKET ACTIVITY DETECTED!")
            print_entries_table(new_entries, title="New Activity Detected", highlight_count=len(new_entries))
        else:
            print("\n[✓] No new activity since last check.")
            print(f"[✓] Last check was: {cached.get('last_checked')}")
            print(f"[✓] Latest docket event: [{current_entries[0]['filing_date']}] {current_entries[0]['type']} - {current_entries[0]['description'][:70]}...")
    else:
        print("\n[*] Initial baseline established.")
        print_entries_table(current_entries[:10], title="Latest 10 Docket Entries")

    save_current_data(case_number, data)

def generate_curl_command(docket_url=DEFAULT_CASE_URL):
    cookies = get_live_cookies()
    print("\n# Copy and run this command in your terminal:")
    print(f"""curl -s '{docket_url}' \\
  -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0' \\
  -H 'Cookie: {cookies}'""")

def main():
    parser = argparse.ArgumentParser(description="Cuyahoga County Court Docket Monitor")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # check
    p_check = subparsers.add_parser("check", help="Check docket for activity")
    p_check.add_argument("--url", default=None, help="Direct docket URL")
    p_check.add_argument("--year", default=None, help="Case year (e.g. 2026)")
    p_check.add_argument("--number", default=None, help="Case number (e.g. 711470)")

    # curl
    p_curl = subparsers.add_parser("curl", help="Generate live curl command with fresh session cookies")
    p_curl.add_argument("--url", default=DEFAULT_CASE_URL, help="URL to curl")

    # history
    p_hist = subparsers.add_parser("history", help="Show saved docket history")
    p_hist.add_argument("--case", default=DEFAULT_CASE_NUM, help="Case number to view")

    args = parser.parse_args()

    if args.command == "curl":
        generate_curl_command(args.url)
    elif args.command == "history":
        data = load_previous_data(args.case)
        if data:
            print(f"Case: {data.get('case_number')} | {data.get('title')}")
            print(f"Last Checked: {data.get('last_checked')}")
            print_entries_table(data.get("entries", []), title="Cached Docket Entries")
        else:
            print(f"No cache found for {args.case}")
    else:
        url = getattr(args, "url", None)
        year = getattr(args, "year", None)
        number = getattr(args, "number", None)
        monitor_case(docket_url=url, case_year=year, case_num=number)

if __name__ == "__main__":
    main()
