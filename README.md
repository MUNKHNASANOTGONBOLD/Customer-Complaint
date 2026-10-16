# Consumer Complaint Early Warning

CFPB public credit-card complaints → Python / SQLite → Google Sheets → Tableau.

Recovered original project source, including ingestion, review rules, dashboard,
Tableau preparation, Windows scheduling and Google Sheets upload scripts.
Raw data, generated exports, local configuration and credentials are excluded.

## Run locally

Requires Python 3.11 or later. From this repository root:

```powershell
python -m pip install -r requirements.txt
python complaint-early-warning/pipeline.py backfill
python prepare_sheets.py
```

The initial backfill contacts the public CFPB endpoint. This endpoint does not
require an API key. Open `complaint-early-warning/output/dashboard.html` after
successful processing.

## Google Sheets authentication

Copy `config.example.json` to `config.json`. Set your own spreadsheet ID and
service-account file path. Keep the service-account JSON outside the repository,
or use the ignored `service-account.json` filename. Enable the Google Sheets API
and share your target spreadsheet with that service account.

Create tabs named Signals, Monthly, ReviewTrend, Quality and Sources before the
first upload. Then run `python upload_sheets.py`. This replaces values in those
managed tabs. For scheduling details see START_HERE.md and setup_daily.ps1.
Tableau Public refresh and republication are a separate manual step.

Never commit API keys, OAuth tokens, service-account JSON or local config.json.
The committed config.example.json contains placeholders only.

## Validation

```powershell
cd complaint-early-warning
python -m unittest -v
```

See complaint-early-warning/README.md for data scope, review thresholds,
publication lag assumptions and interpretation limits. Review signals are
investigation candidates, not findings of misconduct.

[Tableau portfolio](https://public.tableau.com/app/profile/munkhnasan.otgonbold/vizzes)
