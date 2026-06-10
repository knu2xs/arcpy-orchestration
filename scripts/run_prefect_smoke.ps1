#Requires -Version 5.1

[CmdletBinding()]
param(
    [string] $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "setup_prefect.ps1") -Action bootstrap -ProjectRoot $ProjectRoot

$code = @'
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "scripts"))

from make_data_prefect import park_access_flow

result = park_access_flow()
print(f"Smoke run completed, output: {result}")
'@

& python -c $code $ProjectRoot
if ($LASTEXITCODE -ne 0) {
    throw "Prefect smoke run failed."
}
