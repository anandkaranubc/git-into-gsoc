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
#   3. The source on GitHub (needs Git), at the newest release's tag. Only when the release
#      cannot be looked up at all is it the newest commit instead.
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

# The sources to try, best first. Each later one is also a fallback when installing an
# earlier one fails: right after a release, PyPI can serve its provenance before every
# PyPI server offers the files, so for a few minutes the release wheel works and PyPI not.
function Get-InstallSpecs {
  # CI passes a wheel it just built: cloning the repository through pipx takes minutes.
  if ($env:GIG_INSTALL_SPEC) { return @($env:GIG_INSTALL_SPEC) }
  $specs = @()
  $gitSpec = "git+$RepoUrl"
  $from = $RepoUrl
  $version = Get-LatestReleaseVersion
  if ($version) {
    # The tag keeps the source the same code as the release, not changes merged since.
    $gitSpec = "git+${RepoUrl}@v$version"
    $from = "$RepoUrl, release v$version"
    $spec = Get-VerifiedPyPISpec $version
    if ($spec) {
      Log "Using $spec from PyPI (published by $OwnRepo)"
      $specs += $spec
    }
    $spec = Get-ReleaseWheelSpec $version
    if ($spec) {
      if (-not $specs) { Log "Using release v$version from GitHub" }
      $specs += $spec
    }
  }
  $hasGit = [bool](Get-Command git -ErrorAction SilentlyContinue)
  if (-not $specs) {
    if (-not $env:GIG_REPO_URL -and -not $version) { Log "Could not look up the newest release (no network, or GitHub is busy)" }
    Log "Using the source on GitHub ($from)"
    if (-not $hasGit) {
      throw "Installing from the source needs Git, which was not found. Check your internet connection and try again in a few minutes, or install Git from https://git-scm.com/downloads first."
    }
  }
  if ($hasGit) { $specs += $gitSpec }
  return $specs
}

# Runs $Install with each source until one works. A native command that fails does not
# stop PowerShell, so the exit code is checked; otherwise an update that failed would
# leave the old version in place and still report success.
function Install-FirstWorking([scriptblock]$Install) {
  $specs = @(Get-InstallSpecs)
  foreach ($spec in $specs) {
    # With $PSNativeCommandUseErrorActionPreference on, a failed command throws instead.
    try { & $Install $spec } catch { $global:LASTEXITCODE = 1 }
    if ($LASTEXITCODE -eq 0) {
      if ($spec -ne $specs[0]) { Log "Installed from $spec instead" }
      return
    }
    Write-Host ""  # the tool's last error line can lack a newline
    if ($spec -like "git-into-gsoc==*") {
      Log "Could not install $spec from PyPI. A new release can take a few minutes to reach every PyPI server, so trying the next source."
    } else {
      Log "Could not install $spec. Trying the next source."
    }
  }
  throw "Could not install git-into-gsoc from any source. Check your internet connection and try again in a few minutes."
}

# uv installs Python by itself, so a computer without Python 3.11 can still install
# the tool. It is only offered when there is no uv, no pipx, and no usable Python.
function Test-PythonOk {
  try { Find-Python | Out-Null; return $true } catch { return $false }
}

# pipx installs with the Python it runs on. A pipx on Python older than 3.11 fails every
# source with "requires a different Python", and the installer blamed the network.
function Get-PipxPython {
  try { return "$(pipx environment --value PIPX_DEFAULT_PYTHON 2>$null)".Trim() } catch { return "" }
}

function Test-PipxOk {
  if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) { return $false }
  $py = Get-PipxPython
  if (-not $py) { return $true }  # an older pipx cannot say: try it
  try { & $py -c "import sys; raise SystemExit(sys.version_info < (3, 11))" 2>$null } catch { return $false }
  return ($LASTEXITCODE -eq 0)
}

function Request-Uv {
  if ((Get-Command uv -ErrorAction SilentlyContinue) -or (Test-PipxOk) -or (Test-PythonOk)) { return }
  if (Get-Command pipx -ErrorAction SilentlyContinue) {
    Write-Host "pipx is here, but it runs on a Python older than 3.11 ($(Get-PipxPython)), and git-into-gsoc needs 3.11 or newer."
  }
  Write-Host "This computer has no uv, no usable pipx, and no Python 3.11 or newer."
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
    Log "Installing git-into-gsoc with uv"
    # A release minutes old can be missing from uv's cached copy of the PyPI index.
    Install-FirstWorking { param($spec) uv tool install --refresh-package git-into-gsoc -q --force $spec }
    $bin = "$(uv tool dir --bin)".Trim()
    $GigBin = Join-Path $bin "git-into-gsoc.exe"
    Add-ToUserPath $bin
  } elseif (Test-PipxOk) {
    Log "Installing git-into-gsoc with pipx"
    Install-FirstWorking { param($spec) pipx install --force $spec | Out-Null }
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
    Install-FirstWorking { param($spec) & $venvPy -m pip install -q $spec }
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
