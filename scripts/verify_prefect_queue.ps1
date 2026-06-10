#Requires -Version 5.1

[CmdletBinding()]
param(
    [string] $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string] $DeploymentName = "park-access-flow/park-access",
    [int] $DelaySeconds = 2
)

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "setup_prefect.ps1") -Action bootstrap -ProjectRoot $ProjectRoot

Write-Host "Triggering first flow run..."
prefect deployment run $DeploymentName | Out-Host

Start-Sleep -Seconds $DelaySeconds

Write-Host "Triggering second flow run; expected behavior is queued execution due to concurrency_limit=1..."
prefect deployment run $DeploymentName | Out-Host

Write-Host "Inspect run states in Prefect UI. The second run should queue until the first run finishes."
