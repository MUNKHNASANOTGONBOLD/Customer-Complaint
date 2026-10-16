# CFPB → Google Sheets → Tableau Public

The native Google Sheet is created and verified: both aggregate totals equal 261,392 and date cells are populated. Local service-account authorization, Windows scheduling and Tableau publishing remain to be completed.

## 1. Open the existing native Google Sheet
https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID

Title: Consumer Complaint Early Warning — Dashboard Feed. Keep the five tab names and stable file ID. Do not import another copy. config.json already contains this file ID. This workbook is a machine-readable reporting feed; do not manually edit its managed tabs.

## 2. Authorize unattended Python writes locally
The ChatGPT Google Drive connection creates the initial file; it does NOT give a downloaded Windows Python process reusable credentials.
1. In Google Cloud Console create/select a project and enable Google Sheets API.
2. Create a service account for the complaint pipeline. No broad project role is needed solely to edit a shared sheet.
3. Generate its JSON key and save locally as service-account.json next to upload_sheets.py. Do not send the key in chat, commit it, or include it in ZIPs.
4. Share ONLY the dedicated Google Sheet with that service account's client_email as Editor. The file can otherwise remain private; Tableau uses your Google login.
5. config.json already has the correct spreadsheet ID. Keep the local key-file path service-account.json, or update it if you chose a different filename.
6. Open PowerShell in this extracted folder. Run:

    python -m pip install -r requirements.txt
    python upload_sheets.py

Upload uses hidden staging tabs and a single atomic commit for the managed tables, preserving the visible tab IDs. Failure before commit leaves the previous visible snapshot. Inspect upload_runs.jsonl; after a lost response, rerun to clean staging and republish. One writer only. Large dates/timestamps are numeric sheet values with date formatting refreshed on every upload, including newly added rows.

## 3. Build a Google-Sheets-only public workbook
In Tableau Public: File > New > Connect > More > Google Drive. Sign into the SAME account, choose the native Google Sheet. Add Signals, Monthly, ReviewTrend and Quality as SEPARATE data sources, not physical joins. Use the current official Google Drive connector; the old Google Sheets connector is deprecated.

Signals: one company/issue group. Monthly: one month/company/issue. ReviewTrend: one week/issue, ALL companies. Quality: one global row. Sources is provenance. Keep these grains separate. Never COUNTD company or count source rows to estimate complaints; SUM the complaint counts.

Create in Signals:
- Total Complaints: SUM([total_complaints])
- Recent Complaints: SUM([recent])
- Review Candidates: SUM(IF [signal_count] > 0 THEN 1 ELSE 0 END)
- Rising Groups: SUM(IF [volume_signal] THEN 1 ELSE 0 END)
- Late Groups: SUM(IF [late_signal] THEN 1 ELSE 0 END)
- Recent Late Rate: IF SUM([known]) > 0 THEN SUM([late])/SUM([known]) END
Format Recent Late Rate as percentage. volume_ratio is a multiple, not a percent. Filter queue sheet signal_count > 0; do not put that filter on the KPI sheets or total count shrinks.

Early Warning dashboard: KPI sheets above a queue table of company, issue, recent, expected_complaints, volume_ratio, excess, late, known; sort excess descending. Company and issue controls can filter Signals and Monthly after explicitly mapping the matching fields through Tableau relationships for filtering and validating the controls. The monthly line uses month vs SUM(complaints); it responds to both company and issue. ReviewTrend is labelled ALL COMPANIES and only responds to issue, never company. Put it on a separate Trends page if that distinction is confusing.

Data Health: Quality records/coverage/built_at and review window dates. These stay global. Display data age using built_at. No raw complaints or state/channel drill-through in the auto-refresh workbook. The 261,392 complaint-level CSV remains available locally for separate exploration.

Initial checks: Total Complaints 261,392; 104 Review Candidates; 91 Rising Groups; 14 Late Groups. Some groups have both signals. Annual Recent Complaints: 95605. Monthly complaints sum to the full-history total. After refresh use Quality for new expected totals.

## 4. Enable Tableau Public daily refresh
Publish/save to Tableau Public. Select Keep my data in sync with the data source using saved credentials when offered. Confirm Google Drive credentials are saved and request a data refresh on the public workbook once. Verify the published Quality built_at and counts match the Google Sheet. Tableau schedules Sheets refresh approximately every 24 hours, in its assigned window; this is not real time or a guaranteed 08:00 update. Verify next-day refresh before calling the full workflow validated. Keep the workbook connected ONLY to Sheets, not a local CSV mixed into the same publication.

## 5. Daily execution
The ZIP contains complaint-early-warning with the existing loaded SQLite database.
Run once manually:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\run_daily.ps1

The command runs ingestion → aggregation → Sheets upload and stops at any failure. Once it succeeds, run setup_daily.ps1 to register ComplaintSheetsDaily for 08:00 local time while logged in. Disable any older ComplaintSignalsDaily or ComplaintTableauDaily task first so only one ingestion task writes the database. Computer, internet and Google credentials must remain available. This schedules the Windows pipeline, not the Tableau platform's assigned refresh time.

## Method and limits
Recent 365 receipt-date days vs prior 365, newest 60 days excluded as an assumption. Flags are review prompts, not misconduct findings. Missing timeliness excluded from denominator; do not average group rates. Public complaints lack customer-base denominators. Modern Credit card category only. Source revisions and publication lags can change counts. See complaint-early-warning/README.md for ingestion/removal limits. No tested live Google upload or Tableau end-to-end refresh has occurred before account authorization.

Official documentation:
https://help.tableau.com/current/pro/desktop/en-us/public_faq.htm
https://help.tableau.com/current/pro/desktop/en-us/examples_googledrive.htm
https://developers.google.com/workspace/sheets/api/guides/batch

## Tableau design target
Executive Overview: charcoal sidebar (#333536), beige dashboard (#C9BDAB), cream cards (#ECE5DB), orange accent (#FF9E37). Fixed size 1300 x 850. Company filter includes all 830 companies; restrict only chart rankings to Top 10. KPI sheets: Full-history Total Complaints, Annual Recent Complaints, Review Candidates, Rising Groups, Late Flags. Review window is 365 days and baseline is the preceding 365 days. Heuristic signal thresholds remain recent>=20, expected>=10, ratio>=1.5, excess>=10; timeliness known>=30, late>=3, late rate>=10%. These are review thresholds, not calibrated annual statistical tests.

Refresh Tableau metadata after the update. expected_28d was renamed expected_complaints; repair any formula referring to the old field. Existing Total Complaints and Signal Count fields retain their names.
