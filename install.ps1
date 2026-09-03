<#
.SYNOPSIS
  Org installer (Windows): install the OKF CLI tools and register the
  knowledge-bundle skill into all AI agents (Claude Code, Cursor, Codex,
  generic .agents).

.DESCRIPTION
  Uses `uv` (preferred) to install the package as an isolated tool, then runs
  `catalogify --install` to drop the skill into each agent's skills directory.

  -Source controls where the package comes from. For org rollout, pass the Git
  URL of the repo (the package lives in the `catalogify` subdirectory):

    ./install.ps1 -Source "catalogify"

  With no -Source, it installs from this local folder (handy for testing).

  NOTE: okf-inventory and okf-history are bash scripts that shell out to git.
  On Windows they use the bash.exe that ships with Git for Windows, so install
  Git for Windows (https://git-scm.com/download/win) first.

.PARAMETER Source
  pip/uv install source. Default: this script's folder.

.PARAMETER Agents
  Comma-separated agents or 'all'. Default: all.

.PARAMETER Scope
  'user' (default, ~/.<agent>/skills) or 'project' (./.<agent>/skills).

.EXAMPLE
  ./install.ps1

.EXAMPLE
  ./install.ps1 -Source "catalogify"
#>
[CmdletBinding()]
param(
    [string]$Source = "",
    [string]$Agents = "all",
    [ValidateSet("user", "project")]
    [string]$Scope = "user"
)

$ErrorActionPreference = "Stop"
if (-not $Source) { $Source = $PSScriptRoot }

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

Write-Host "Installing catalogify from: $Source"

if (-not (Test-Command "git")) {
    Write-Warning "git not found on PATH. okf-inventory / okf-history need git and its bash.exe (Git for Windows)."
}

if (Test-Command "uv") {
    # --native-tls uses the system cert store (needed behind TLS-inspecting proxies).
    uv tool install --native-tls --force "$Source"
    uv tool update-shell 2>$null
}
elseif (Test-Command "pip") {
    Write-Host "uv not found; falling back to pip install --user..."
    pip install --user --upgrade "$Source"
}
elseif (Test-Command "python") {
    python -m pip install --user --upgrade "$Source"
}
else {
    throw "Neither uv, pip, nor python found on PATH. Install uv (https://astral.sh/uv) or Python first."
}

$skillArgs = @("--agents", $Agents, "--scope", $Scope)

Write-Host "Registering the skill with agents: $Agents (scope=$Scope)..."
if (Test-Command "catalogify") {
    & catalogify install @skillArgs
}
else {
    Write-Host "(catalogify not on PATH yet; invoking via python module)"
    python -m catalogify.installer @skillArgs
}

Write-Host ""
Write-Host "Done. Open a new terminal so PATH refreshes, then ask your agent:"
Write-Host '  "generate an OKF knowledge bundle for this repo"'
