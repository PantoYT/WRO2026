# ============================================================
# Espero-bot — one-command setup & launch (Windows)
#
#   .\run.ps1              # set up env if needed, run the robot
#   .\run.ps1 -Test        # set up env if needed, run BLE link test
#   .\run.ps1 -SetupOnly   # just prepare the environment
#   .\run.ps1 -Reinstall   # force reinstall of dependencies
#
# Safe to run on a fresh machine: finds Python 3.10–3.13, creates
# the venv, detects a venv broken by moving/copying the project
# (hardcoded paths) and rebuilds it, installs deps only when
# requirements.txt changed.
# ============================================================
param(
    [switch]$Test,
    [switch]$SetupOnly,
    [switch]$Reinstall
)
$ErrorActionPreference = "Stop"

$Root   = $PSScriptRoot
$Venv   = Join-Path $Root "espero_env"
$VenvPy = Join-Path $Venv "Scripts\python.exe"
$Marker = Join-Path $Venv ".requirements.sha256"

function Find-BasePython {
    # torch needs <= 3.13, pybricksdev needs >= 3.10
    foreach ($v in "3.13", "3.12", "3.11", "3.10") {
        try {
            $exe = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
        } catch {}
    }
    try {
        $ok = & python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return (& python -c "import sys; print(sys.executable)").Trim()
        }
    } catch {}
    return $null
}

# ── 1. Validate the venv (catches the moved-project case) ──
$venvOk = $false
if (Test-Path $VenvPy) {
    & $VenvPy -m pip --version *> $null
    if ($LASTEXITCODE -eq 0) {
        # venv created for a different location? (entry-point .exe files
        # embed the absolute path and break after a move)
        $cfg = Get-Content (Join-Path $Venv "pyvenv.cfg") -ErrorAction SilentlyContinue
        $cmd = ($cfg | Where-Object { $_ -match "^command\s*=" }) -join ""
        if ($cmd -and $cmd -notmatch [regex]::Escape($Venv)) {
            Write-Host "[setup] Venv was created for a different path - rebuilding..."
        } else {
            $venvOk = $true
        }
    } else {
        Write-Host "[setup] Venv python/pip not working - rebuilding..."
    }
}

if (-not $venvOk) {
    if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
    $base = Find-BasePython
    if (-not $base) {
        Write-Error "No Python 3.10-3.13 found. Install one from python.org, then re-run."
        exit 1
    }
    Write-Host "[setup] Creating venv with $base ..."
    & $base -m venv $Venv
    & $VenvPy -m pip install --upgrade pip --quiet
}

# ── 2. Install dependencies only when requirements.txt changed ──
$reqHash = (Get-FileHash (Join-Path $Root "requirements.txt") -Algorithm SHA256).Hash
$oldHash = if (Test-Path $Marker) { (Get-Content $Marker -Raw).Trim() } else { "" }
if ($Reinstall -or $reqHash -ne $oldHash) {
    Write-Host "[setup] Installing dependencies (first time downloads ~2 GB for torch)..."
    & $VenvPy -m pip install -r (Join-Path $Root "requirements.txt")
    if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed."; exit 1 }
    Set-Content -Path $Marker -Value $reqHash
} else {
    Write-Host "[setup] Dependencies up to date."
}

if ($SetupOnly) { Write-Host "[setup] Done."; exit 0 }

# ── 3. Launch ──
Set-Location $Root
if ($Test) {
    & $VenvPy (Join-Path $Root "tools\ble_link_test.py") --auto
} else {
    & $VenvPy (Join-Path $Root "computer.py")
}
exit $LASTEXITCODE
