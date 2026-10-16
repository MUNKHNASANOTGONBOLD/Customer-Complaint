$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
 python .\complaint-early-warning\pipeline.py daily
 if ($LASTEXITCODE -ne 0) { throw 'CFPB pipeline failed.' }
 python .\prepare_sheets.py .\complaint-early-warning
 if ($LASTEXITCODE -ne 0) { throw 'Aggregation failed.' }
 python .\upload_sheets.py
 if ($LASTEXITCODE -ne 0) { throw 'Google Sheets upload failed.' }
} finally { Pop-Location }
