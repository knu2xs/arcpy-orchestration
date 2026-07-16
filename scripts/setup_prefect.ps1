#Requires -Version 5.1

[CmdletBinding()]
param(
    [ValidateSet("bootstrap", "show-config", "start-server", "start-worker", "serve-flow")]
    [string] $Action = "bootstrap",
    [string] $ProjectRoot,
    [string] $WorkPoolName,
    [string] $WorkerType
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $scriptPath = $PSCommandPath
    if ([string]::IsNullOrWhiteSpace($scriptPath)) {
        $scriptPath = $MyInvocation.MyCommand.Path
    }
    if ([string]::IsNullOrWhiteSpace($scriptPath)) {
        throw "Unable to resolve script path for setup_prefect.ps1. Pass -ProjectRoot explicitly."
    }

    $scriptDir = Split-Path -Path $scriptPath -Parent
    $ProjectRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
}

function Get-PythonExecutable {
    param([string] $Root)

    $projectEnvPython = Join-Path $Root "env\python.exe"
    if (Test-Path $projectEnvPython) {
        return $projectEnvPython
    }

    if (-not [string]::IsNullOrWhiteSpace($env:CONDA_PREFIX)) {
        $condaPrefixPython = Join-Path $env:CONDA_PREFIX "python.exe"
        if (Test-Path $condaPrefixPython) {
            return $condaPrefixPython
        }
    }

    return (Get-Command python -ErrorAction Stop).Source
}

$PythonExecutable = Get-PythonExecutable -Root $ProjectRoot

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

    $json = $code | & $PythonExecutable - $Root
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

function Wait-ForPrefectApi {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ApiUrl,
        [int] $TimeoutSeconds = 90,
        [int] $PollSeconds = 2
    )

    if ([string]::IsNullOrWhiteSpace($ApiUrl)) {
        throw "PREFECT_API_URL is not set; cannot check Prefect API readiness."
    }

    $baseApiUrl = $ApiUrl.TrimEnd("/")
    $healthUrl = "$baseApiUrl/health"
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    Write-Host "Waiting for Prefect API at '$healthUrl' (timeout: ${TimeoutSeconds}s)..."

    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $healthUrl -Method Get -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                Write-Host "Prefect API is reachable."
                return
            }
        }
        catch {
            # Server may still be starting; continue polling until timeout.
        }

        Start-Sleep -Seconds $PollSeconds
    }

    throw "Prefect API did not become reachable at '$healthUrl' within ${TimeoutSeconds}s."
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
        & $PythonExecutable -m prefect server start
    }
    "start-worker" {
        Write-Host "Ensuring work pool '$effectiveWorkPool' exists..."
        & $PythonExecutable -m prefect work-pool create $effectiveWorkPool --type $effectiveWorkerType 2>$null
        Write-Host "Starting Prefect worker..."
        & $PythonExecutable -m prefect worker start --pool $effectiveWorkPool --type $effectiveWorkerType
    }
    "serve-flow" {
        Write-Host "Starting managed flow serve process..."
        $apiTimeout = 90
        if (-not [string]::IsNullOrWhiteSpace($env:PREFECT_API_STARTUP_TIMEOUT_SEC)) {
            try {
                $apiTimeout = [int]$env:PREFECT_API_STARTUP_TIMEOUT_SEC
            }
            catch {
                Write-Warning "Invalid PREFECT_API_STARTUP_TIMEOUT_SEC '$($env:PREFECT_API_STARTUP_TIMEOUT_SEC)'; using default ${apiTimeout}s."
            }
        }

        Wait-ForPrefectApi -ApiUrl ([string]$runtimeState.env.PREFECT_API_URL) -TimeoutSeconds $apiTimeout
        & $PythonExecutable (Join-Path $ProjectRoot "scripts\make_data_prefect.py")
    }
}
