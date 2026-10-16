$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python pipeline.py daily
    if ($LASTEXITCODE -ne 0) { throw 'CFPB pipeline failed; Tableau exports were not rebuilt.' }
    python prepare_tableau.py
    if ($LASTEXITCODE -ne 0) { throw 'Tableau preparation failed.' }
    Write-Host 'Data updated. Refresh your local Tableau extract and save to Tableau Public again.'
} finally { Pop-Location }
