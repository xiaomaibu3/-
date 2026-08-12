$ErrorActionPreference = "Stop"

$python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

& $python -m pip install -r requirements-desktop.txt
& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --icon "static\icons\app-icon.ico" `
  --name Xinggui `
  --add-data "templates;templates" `
  --add-data "static;static" `
  --collect-all webview `
  desktop_app.py

Copy-Item -LiteralPath "README-server-client.txt" -Destination "dist\Xinggui\README.txt" -Force
Write-Host "Desktop build created at: dist\Xinggui"
