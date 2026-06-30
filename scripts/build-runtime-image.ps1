param(
    [string]$Context = "macmini",
    [string]$Image = $env:RUNTIME_CONTAINER_IMAGE,
    [switch]$NoCache
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $Image) {
    $Image = "headmaster-hermes-runtime:latest"
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$DockerArgs = @("--context", $Context, "build", "--pull", "-f", (Join-Path $Root "backend/runtime.Dockerfile"), "-t", $Image)
if ($NoCache) {
    $DockerArgs += "--no-cache"
}
$DockerArgs += $Root

Write-Host "Building runtime image '$Image' on Docker context '$Context'..."
& docker @DockerArgs
if ($LASTEXITCODE -ne 0) {
    throw "Runtime image build failed with exit code $LASTEXITCODE"
}

Write-Host "Runtime image ready: $Image"
