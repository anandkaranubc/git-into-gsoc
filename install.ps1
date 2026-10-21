<#
.SYNOPSIS
  git-into-gsoc one-shot installer for Windows PowerShell.

.DESCRIPTION
  From a clone:   .\install.ps1 [-NoUserSkills | -UserSkills] [-Assistant name] [-SkillOnly] [-McpOnly] [-DryRun] [-InstallUv]
                  -> installs the package into .\.venv, then runs `git-into-gsoc setup`
  From anywhere:  irm https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.ps1 | iex
                  -> installs the tool with uv or pipx (or a private venv), then runs setup

  Needs uv, pipx, or Python 3.11 or newer on PATH as `py` or `python`. When none of
  them is present it offers to install uv, which brings its own Python.
#>
[CmdletBinding()]
param(
  [switch]$NoUserSkills,
  [switch]$UserSkills,
  [string[]]$Assistant = @(),
  [switch]$SkillOnly,
  [switch]$McpOnly,
  [switch]$DryRun,
  [switch]$InstallUv
)

$ErrorActionPreference = "Stop"
$RepoUrl = if ($env:GIG_REPO_URL) { $env:GIG_REPO_URL } else { "https://github.com/anandkaranubc/git-into-gsoc" }
$OwnRepo = "anandkaranubc/git-into-gsoc"
$DocsUrl = "$RepoUrl/blob/main/docs"

function Log($msg) { Write-Host "==> $msg" }

$Root = $null
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "pyproject.toml"))) {
  if (Select-String -Path (Join-Path $PSScriptRoot "pyproject.toml") -Pattern '^name = "git-into-gsoc"' -Quiet) {
    $Root = $PSScriptRoot
  }
}
$Mode = if ($Root) { "checkout" } else { "remote" }
$Scope = if ($UserSkills) { "user" } elseif ($NoUserSkills) { "project" } elseif ($Mode -eq "remote") { "user" } else { "project" }

function Find-Python {
  foreach ($candidate in @(@("py", "-3"), @("python"), @("python3"))) {
    $exe = Get-Command $candidate[0] -ErrorAction SilentlyContinue
    if (-not $exe) { continue }
    $args = @($candidate[1..($candidate.Length)] | Where-Object { $_ }) + @("-c", "import sys; print(sys.version_info >= (3, 11))")
    $ok = & $exe.Source @args 2>$null
    if ("$ok".Trim() -eq "True") { return ,($candidate) }
  }
  throw "Python 3.11 or newer is required. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') and run this script again."
}

# Where the package comes from, best first:
#   1. PyPI, but only for a release that this repository's own release workflow published.
#      The name "git-into-gsoc" is not reserved on PyPI until the first upload, so anyone
#      could claim it; PyPI checks the trusted-publishing attestation on every upload and
#      serves the publisher it verified, which an upload from another repository cannot fake.
#   2. The wheel attached to the newest GitHub release: a finished package, so neither
#      Git nor a build step is needed.
#   3. The source on GitHub (needs Git), when the release cannot be looked up.
# An explicit GIG_REPO_URL means "install exactly this source", so 1 and 2 are skipped.
function Get-LatestReleaseVersion {
  if ($env:GIG_REPO_URL) { return $null }
  try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$OwnRepo/releases/latest" -TimeoutSec 10
    $version = "$($release.tag_name)".TrimStart("v")
    if ($version) { return $version }
  } catch { }
  # The API allows 60 requests an hour per address, which a classroom can use up. The
  # release page redirects to the newest tag without counting against that limit.
  try {
    $page = Invoke-WebRequest -Uri "https://github.com/$OwnRepo/releases/latest" -Method Head -UseBasicParsing -TimeoutSec 10
    # Where the redirect ended: ResponseUri in Windows PowerShell 5.1, RequestMessage in 7.
    $final = if ($page.BaseResponse.ResponseUri) { $page.BaseResponse.ResponseUri.AbsoluteUri } else { $page.BaseResponse.RequestMessage.RequestUri.AbsoluteUri }
    if ("$final" -match "/releases/tag/v?([0-9][0-9A-Za-z.+-]*)$") { return $Matches[1] }
  } catch { }
  return $null
}

function Get-VerifiedPyPISpec([string]$Version) {
  try {
    $wheel = "git_into_gsoc-$Version-py3-none-any.whl"
    $provenance = Invoke-RestMethod -Uri "https://pypi.org/integrity/git-into-gsoc/$Version/$wheel/provenance" -TimeoutSec 10
    foreach ($bundle in $provenance.attestation_bundles) {
      if ($bundle.publisher.kind -eq "GitHub" -and $bundle.publisher.repository -eq $OwnRepo) {
        return "git-into-gsoc==$Version"
      }
    }
  } catch { }
  return $null
}

function Get-ReleaseWheelSpec([string]$Version) {
  $url = "https://github.com/$OwnRepo/releases/download/v$Version/git_into_gsoc-$Version-py3-none-any.whl"
  try {
    Invoke-WebRequest -Uri $url -Method Head -UseBasicParsing -TimeoutSec 15 | Out-Null
    return $url
  } catch { }
  return $null
}

function Get-InstallSpec {
  $version = Get-LatestReleaseVersion
  if ($version) {
    $spec = Get-VerifiedPyPISpec $version
    if ($spec) {
      Log "Using $spec from PyPI (published by $OwnRepo)"
      return $spec
    }
    $spec = Get-ReleaseWheelSpec $version
    if ($spec) {
      Log "Using release v$version from GitHub"
      return $spec
    }
  }
  if (-not $env:GIG_REPO_URL) { Log "Could not look up the newest release (no network, or GitHub is busy)" }
  Log "Using the source on GitHub ($RepoUrl)"
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Installing from the source needs Git, which was not found. Check your internet connection and try again in a few minutes, or install Git from https://git-scm.com/downloads first."
  }
  return "git+$RepoUrl"
}

# uv installs Python by itself, so a computer without Python 3.11 can still install
# the tool. It is only offered when there is no uv, no pipx, and no usable Python.
function Test-PythonOk {
  try { Find-Python | Out-Null; return $true } catch { return $false }
}

function Request-Uv {
  if ((Get-Command uv -ErrorAction SilentlyContinue) -or (Get-Command pipx -ErrorAction SilentlyContinue) -or (Test-PythonOk)) { return }
  Write-Host "This computer has no uv, no pipx, and no Python 3.11 or newer."
  Write-Host "uv is a free tool from Astral (https://docs.astral.sh/uv/) that installs Python"
  Write-Host "programs and the Python they need, into your user folder only."
  $yes = $InstallUv
  if (-not $yes -and [Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
    $answer = Read-Host "Install uv now? [Y/n]"
    $yes = ($answer -eq "" -or $answer -match "^[Yy]")
  }
  if (-not $yes) {
    throw "To let this installer get uv for you, run it again with -InstallUv:`n  & ([scriptblock]::Create((irm https://raw.githubusercontent.com/$OwnRepo/main/install.ps1))) -InstallUv`nOr install Python 3.11 or newer from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') and run this installer again."
  }
  Log "Installing uv from https://astral.sh/uv/install.ps1"
  powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
  $env:Path = "$(Join-Path $env:USERPROFILE '.local\bin');$env:Path"
  if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was installed but is not on PATH yet. Open a new terminal and run this script again."
  }
}

$GigBin = $null

# New terminals read the user PATH from the registry, so a folder added here is found by
# every terminal opened afterwards. The current one is updated too.
function Add-ToUserPath([string]$Dir) {
  $current = [Environment]::GetEnvironmentVariable("Path", "User")
  $parts = @("$current".Split(";") | Where-Object { $_ })
  $machine = @("$([Environment]::GetEnvironmentVariable("Path", "Machine"))".Split(";"))
  if ($parts -notcontains $Dir -and $machine -notcontains $Dir) {
    [Environment]::SetEnvironmentVariable("Path", (@($parts) + $Dir) -join ";", "User")
    Log "Added $Dir to your PATH, so new terminals find git-into-gsoc"
  }
  if (@($env:Path.Split(";")) -notcontains $Dir) { $env:Path = "$env:Path;$Dir" }
}

if (-not $SkillOnly) {
  if ($Mode -ne "checkout") { Request-Uv }
  if ($Mode -eq "checkout") {
    Log "Installing git-into-gsoc into $Root\.venv"
    $py = Find-Python
    $venv = Join-Path $Root ".venv"
    if (-not (Test-Path $venv)) { & $py[0] @($py[1..($py.Length)] | Where-Object { $_ }) -m venv $venv }
    $venvPy = Join-Path $venv "Scripts\python.exe"
    & $venvPy -m pip install -q -U pip
    & $venvPy -m pip install -q -e $Root
    $GigBin = Join-Path $venv "Scripts\git-into-gsoc.exe"
  } elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    $spec = Get-InstallSpec
    Log "Installing git-into-gsoc with uv"
    uv tool install -q --force $spec
    $bin = "$(uv tool dir --bin)".Trim()
    $GigBin = Join-Path $bin "git-into-gsoc.exe"
    Add-ToUserPath $bin
  } elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
    $spec = Get-InstallSpec
    Log "Installing git-into-gsoc with pipx"
    pipx install --force $spec | Out-Null
    $bin = "$(pipx environment --value PIPX_BIN_DIR 2>$null)".Trim()
    if (-not $bin) { $bin = Join-Path $env:USERPROFILE ".local\bin" }
    $GigBin = Join-Path $bin "git-into-gsoc.exe"
    Add-ToUserPath $bin
  } else {
    $py = Find-Python
    $base = Join-Path $env:LOCALAPPDATA "git-into-gsoc"
    Log "Installing git-into-gsoc into $base\venv (install uv or pipx for a lighter setup)"
    $venv = Join-Path $base "venv"
    if (-not (Test-Path $venv)) { & $py[0] @($py[1..($py.Length)] | Where-Object { $_ }) -m venv $venv }
    $venvPy = Join-Path $venv "Scripts\python.exe"
    & $venvPy -m pip install -q -U pip
    & $venvPy -m pip install -q (Get-InstallSpec)
    $GigBin = Join-Path $venv "Scripts\git-into-gsoc.exe"
    Add-ToUserPath (Join-Path $venv "Scripts")
  }
  if (-not (Test-Path $GigBin)) {
    throw "The install finished, but $GigBin is missing. Run this installer again; if it fails the same way, open an issue at $RepoUrl/issues with this message."
  }
  & $GigBin --version | Out-Null
} else {
  if ($Mode -eq "checkout" -and (Test-Path (Join-Path $Root ".venv\Scripts\git-into-gsoc.exe"))) {
    $GigBin = Join-Path $Root ".venv\Scripts\git-into-gsoc.exe"
  } elseif (Get-Command git-into-gsoc -ErrorAction SilentlyContinue) {
    $GigBin = "git-into-gsoc"
  } else {
    throw "git-into-gsoc is not installed yet; run install.ps1 without -SkillOnly first."
  }
}

$setupArgs = @("setup", "--scope", $Scope)
if ($Scope -eq "project" -and $Root) { $setupArgs += @("--project-dir", $Root) }
if ($SkillOnly) { $setupArgs += "--no-mcp" }
if ($McpOnly) { $setupArgs += "--no-skill" }
if ($DryRun) { $setupArgs += "--dry-run" }
foreach ($a in $Assistant) { $setupArgs += @("--assistant", $a) }
Log "Running: git-into-gsoc $($setupArgs -join ' ')"
& $GigBin @setupArgs

if (-not $DryRun) {
  Write-Host ""
  Write-Host "All set. Next steps:"
  if ($Mode -eq "checkout") {
    Write-Host "  1. Run the tool with its full path, or activate the environment first:"
    Write-Host "       $GigBin start"
    Write-Host "       .\.venv\Scripts\Activate.ps1"
  } else {
    Write-Host "  1. Open a new terminal, then answer four quick questions and see"
    Write-Host "     organizations that fit you:"
    Write-Host "       git-into-gsoc start"
  }
  Write-Host "  2. Any time you are unsure what to do next:  git-into-gsoc next"
  Write-Host "  3. If something does not work:  git-into-gsoc doctor"
  Write-Host ""
  Write-Host "  The beginner guide walks through every step: $DocsUrl/README.md"
}
