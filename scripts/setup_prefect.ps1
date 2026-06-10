#Requires -Version 5.1

[CmdletBinding()]
param(
    [ValidateSet("bootstrap", "show-config", "start-server", "start-worker", "serve-flow")]
    [string] $Action = "bootstrap",
    [string] $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string] $WorkPoolName,
    [string] $WorkerType
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-PrefectRuntimeState {
    param([string] $Root)

    $code = @'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "src"))

from arcpy_orchestration.orchestration import (
    assert_sqlite_health,
    build_prefect_environment,
    render_effective_runtime_settings,
    resolve_prefect_runtime_config,
)

runtime = resolve_prefect_runtime_config()
assert_sqlite_health(runtime)
env_map = build_prefect_environment(runtime)
print(
    json.dumps(
        {
            "env": env_map,
            "worker_type": runtime.worker_type,
            "work_pool_name": runtime.work_pool_name,
            "rendered": render_effective_runtime_settings(runtime),
        }
    )
)
'@

    $json = $code | & python - $Root
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to resolve Prefect runtime configuration."
    }

    return $json | ConvertFrom-Json
}

function Export-PrefectEnvironment {
    param($RuntimeState)

    foreach ($property in $RuntimeState.env.PSObject.Properties) {
        Set-Item -Path "Env:$($property.Name)" -Value ([string]$property.Value)
    }
}

$runtimeState = Get-PrefectRuntimeState -Root $ProjectRoot
Export-PrefectEnvironment -RuntimeState $runtimeState

Write-Host $runtimeState.rendered

$effectiveWorkPool = if ($WorkPoolName) { $WorkPoolName } else { [string]$runtimeState.work_pool_name }
$effectiveWorkerType = if ($WorkerType) { $WorkerType } else { [string]$runtimeState.worker_type }

switch ($Action) {
    "bootstrap" {
        Write-Host "Prefect runtime bootstrap complete."
    }
    "show-config" {
        Write-Host "Displayed resolved Prefect runtime configuration."
    }
    "start-server" {
        Write-Host "Starting Prefect server..."
        prefect server start
    }
    "start-worker" {
        Write-Host "Ensuring work pool '$effectiveWorkPool' exists..."
        prefect work-pool create $effectiveWorkPool --type $effectiveWorkerType 2>$null
        Write-Host "Starting Prefect worker..."
        prefect worker start --pool $effectiveWorkPool --type $effectiveWorkerType
    }
    "serve-flow" {
        Write-Host "Starting managed flow serve process..."
        & python (Join-Path $ProjectRoot "scripts\make_data_prefect.py")
    }
}
