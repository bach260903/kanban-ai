# Dev server with reload; exclude sandbox dirs to avoid reload loops when agents write files.
Set-Location $PSScriptRoot
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000 `
  --reload-exclude "sandbox/*" `
  --reload-exclude "*/sandbox/*"
