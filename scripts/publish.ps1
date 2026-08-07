# [ ∅ VANTIO ] npm publish script
# Run from Windows PowerShell in the vantio-open-core directory:
#   cd C:\Users\zach_vantio\vantio-open-core
#   .\scripts\publish.ps1
#
# Prerequisites:
#   1. npm login (or set NPM_TOKEN environment variable)
#   2. pnpm is installed globally

param(
    [switch]$DryRun
)

$Root = Split-Path $PSScriptRoot -Parent
$DryRunFlag = if ($DryRun) { "--dry-run" } else { "" }

Write-Host ""
Write-Host "[ ∅ VANTIO ] npm publish" -ForegroundColor Cyan
Write-Host "  dry-run: $DryRun" -ForegroundColor Gray
Write-Host ""

# ── Build @vantio/agent-sdk ────────────────────────────────────────────────────
Write-Host "Building @vantio/agent-sdk..." -ForegroundColor Yellow
Set-Location "$Root\packages\vantio-agent-sdk"
pnpm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed." -ForegroundColor Red
    exit 1
}

Write-Host "Publishing @vantio/agent-sdk..." -ForegroundColor Yellow
npm publish --access public $DryRunFlag
if ($LASTEXITCODE -ne 0) {
    Write-Host "Publish failed (may already exist)." -ForegroundColor Yellow
}

# ── Publish @vantio/cli ────────────────────────────────────────────────────────
Write-Host "Publishing @vantio/cli..." -ForegroundColor Yellow
Set-Location "$Root\packages\vantio-cli"
npm publish --access public $DryRunFlag
if ($LASTEXITCODE -ne 0) {
    Write-Host "Publish failed (may already exist)." -ForegroundColor Yellow
}

Set-Location $Root
Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  @vantio/agent-sdk: https://www.npmjs.com/package/@vantio/agent-sdk"
Write-Host "  @vantio/cli:       https://www.npmjs.com/package/@vantio/cli"
Write-Host ""
