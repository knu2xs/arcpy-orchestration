#Requires -Version 5.1

[CmdletBinding()]
param(
    [string] $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

& (Join-Path $PSScriptRoot "setup_prefect.ps1") -Action show-config -ProjectRoot $ProjectRoot
