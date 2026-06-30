param(
    [string]$Context = "macmini",
    [string]$ProjectName = "gcaplabs-hermeshq",
    [string]$RuntimeImage = $env:RUNTIME_CONTAINER_IMAGE,
    [string]$ContainerHostUrl = $env:CONTAINER_HOST_URL,
    [switch]$NoCacheRuntime,
    [switch]$SkipRuntimeImage,
    [switch]$SkipComposeBuild,
    [switch]$CleanupStoppedRuntimes,
    [switch]$Smoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $RuntimeImage) {
    $RuntimeImage = "headmaster-hermes-runtime:latest"
}
if (-not $ContainerHostUrl) {
    $ContainerHostUrl = "https://hq.gcaplabs.com"
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

function Invoke-Docker {
    param([string[]]$ArgsList)
    & docker --context $Context @ArgsList
    if ($LASTEXITCODE -ne 0) {
        throw "docker $($ArgsList -join ' ') failed with exit code $LASTEXITCODE"
    }
}

Write-Host "Using Docker context '$Context'"
Invoke-Docker -ArgsList @("version", "--format", "{{.Server.Version}}")

if (-not $SkipRuntimeImage) {
    $runtimeArgs = @("-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "build-runtime-image.ps1"), "-Context", $Context, "-Image", $RuntimeImage)
    if ($NoCacheRuntime) {
        $runtimeArgs += "-NoCache"
    }
    & powershell @runtimeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Runtime image build failed with exit code $LASTEXITCODE"
    }
}

$oldRuntimeImage = $env:RUNTIME_CONTAINER_IMAGE
$oldContainerHostUrl = $env:CONTAINER_HOST_URL
$oldRuntimeNetwork = $env:RUNTIME_CONTAINER_NETWORK
try {
    $env:RUNTIME_CONTAINER_IMAGE = $RuntimeImage
    $env:CONTAINER_HOST_URL = $ContainerHostUrl
    $env:RUNTIME_CONTAINER_NETWORK = "hermes_runtime"

    $stoppedProjectContainers = & docker --context $Context ps -aq --filter "label=com.docker.compose.project=$ProjectName" --filter "status=exited" --filter "status=created"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to list stopped compose containers"
    }
    if ($stoppedProjectContainers) {
        Write-Host "Removing stopped HermesHQ compose containers..."
        & docker --context $Context rm @stoppedProjectContainers
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to remove stopped compose containers"
        }
    }

    $composeArgs = @(
        "compose",
        "--project-name", $ProjectName,
        "-f", (Join-Path $Root "docker-compose.yml"),
        "up"
    )
    if (-not $SkipComposeBuild) {
        $composeArgs += "--build"
    }
    $composeArgs += @("-d")

    Write-Host "Deploying HermesHQ stack to '$Context'..."
    Invoke-Docker -ArgsList $composeArgs
}
finally {
    $env:RUNTIME_CONTAINER_IMAGE = $oldRuntimeImage
    $env:CONTAINER_HOST_URL = $oldContainerHostUrl
    $env:RUNTIME_CONTAINER_NETWORK = $oldRuntimeNetwork
}

if ($CleanupStoppedRuntimes) {
    Write-Host "Removing stopped Headmaster runtime containers..."
    $ids = & docker --context $Context ps -aq --filter "label=hermeshq.runtime_container_id" --filter "status=exited"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to list stopped runtime containers"
    }
    if ($ids) {
        & docker --context $Context rm -f @ids
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to remove stopped runtime containers"
        }
    }
}

Write-Host "Current HermesHQ containers:"
Invoke-Docker -ArgsList @("compose", "--project-name", $ProjectName, "-f", (Join-Path $Root "docker-compose.yml"), "ps")

if ($Smoke) {
    $healthUrl = "$($ContainerHostUrl.TrimEnd('/'))/api/health"
    Write-Host "Checking $healthUrl ..."
    $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 20
    if ($response.StatusCode -lt 200 -or $response.StatusCode -gt 299) {
        throw "Smoke check failed with HTTP $($response.StatusCode)"
    }
    Write-Host "Smoke check passed: HTTP $($response.StatusCode)"
}

Write-Host "Remote deploy complete."
