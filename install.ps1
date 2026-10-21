<#
.SYNOPSIS
  git-into-gsoc one-shot installer for Windows PowerShell.

.DESCRIPTION
  From a clone:   .\install.ps1 [-NoUserSkills | -UserSkills] [-Assistant name] [-SkillOnly] [-McpOnly] [-DryRun]
                  -> installs the package into .\.venv, then runs `git-into-gsoc setup`
  From anywhere:  irm https://raw.githubusercontent.com/anandkaranubc/git-into-gsoc/main/install.ps1 | iex
                  -> installs the tool with uv or pipx (or a private venv), then runs setup

  Requires Python 3.11 or newer on PATH as `py` or `python`.
#>
[CmdletBinding()]
param(
  [switch]$NoUserSkills,
  [switch]$UserSkills,
  [string[]]$Assistant = @(),
  [switch]$SkillOnly,
  [switch]$McpOnly,
  [switch]$DryRun
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

# PyPI is used only for a release that this repository's own release workflow published.
# The name "git-into-gsoc" is not reserved on PyPI until the first upload, so anyone
# could claim it; PyPI checks the trusted-publishing attestation on every upload and
# serves the publisher it verified, which an upload from another repository cannot fake.
# Anything else (no release yet, another publisher, no network) installs from GitHub.
# An explicit GIG_REPO_URL means "install exactly this source", so PyPI is skipped.
function Get-VerifiedPyPISpec {
  if ($env:GIG_REPO_URL) { return $null }
  try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$OwnRepo/releases/latest" -TimeoutSec 10
    $version = "$($release.tag_name)".TrimStart("v")
    if (-not $version) { return $null }
    $wheel = "git_into_gsoc-$version-py3-none-any.whl"
    $provenance = Invoke-RestMethod -Uri "https://pypi.org/integrity/git-into-gsoc/$version/$wheel/provenance" -TimeoutSec 10
    foreach ($bundle in $provenance.attestation_bundles) {
      if ($bundle.publisher.kind -eq "GitHub" -and $bundle.publisher.repository -eq $OwnRepo) {
        return "git-into-gsoc==$version"
      }
    }
  } catch {
    return $null
  }
  return $null
}

function Get-InstallSpec {
  $spec = Get-VerifiedPyPISpec
  if ($spec) {
    Log "Using $spec from PyPI (published by $OwnRepo)"
    return $spec
  }
  Log "Using the source on GitHub ($RepoUrl)"
  return "git+$RepoUrl"
}

$GigBin = $null

if (-not $SkillOnly) {
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
    $GigBin = Join-Path (uv tool dir --bin) "git-into-gsoc.exe"
  } elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
    $spec = Get-InstallSpec
    Log "Installing git-into-gsoc with pipx"
    pipx install --force $spec | Out-Null
    $GigBin = "git-into-gsoc"
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
    Write-Host "Add $(Join-Path $venv 'Scripts') to your PATH to run git-into-gsoc from any folder."
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
    Write-Host "       $GigBin program"
    Write-Host "       .\.venv\Scripts\Activate.ps1"
  } else {
    Write-Host "  1. Open a new terminal, then try:"
    Write-Host "       git-into-gsoc program"
  }
  Write-Host "  2. Check your setup any time:  git-into-gsoc doctor"
  Write-Host "  3. Beginner guide:  $DocsUrl/README.md"
}
