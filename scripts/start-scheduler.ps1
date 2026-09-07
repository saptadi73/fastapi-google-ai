$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
New-Item -ItemType Directory -Force -Path storage | Out-Null
& .\venv\Scripts\python.exe -m celery -A app.workers.celery_app:celery_app beat --loglevel=info --schedule=storage/celerybeat-schedule
