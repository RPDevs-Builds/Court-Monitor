# Justice & Custody Systems: Master Vendor Registry

Authoritative reference catalog of software vendors, platform architectures, session mechanics, and integration strategies reversed and integrated by the Ohio Justice & Custody Monitor. This registry serves as the blueprint for expanding cross-county and nationwide to other states.

---

## 1. OCV, LLC (TheSheriffApp Platform)

* **Vendor Profile**: OCV, LLC (Auburn, AL) — The dominant white-label mobile app and citizen engagement vendor for US law enforcement.
* **National Footprint**: Hundreds of Sheriff Offices and Police Departments across AL, FL, GA, IL, IN, NC, OH, SC, TN, TX, and more.
* **Architecture Pattern**: Multi-Tenant AWS S3 / CloudFront CDN + AWS API Gateway Serverless Microservices.
* **Tenant Identification**: Predictable incrementing `appID` (e.g. `a26544113` for Cuyahoga County, OH).
* **Data Transport**: Clean, unauthenticated public JSON feeds.
* **Key Endpoint Schemas**:
  * **Direct S3 Inmate Roster (JMS)**: `https://myocv.s3.us-east-1.amazonaws.com/ocvapps/{appID}/{County}inmates.json`
  * **RTJB Inmate Feed Gateway**: `https://apps.myocv.com/feed/rtjb/{appID}/Inmates`
  * **Master App Config Manifest**: `https://cdn.myocv.com/ocvapps/{appID}/public/int_manifestMenuNew.json`
  * **Sex Offender Database**: `https://cdn.myocv.com/ocvapps/{appID}/sexOffenders.json`
  * **Sheriff News Feed**: `https://cdn.myocv.com/ocvapps/{appID}/public/blog_sheriffNews.json`
* **Authentication**: None required. Open public S3/CDN distribution.
* **Caching Strategy**: Respects HTTP `ETag` and `If-None-Match` for bandwidth-efficient change polling.
* **Expansion Readiness**: **Extremely High**. Identifying an agency's `appID` on Google Play / App Store immediately unlocks that agency's complete app manifest and jail roster nationwide without custom scraping.

---

## 2. Microsoft ASP.NET WebForms + F5 BIG-IP ASM (Cuyahoga County Court)

* **Vendor / Stack**: Custom Microsoft IIS / ASP.NET WebForms 4.0 fronted by F5 BIG-IP Application Security Manager (ASM).
* **Footprint**: Cuyahoga County Court of Common Pleas (`cpdocket.cp.cuyahogacounty.gov`). Widely deployed in legacy US county court IT infrastructures.
* **Architecture Pattern**: Monolithic server-side rendered WebForms with heavy `__VIEWSTATE`, `__EVENTVALIDATION`, and hidden form state.
* **Security & Session Mechanics**:
  * Mandatory Terms of Service gate (`btnYes` on `/` or `/TOS.aspx`).
  * F5 ASM Cookie (`TS01ef00af`) + ASP.NET Session Cookie (`ASP.NET_SessionId`).
  * Strict session timeout (20 minutes of inactivity redirects to `/Unavailable.aspx`).
* **Integration Strategy**: Headless Chromium session management via `agent-browser` daemon with auto-TOS submission, cookie extraction, and dynamic `curl` command synthesis.
* **Expansion Readiness**: Medium. Requires headless browser orchestration or strict cookie + ViewState preservation for POST postbacks.

---

## 3. High-Frequency PDF Inmate Publishing (Summit County Sheriff / EyeMG)

* **Vendor / Stack**: EyeMG Web Platform + Automated Jail Management Export (Summit County Sheriff, Akron, OH).
* **Footprint**: Summit County (`sheriff.summitoh.net`) and municipal agencies using automated document publishing systems.
* **Architecture Pattern**: Automated cron pipeline that compiles the jail's live JMS database into an official PDF document (`activeoffenderreport.pdf`) updated several times daily.
* **Integration Strategy**:
  * Stream PDF via HTTP GET.
  * Ingest and transform into high-fidelity plaintext via `/usr/bin/pdftotext`.
  * Regex extraction of tabular fields: Inmate ID, Full Name, DOB, Race, Sex, and ORC criminal statutes.
* **Authentication**: None. Public static file serving.
* **Expansion Readiness**: High for agencies that publish daily PDF/CSV jail rosters instead of interactive web forms.

---

## 4. State Department of Corrections Portals (ODRC Offender Search)

* **Vendor / Stack**: Microsoft ASP.NET MVC 5.2 / IIS 8.5 (Ohio Department of Rehabilitation and Correction).
* **Footprint**: State of Ohio (`appgateway.drc.ohio.gov`). Structurally representative of state DOC search systems across all 50 US states.
* **Architecture Pattern**: Two-step CSRF-protected form workflow.
  * Initial GET request to `/OffenderSearch/Search/Search` establishes session and provides `__RequestVerificationToken`.
  * POST request to `/OffenderSearch/Search/SearchResults` executes query.
* **Data Schema**: HTML table containing photo URL, full name, state offender number, DOB, custody status (`INCARCERATED`, `RELEASED`, `PAROLE`), and offense list.
* **Expansion Readiness**: High. Statewide DOC portals across states (e.g. CDCR in California, TDCJ in Texas, FDOC in Florida) follow nearly identical session + POST query patterns.

---

## 5. Tyler Technologies (Odyssey / CourtView / eServices)

* **Vendor Profile**: Tyler Technologies (Plano, TX) — The largest court management software vendor in the United States.
* **National Footprint**: Hundreds of county and state court systems across TX, CA, OH, FL, IN, MN, WA, etc.
* **Ohio Deployments**: Lorain County Court of Common Pleas (`coc.loraincountyohio.gov/eservices/`), Lake County, and numerous municipal courts.
* **Architecture Pattern**: Tyler Odyssey eServices / Portal with standardized REST/JSON APIs or server-side paginated tables.
* **Expansion Readiness**: High. Once an Odyssey adapter is built, it can be ported with minimal changes across dozens of jurisdictions nationwide.

---

## 6. IBM WebSphere / Java EE Servlet Architecture (Franklin County CIO)

* **Vendor / Stack**: IBM WebSphere Application Server / Java EE Servlet 3.1 (`co.franklin.oh.us`).
* **Footprint**: Franklin County Court of Common Pleas & Municipal Court (Columbus, OH).
* **Architecture Pattern**: Multi-step session flow with dynamic session identifier URLs (`acceptDisclaimer?-session_id`), hidden field state flags (`setField=1` for name, `setField=2` for case), and dedicated servlet action targets (`nameSearch`, `caseSearch`).
* **Expansion Readiness**: Medium. Standard Java EE court portal pattern used by large metropolitan jurisdictions.

---

## Vendor Capability Matrix

| Vendor / Platform | Scope | Primary Data | Transport | Auth Required | National Footprint |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **OCV (TheSheriffApp)** | Jail / Sheriff | Live Roster, Mugshots, Charges | S3 JSON / RTJB Feed | ❌ None | **Hundreds of Counties** |
| **ASP.NET WebForms + F5** | Court Docket | Criminal, Civil, Appellate Dockets | HTML POST / ViewState | ❌ (Cookie/TOS only) | Widespread County Courts |
| **PDF Headcount Reports** | Jail / Sheriff | Tabular Inmate Rosters | Static PDF Stream | ❌ None | Moderate Regional |
| **State DOC (ODRC)** | Prison / Parole | Statewide Incarceration & APA | ASP.NET MVC Form | ❌ (CSRF Token only) | **All 50 States** |
| **Tyler Odyssey** | Court Docket | Full Court Records & Dockets | eServices / Portal | ❌ (Public Search) | **Market Leader Nationwide** |
| **IBM WebSphere / Java** | Court Docket | Common Pleas & Municipal Dockets | Java Servlet POST | ❌ (Session Cookie) | Large Metro Counties |
