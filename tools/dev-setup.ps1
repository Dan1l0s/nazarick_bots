<#
.SYNOPSIS
    Sets up a local development environment on Windows: a virtualenv, the test
    dependencies, and (optionally) the pre-commit hook.

.DESCRIPTION
    The native counterpart to setup.sh, which is a bash script and only detects
    Windows when it runs under Git Bash ($OSTYPE = "msys"). Running it from
    PowerShell picks up whichever `bash` is first on PATH - usually
    C:\Windows\System32\bash.exe, the WSL launcher. That fails outright with

        WSL (...) ERROR: CreateProcessCommon:818: execvpe(/bin/bash) failed

    when no WSL distro is installed, and is *worse* when one is: setup.sh then
    takes its Linux branch and installs Python packages and ffmpeg inside WSL,
    which is a different machine from the one your bots run on.

.PARAMETER VenvPath
    Where to create the virtualenv. Defaults to .venv in the repo root, which is
    the name hosting/deploy.sh looks for.

.PARAMETER Runtime
    Install only the runtime dependencies (requirements.txt). The default
    installs requirements-dev.txt, which includes the test suite.

.PARAMETER InstallHook
    Also copy tools/pre-commit into .git/hooks, so the suite runs before every
    commit.

.PARAMETER Force
    Recreate the virtualenv from scratch even if one already exists.

.EXAMPLE
    .\tools\dev-setup.ps1
    .\tools\dev-setup.ps1 -InstallHook
    powershell -ExecutionPolicy Bypass -File .\tools\dev-setup.ps1

.NOTES
    If PowerShell refuses to run this file, either use the -ExecutionPolicy form
    above or allow it for the current window only:
        Set-ExecutionPolicy -Scope Process -Bypass
#>

[CmdletBinding()]
param(
    [string] $VenvPath = ".venv",
    [switch] $Runtime,
    [switch] $InstallHook,
    [switch] $Force
)

$ErrorActionPreference = "Stop"

function Write-Step   { param($m) Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Ok     { param($m) Write-Host "    $m" -ForegroundColor Green }
function Write-Warn   { param($m) Write-Host "    $m" -ForegroundColor Yellow }
function Write-Fail   { param($m) Write-Host "    $m" -ForegroundColor Red }

# Always operate on the repo root, regardless of where this was invoked from.
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    Write-Step "Repository: $repoRoot"

    # --- locate a usable Python ------------------------------------------------
    # `py` (the launcher) is preferred: it finds real installations even when the
    # bare `python` on PATH is the Microsoft Store alias stub, which prints
    # nothing and opens the Store instead of running.
    Write-Step "Looking for Python"
    $python = $null
    foreach ($candidate in @(
            @{ Exe = "py";     Args = @("-3") },
            @{ Exe = "python"; Args = @() },
            @{ Exe = "python3"; Args = @() })) {
        if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) { continue }
        $probe = & $candidate.Exe @($candidate.Args + @("-c", "import sys; print(sys.version.split()[0])")) 2>&1
        if ($LASTEXITCODE -eq 0 -and $probe -match '^\d+\.\d+') {
            $python = $candidate
            Write-Ok "$($candidate.Exe) $($candidate.Args -join ' ') -> Python $probe"
            break
        }
    }

    if (-not $python) {
        Write-Fail "No working Python found."
        Write-Host ""
        # Single-quoted: in a double-quoted PowerShell string the backtick is the
        # escape character, so "`python`" would silently render as "python".
        Write-Host '    If "python" opens the Microsoft Store, that is the alias stub,'
        Write-Host '    not an interpreter. Install Python from'
        Write-Host '    https://www.python.org/downloads/ with "Add python.exe to PATH"'
        Write-Host '    ticked, then reopen PowerShell.'
        exit 1
    }

    $versionText = & $python.Exe @($python.Args + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])"))
    $parts = $versionText.Trim().Split('.')
    if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 10)) {
        Write-Fail "Python $versionText is too old; this project needs 3.10+ (match statements)."
        exit 1
    }

    # --- virtualenv -----------------------------------------------------------
    $venvPython = Join-Path $VenvPath "Scripts\python.exe"

    if ($Force -and (Test-Path $VenvPath)) {
        Write-Step "Removing existing $VenvPath (-Force)"
        Remove-Item -Recurse -Force $VenvPath
    }

    if (Test-Path $venvPython) {
        Write-Step "Reusing virtualenv at $VenvPath"
    } else {
        Write-Step "Creating virtualenv at $VenvPath"
        & $python.Exe @($python.Args + @("-m", "venv", $VenvPath))
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
            Write-Fail "Failed to create the virtualenv."
            exit 1
        }
    }
    Write-Ok $venvPython

    # --- dependencies ---------------------------------------------------------
    $requirements = if ($Runtime) { "requirements.txt" } else { "requirements-dev.txt" }
    Write-Step "Installing $requirements"

    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { Write-Warn "Could not upgrade pip; continuing." }

    & $venvPython -m pip install --upgrade -r $requirements
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Dependency install failed - see the pip output above."
        exit 1
    }
    Write-Ok "Dependencies installed"

    # --- ffmpeg (music bots only) ---------------------------------------------
    Write-Step "Checking FFmpeg"
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        Write-Ok "ffmpeg found on PATH"
    } else {
        Write-Warn "ffmpeg is NOT on PATH. The music bots need it; the tests do not."
        Write-Warn "Get a build from https://www.gyan.dev/ffmpeg/builds/ and add its"
        Write-Warn "bin\ folder to PATH - see the README, 'FFmpeg installation'."
    }

    # --- optional git hook ----------------------------------------------------
    if ($InstallHook) {
        Write-Step "Installing the pre-commit hook"
        $hookSource = Join-Path $repoRoot "tools\pre-commit"
        $hookTarget = Join-Path $repoRoot ".git\hooks\pre-commit"
        if (-not (Test-Path (Join-Path $repoRoot ".git"))) {
            Write-Warn "Not a git checkout; skipping."
        } else {
            Copy-Item $hookSource $hookTarget -Force
            Write-Ok "Installed. Bypass a single commit with: git commit --no-verify"
        }
    }

    # --- verify by actually running the suite ---------------------------------
    Write-Step "Running the test suite"
    & $venvPython -m pytest -q
    $testsExit = $LASTEXITCODE

    Write-Host ""
    if ($testsExit -eq 0) {
        Write-Ok "Environment is ready and the suite passes."
    } else {
        Write-Warn "The suite did not pass (exit $testsExit)."
        Write-Warn "Note coverage is enforced, so this can fail with every test passing."
    }

    Write-Host ""
    Write-Host "Activate it with:" -ForegroundColor Cyan
    Write-Host "    .\$VenvPath\Scripts\Activate.ps1"
    Write-Host "Then run the tests with:" -ForegroundColor Cyan
    Write-Host "    python -m pytest -q            # what CI runs"
    Write-Host "    python -m pytest -q --no-cov   # faster, for an edit-run loop"
    Write-Host ""
    Write-Host "Before the bots will start you still need configs\private_config.py" -ForegroundColor Yellow
    Write-Host "and db\ - see the README, 'Before the first run'." -ForegroundColor Yellow

    exit $testsExit
}
finally {
    Pop-Location
}
