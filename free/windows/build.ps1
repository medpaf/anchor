# Builds Anchor for Windows: runs the tests, makes dist\Anchor\Anchor.exe, then the installer
# dist\anchor-win.exe (when Inno Setup 6 is installed).
#
#   powershell -ExecutionPolicy Bypass -File build.ps1
#
# Needs Python 3.10+ from python.org (with the "py" launcher). Inno Setup: https://jrsoftware.org/isinfo.php

param([switch]$SkipTests, [switch]$SkipInstaller)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1. A private Python environment with Qt, cryptography and PyInstaller.
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv .venv } else { python -m venv .venv }
}
$python = ".venv\Scripts\python.exe"
& $python -m pip install --quiet --upgrade pip
& $python -m pip install --quiet -r requirements.txt pyinstaller

# 2. adb: Google's platform-tools, shipped inside Anchor so users don't need to install anything.
$tools = "desktop\platform-tools"
if (-not (Test-Path "$tools\adb.exe")) {
    Write-Host "Downloading Google's platform-tools (adb)..."
    $zip = Join-Path $env:TEMP "anchor-platform-tools.zip"
    $unzipped = Join-Path $env:TEMP "anchor-platform-tools"
    Invoke-WebRequest "https://dl.google.com/android/repository/platform-tools-latest-windows.zip" -OutFile $zip
    Expand-Archive $zip -DestinationPath $unzipped -Force
    New-Item -ItemType Directory -Force $tools | Out-Null
    foreach ($f in "adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll", "NOTICE.txt") {
        Copy-Item (Join-Path $unzipped "platform-tools\$f") $tools
    }
}

# 3. Tests (no phone needed).
if (-not $SkipTests) {
    & $python tests\run_tests.py
    if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
}

# 4. Anchor.exe and its folder.
& $python -m PyInstaller --noconfirm --clean anchor.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# 5. The installer.
if (-not $SkipInstaller) {
    $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
              "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($iscc) {
        & $iscc /Q installer.iss
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
        Write-Host "Installer: dist\anchor-win.exe"
    } else {
        Write-Host "Inno Setup 6 isn't installed, so only dist\Anchor\Anchor.exe was built."
    }
}
