# Consumer Complaint Early Warning — Tableau Public project

## Purpose
Help complaint operations prioritize company/issue groups for investigation based on rising published complaint volume and repeated late-response flags. Modern Credit card category only. Review flags are not findings of misconduct or customer incidence rankings.

This is a working Python/SQLite pipeline plus a Tableau build kit. No finished .twb/.twbx is included. Native worksheets and dashboards must be assembled and checked in Tableau Desktop Public Edition.

## 1. Extract and connect — first session
1. Extract the ZIP to a stable folder, such as C:\Projects. Locate the folder containing pipeline.py.
2. Open Tableau Desktop Public Edition. File > New.
3. Connect > To a File > Text file. Select tableau_data/complaints.csv.
4. Name the data source Complaints. Keep complaint_id as String; received_date and sent_date as Date; is_recent/is_baseline/is_review_period as whole numbers.
5. Data > New Data Source > Text file: add tableau_data/investigation_queue.csv. Name it Signals. company/issue are String; signal_count/recent/baseline/known/late are whole numbers; expected_28d/volume_ratio/excess are decimal; volume_signal/late_signal are Boolean.
6. Add quality.csv as Quality and pipeline_runs.csv as Runs, each as a separate data source.
7. Do NOT physically join Signals to Complaints: one row is a company/issue group, the other a complaint. Joining multiplies the signal metrics.
8. Create the fields in TABLEAU_CALCULATIONS.txt one at a time, in the specified source. Nothing needs to be downloaded again to start.

## 2. Dashboard: Early Warning (1200 x 800)
Use a white canvas, dark navy #142D4E headings, teal #178C88 for normal metrics and amber #D98D24 for review flags. Use 10–11 pt labels and 24–28 pt KPI numbers.

- Title: Consumer Complaint Early Warning. Subtitle: Credit cards | published complaints | review flags, not proven misconduct.
- Top: KPI sheets Recent Complaints (Complaints), Review Candidates (Signals), Rising Groups (Signals), Recent Late Response Rate (Complaints). Put recent late and known counts beside the rate.
- Queue sheet (Signals): company and issue on Rows; Measure Names on Columns; Measure Values on Text. Include recent, expected_28d, volume_ratio, excess, late, known, Late Response Share. Filter signal_count > 0; sort excess descending. Put Review Reason on Color or Tooltip. Format expected/excess to one decimal; volume_ratio to two decimals.
- Weekly trend (Complaints): Week on Columns, Review Trend Count on Rows, Line marks. Filter is_review_period = 1. Review boundaries may leave partial weeks.
- Top issues (Complaints): issue on Rows, Recent Complaints on Columns; descending bars, Top 5 by Recent Complaints.
- Use company and issue filters. For each filter use Apply to Worksheets > All Using Related Data Sources only after mapping the equivalent company/issue fields via Data > Edit Relationships. These filter-only relationships are not physical joins. Test both sources; if filters do not propagate, use separate clearly labelled source filters until validated.
- Do not add state/date/channel controls to this dashboard: the upstream Signals queue uses a fixed evaluation window. State/date/channel filters belong only on Explorer.

## 3. Dashboard: Complaint Explorer
- Use Complaints only. Add company, issue, received_date, state and channel filters.
- KPI sheets: Complaint Count, Known Responses, Late Responses, Late Response Rate.
- Monthly line: Month vs Complaint Count.
- Evidence text table: complaint_id, received_date, company, issue, sub_issue, state, response, timely.
- Add a dashboard filter action from the Early Warning queue to Explorer evidence sheets: Selected Fields company->company and issue->issue. On clearing selection choose Show all values. Add a navigation button to Explorer; test the selected company and issue are carried through. If the action cannot cross dashboards in your version, add a small evidence table to Early Warning and apply the action there, then use explicit Explorer filters.
- Set the receipt-date filter to the recent_start/recent_end values in quality.csv when checking a signal. Without it, Explorer intentionally shows all history.

## 4. Dashboard: Data Health
Use Quality for global records, date coverage, built_at, window dates, excluded_newest_days and review counts. Use Runs for ingestion status/history. Do not apply complaint company/issue filters here.
Show rule text: preceding 28 days compared with previous 84 days; expected = baseline / 3. Newest 60 receipt-date days excluded as a sensitivity assumption, not guaranteed completeness. Volume flag: recent >=20, expected >=10, multiple >=1.5, excess >=10. Late flag: known >=30, late >=3 and late share >=10%. Unknown response flags excluded from denominator.

## 5. Snapshot checks before publishing
Clear all filters. Included snapshot (2026-10-10):
- Complaint Count: 261,392
- Review Candidates: 6
- Rising Groups: 5
- Late Response Groups: 1
- Recent period: July 15–August 11, 2026
- Baseline: April 22–July 14, 2026
- CAPITAL ONE FINANCIAL CORPORATION / Fees or interest: recent 119, baseline 220, expected 73.33, multiple 1.623, late 0, known 119.
After future runs use tableau_data/quality.csv for the current counts and windows. Validate calculations, filters, action selections and extract refresh in Desktop; this environment cannot execute Tableau.

## 6. Publish
Save the workbook locally. Use Server > Tableau Public > Save to Tableau Public (menu wording varies by edition), sign into Tableau Public, and name it Consumer Complaint Early Warning. Share the resulting URL or embed it in your portfolio. Public workbooks/data are accessible to everyone; this kit contains public CFPB data and no complaint narratives.

## 7. Daily data update versus public dashboard update
Open PowerShell in the folder containing pipeline.py:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\refresh_tableau.ps1

This runs pipeline.py daily, then prepare_tableau.py ONLY after success. The data files are replaced at the same paths. Do not refresh Tableau during export preparation.
Then in Tableau refresh the data sources/extracts and save to Tableau Public again. This republishes the current data. CSV-based Tableau Public workbooks do NOT automatically refresh from your computer.

Optional local daily task: run setup_tableau_daily.ps1. It schedules the data pipeline/export preparation for 08:00 local time while logged in. Do not also install the older setup_daily.ps1 task; if already installed, disable ComplaintSignalsDaily before enabling ComplaintTableauDaily to avoid concurrent writers. Powered-off computers cannot run it. This does not schedule public workbook publishing.

## Limits
Public complaint reporting and publication effects differ by company. No customer-base denominator. Labels are not consolidated corporate entities. Timeliness is not resolution duration or satisfaction. Raw counts are not bank-quality rankings. Review thresholds are assumptions. Removal of records from later exports is not mirrored automatically; see README.md. No savings or complaint reduction have been measured.

## Official references
https://help.tableau.com/current/pro/desktop/en-us/public_faq.htm
https://help.tableau.com/current/pro/desktop/en-us/publish_workbooks_tableaupublic.htm
https://help.tableau.com/current/pro/desktop/en-us/refreshing_data.htm
https://www.consumerfinance.gov/data-research/consumer-complaints/
