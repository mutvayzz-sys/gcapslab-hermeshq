param(
    [string]$Context = "macmini",
    [string]$ProjectName = "gcaplabs-hermeshq"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

& docker --context $Context compose --project-name $ProjectName -f (Join-Path $Root "docker-compose.yml") ps
if ($LASTEXITCODE -ne 0) {
    throw "docker compose ps failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Runtime containers:"
& docker --context $Context ps --filter "label=hermeshq.runtime_container_id" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
if ($LASTEXITCODE -ne 0) {
    throw "docker ps failed with exit code $LASTEXITCODE"
}
