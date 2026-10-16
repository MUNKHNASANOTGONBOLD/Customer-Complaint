# Consumer Complaint Early Warning — Credit Cards

Purpose: help a consumer-operations or compliance analyst choose which recurring
credit-card issues to investigate. The main deliverable is a review queue with
transparent evidence, not a ranking of banks by misconduct or customer incidence.

## Start here

Open output/dashboard.html. It includes the loaded data and works locally.
Choose a company, review the queue, and click Review for complaint-level evidence.
Data Health contains coverage and ingestion logs. No web server is required.

## Pipeline

CFPB export API -> immutable changed raw snapshots -> validate -> SQLite upsert
by Complaint ID -> descriptive review signals -> CSVs and interactive dashboard.

Python 3.11+, standard library only, no API key for the tested public endpoint:

```powershell
python pipeline.py backfill
python pipeline.py daily
python pipeline.py export
python -m unittest -v
```

Backfill covers Credit card product records received from 2023, using cached
quarterly exports. This product label was not used in early 2023; correctly
shaped empty exports are retained. Legacy Credit card or prepaid card is excluded.
This is a deliberate product scope, not all financial complaints. Scope is
verified against returned dates and product fields before loading. The live API
includes the maximum calendar date, so raw snapshots may include boundary-day
rows; normalized partitions enforce exclusive end dates locally.

Daily refresh revisits quarters intersecting the most recent 180 days, because
publication and response changes can alter older records. Full backfill with
--refresh retrieves older corrections. Records removed from a later public export
are not automatically deleted from local storage; the pipeline does not claim
to mirror removals. Unknown timeliness remains NULL; it is excluded from the
late-share denominator. Labels are whitespace-trimmed; no company aliases are
fuzzily merged. Schema/required-field failures stop the load rather than silently
discarding records. Snapshot hashes and API URLs record provenance.

Writes are transactional: failed extraction/validation/load cannot partially
change the complaints table. Corrections preserve previous values in revisions.
Dashboard/CSV exports follow the ingestion commit; an export failure may leave
older output files. Rerun export to recover. Exports are not an atomic multi-file
publication. Run only one writer at a time.

## Review rules

Newest 60 receipt-date days are excluded as an explicit publication-lag
sensitivity assumption, not a guarantee of completeness. Compare the preceding
365 days with the previous 365 days. Expected annual count = prior 365-day baseline count.

Rising-volume rule: >=20 recent, >=10 expected, >=1.5 times expected and >=10
excess complaints. Late-response rule: >=30 known recent timeliness flags,
>=3 No flags, and >=10% No among known Yes/No flags. These are assumed review
thresholds, not calibrated statistical tests, regulatory limits or risk scores.
Both signals are independent. Sort by number of signals, excess volume, recent
volume. The analyst must verify evidence before deciding on corrective action.

The daily clock and receipt dates use UTC. Boundary weeks in the trend chart
can be partial. Rule dates and generated-at timestamps are recorded in outputs.
Published timeliness is not resolution duration or satisfaction. Company
response labels record reported responses, not verified outcomes. Examples are
the latest up to 12 records per group, not a random sample or complete evidence.

## Deliverables

- pipeline.py: historical and daily ingestion, validation, transformations.
- data/complaints.sqlite: complaints, revisions, runs, daily_volume and review queue.
- data/raw: exact public API CSV exports and provenance.
- output/dashboard.html: company filter, queue, trends, evidence, Data Health.
- output/complaints.csv: Power BI-ready complaint table.
- output/investigation_queue.csv: review groups and transparent signal measures.
- output/pipeline_runs.csv and quality_summary.json: coverage and run monitoring.
- setup_daily.ps1: Windows Task Scheduler setup for the downloaded local copy.

This is a working HTML dashboard, not a native Power BI .pbix. Power BI can
import the CSVs; unattended Service refresh needs separate gateway/account setup.

## Optional daily local execution

Run setup_daily.ps1 on your Windows machine to register ComplaintSignalsDaily
at 8 a.m. local time. Python must be installed. It runs while you are logged
in, retries failed starts and can wake the computer; powered-off machines do
not execute it. Downloading the ZIP does not install the task.

## Interpretation

CFPB public complaints are not a representative sample of all consumers. Raw
company counts lack customer-base denominators. Publicity, product mix,
submission behavior, seasonality and category revisions can affect comparisons.
Some complaints are not published, and receipt dates differ from publication
dates. Newly received complaints and response updates may be delayed. Narrative
text is not collected by this pipeline. Complaint allegations are not proven
misconduct. Signals support investigation, not causal conclusions or automated
enforcement. No operational savings or reduction in complaints has been measured.

Source and API documentation:
https://www.consumerfinance.gov/data-research/consumer-complaints/
https://cfpb.github.io/api/ccdb/
https://cfpb.github.io/api/ccdb/fields.html
https://cfpb.github.io/ccdb5-api/documentation/
