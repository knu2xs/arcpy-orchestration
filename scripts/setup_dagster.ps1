<#
.SYNOPSIS
    Automates the production Dagster deployment described in
    docsrc/mkdocs/dagster_setup_instructions.md.

.DESCRIPTION
    Performs the steps from the Dagster setup guide on a Windows server:
      - Phase B: Enables IIS features and installs URL Rewrite + ARR via WinGet (sec. 1.1, 1.2)
      - Phase C: Imports an HTTPS certificate and binds it to Default Web Site (sec. 1.3)
      - Phase D: Enables ARR proxy and adds the Dagster reverse-proxy rewrite rule (sec. 1.4)
      - Phase D2: Clones the ArcGIS Pro `arcgispro-py3` conda env into CondaEnvPath (sec. 2.1)
      - Phase E: Installs dagster + dagster-webserver into the cloned conda env (sec. 2.2)
      - Phase F: Creates DAGSTER_HOME and writes dagster.yaml + workspace.yaml (sec. 3)
      - Phase G: Installs Servy via WinGet and creates two services via servy-cli (sec. 5, 6)
      - Phase H: Enables the Dagster schedule via the dagster CLI (sec. 7)

    Re-runnable: each phase can be skipped with the corresponding -Skip* switch.
    Existing files and services are preserved unless -Force / -ReinstallServices
    are passed.

.PARAMETER ProjectRoot
    Absolute path to the project root. Defaults to C:\projects\arcpy-orchestration.

.PARAMETER DagsterHome
    Path used for DAGSTER_HOME. Defaults to "<ProjectRoot>\dagster_home".

.PARAMETER CondaEnvPath
    Path to the conda environment containing dagster-webserver.exe and
    dagster-daemon.exe in its Scripts\ directory. Defaults to "<ProjectRoot>\env".

.PARAMETER WebserverPort
    TCP port the Dagster webserver listens on. Defaults to 3000.

.PARAMETER PathPrefix
    Optional URL path prefix (e.g. '/dagster') for sub-path hosting. Empty = root.

.PARAMETER ScheduleName
    Dagster schedule name to enable. Defaults to 'park_access_daily'.

.PARAMETER SkipIIS
    Skip IIS feature install, URL Rewrite + ARR install, and the reverse-proxy rule.

.PARAMETER SkipCert
    Skip the HTTPS certificate import and binding.

.PARAMETER SkipDagsterInstall
    Skip pip install of dagster + dagster-webserver into the conda env.

.PARAMETER SkipEnvClone
    Skip cloning the ArcGIS Pro `arcgispro-py3` env into CondaEnvPath. Use this
    when the cloned env has already been provisioned by another process.

.PARAMETER SkipServy
    Skip Servy install and service creation.

.PARAMETER SkipScheduleEnable
    Skip the final 'dagster schedule start' call.

.PARAMETER Force
    Overwrite existing dagster.yaml and workspace.yaml.

.PARAMETER ReinstallServices
    Uninstall and recreate DagsterWebserver / DagsterDaemon if they already exist.

.EXAMPLE
    PS> .\setup_dagster.ps1

.EXAMPLE
    PS> .\setup_dagster.ps1 -SkipIIS -SkipCert -SkipServy -SkipDagsterInstall -SkipScheduleEnable
    Generates only DAGSTER_HOME and the two YAML config files.

.NOTES
    Must be run from an elevated (Administrator) PowerShell session.
    Requires ArcGIS Pro to be installed locally; the script reads its install
    location from `HKLM:\SOFTWARE\ESRI\ArcGISPro` (with `HKCU:\` as fallback)
    so it can invoke the bundled conda to clone `arcgispro-py3`.
#>

#Requires -Version 5.1
#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string] $ProjectRoot         = 'C:\projects\arcpy-orchestration',
    [string] $DagsterHome,
    [string] $CondaEnvPath,
    [int]    $WebserverPort       = 3000,
    [string] $PathPrefix          = '',
    [string] $ScheduleName        = 'park_access_daily',
    [switch] $SkipIIS,
    [switch] $SkipCert,
    [switch] $SkipDagsterInstall,
    [switch] $SkipEnvClone,
    [switch] $SkipServy,
    [switch] $SkipScheduleEnable,
    [switch] $Force,
    [switch] $ReinstallServices
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Resolve dependent defaults now that $ProjectRoot is known.
if (-not $DagsterHome)  { $DagsterHome  = Join-Path $ProjectRoot 'dagster_home' }
if (-not $CondaEnvPath) { $CondaEnvPath = Join-Path $ProjectRoot 'env' }

$script:SkippedPhases = New-Object System.Collections.Generic.List[string]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Step {
    param([Parameter(Mandatory)][string] $Message)
    Write-Host ''
    Write-Host ('==> ' + $Message) -ForegroundColor Cyan
}

function Write-Info {
    param([Parameter(Mandatory)][string] $Message)
    Write-Host ('    ' + $Message) -ForegroundColor DarkGray
}

function Write-Skip {
    param([Parameter(Mandatory)][string] $Phase)
    Write-Host ('--  Skipping: ' + $Phase) -ForegroundColor Yellow
    $script:SkippedPhases.Add($Phase) | Out-Null
}

function Test-Command {
    param([Parameter(Mandatory)][string] $Name)
    return [bool] (Get-Command -Name $Name -ErrorAction SilentlyContinue)
}

function Invoke-Native {
    <#
    Invokes a native executable, streams output, throws on non-zero exit
    unless the exit code is in -AllowedExitCodes.
    #>
    param(
        [Parameter(Mandatory)][string]   $FilePath,
        [Parameter()][string[]]          $ArgumentList = @(),
        [Parameter()][int[]]             $AllowedExitCodes = @(0)
    )
    Write-Info ("`$ " + $FilePath + ' ' + ($ArgumentList -join ' '))
    & $FilePath @ArgumentList
    $code = $LASTEXITCODE
    if ($AllowedExitCodes -notcontains $code) {
        throw ("Command failed (exit $code): $FilePath " + ($ArgumentList -join ' '))
    }
    return $code
}

function Invoke-WinGetInstall {
    <#
    Installs a WinGet package by ID. Treats "no applicable upgrade found" /
    "package already installed" exit codes as success.
    #>
    param([Parameter(Mandatory)][string] $PackageId)

    # WinGet success-equivalent exit codes:
    #   0           OK
    #   -1978335189 APPINSTALLER_CLI_ERROR_UPDATE_NOT_APPLICABLE  (already installed / no update)
    #   -1978335135 APPINSTALLER_CLI_ERROR_NO_APPLICABLE_INSTALLER (sometimes returned when present)
    $allowed = @(0, -1978335189, -1978335135)

    Invoke-Native -FilePath 'winget' -ArgumentList @(
        'install',
        '--id', $PackageId,
        '-e',
        '--silent',
        '--accept-source-agreements',
        '--accept-package-agreements'
    ) -AllowedExitCodes $allowed | Out-Null
}

function Update-PathFromRegistry {
    $machinePath = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath    = [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $parts = @($machinePath, $userPath) | Where-Object { $_ }
    $env:Path = ($parts -join ';').TrimEnd(';')
}

function Assert-Prerequisites {
    Write-Step 'Validating prerequisites'

    $principal = New-Object Security.Principal.WindowsPrincipal(
        [Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
        throw 'This script must be run from an elevated (Administrator) PowerShell session.'
    }

    if (-not (Test-Command -Name 'winget')) {
        throw 'winget was not found on PATH. Install the App Installer from the Microsoft Store and retry.'
    }

    if (-not (Test-Path -LiteralPath $ProjectRoot)) {
        throw "ProjectRoot does not exist: $ProjectRoot"
    }

    # The cloned conda env may not exist yet (it is created in Phase D2). Only
    # require it up-front when both the clone and the install are being skipped
    # — in that case downstream phases (Servy, schedule) need it pre-existing.
    $envScripts = Join-Path $CondaEnvPath 'Scripts'
    if ($SkipEnvClone -and $SkipDagsterInstall) {
        if (-not (Test-Path -LiteralPath $envScripts)) {
            throw "Conda environment Scripts directory not found: $envScripts (required when both -SkipEnvClone and -SkipDagsterInstall are set)."
        }
    } elseif (Test-Path -LiteralPath $CondaEnvPath) {
        # If CondaEnvPath exists, it must look like a real env (have Scripts\).
        if (-not (Test-Path -LiteralPath $envScripts)) {
            throw "$CondaEnvPath exists but does not contain a Scripts\ directory; refusing to clone over it."
        }
    }

    Write-Info "ProjectRoot   = $ProjectRoot"
    Write-Info "DagsterHome   = $DagsterHome"
    Write-Info "CondaEnvPath  = $CondaEnvPath"
    Write-Info "WebserverPort = $WebserverPort"
    if ($PathPrefix) { Write-Info "PathPrefix    = $PathPrefix" }
}

# ---------------------------------------------------------------------------
# Phase B: IIS features + URL Rewrite + ARR
# ---------------------------------------------------------------------------

function Enable-IISFeatures {
    Write-Step 'Enabling IIS Windows features'

    $features = @(
        'IIS-WebServerRole',
        'IIS-WebServer',
        'IIS-CommonHttpFeatures',
        'IIS-DefaultDocument',
        'IIS-StaticContent',
        'IIS-HttpErrors',
        'IIS-ApplicationDevelopment',
        'IIS-ISAPIExtensions',
        'IIS-ISAPIFilter',
        'IIS-ManagementConsole'
    )

    foreach ($feature in $features) {
        $state = (Get-WindowsOptionalFeature -Online -FeatureName $feature -ErrorAction Stop).State
        if ($state -eq 'Enabled') {
            Write-Info "$feature already enabled"
            continue
        }
        Write-Info "Enabling $feature ..."
        Enable-WindowsOptionalFeature -Online -FeatureName $feature -NoRestart -All `
            -ErrorAction Stop | Out-Null
    }
}

function Install-IISProxyModules {
    Write-Step 'Installing URL Rewrite and Application Request Routing via WinGet'
    Invoke-WinGetInstall -PackageId 'Microsoft.IIS.URLRewriteModule'
    Invoke-WinGetInstall -PackageId 'Microsoft.IIS.ApplicationRequestRouting'

    Write-Step 'Restarting IIS'
    Invoke-Native -FilePath 'iisreset' -ArgumentList @('/restart') | Out-Null
}

# ---------------------------------------------------------------------------
# Phase C: HTTPS certificate
# ---------------------------------------------------------------------------

function Import-HttpsCertificate {
    Write-Step 'Importing HTTPS certificate'

    Import-Module WebAdministration -ErrorAction Stop
    $existingSsl = Get-Item -LiteralPath 'IIS:\SslBindings\0.0.0.0!443' -ErrorAction SilentlyContinue
    if ($existingSsl) {
        Write-Warning ("An HTTPS binding already exists on 0.0.0.0:443 (thumbprint $($existingSsl.Thumbprint)); skipping cert import. Pass -Force to replace it.")
        if (-not $Force) {
            $script:SkippedPhases.Add('Phase C (HTTPS certificate already bound)') | Out-Null
            return
        }
    }

    $pfxPath = Read-Host 'Path to .pfx certificate file'
    if (-not (Test-Path -LiteralPath $pfxPath)) {
        throw "PFX file not found: $pfxPath"
    }
    $pfxPwd = Read-Host -AsSecureString 'PFX password'

    $cert = Import-PfxCertificate `
        -FilePath $pfxPath `
        -CertStoreLocation 'Cert:\LocalMachine\My' `
        -Password $pfxPwd `
        -ErrorAction Stop
    Write-Info "Imported certificate; thumbprint = $($cert.Thumbprint)"

    Import-Module WebAdministration -ErrorAction Stop

    $site = 'Default Web Site'
    $existingBinding = Get-WebBinding -Name $site -Protocol https -Port 443 `
        -ErrorAction SilentlyContinue
    if (-not $existingBinding) {
        Write-Info "Creating https binding on port 443 for '$site'"
        New-WebBinding -Name $site -Protocol https -Port 443 -IPAddress '*' | Out-Null
    } else {
        Write-Info 'HTTPS binding on port 443 already present'
    }

    $sslPath = 'IIS:\SslBindings\0.0.0.0!443'
    if (Test-Path -LiteralPath $sslPath) {
        Write-Info "Replacing existing SSL binding at $sslPath"
        Remove-Item -LiteralPath $sslPath -Force
    }
    New-Item -Path $sslPath -Thumbprint $cert.Thumbprint -SSLFlags 0 | Out-Null
    Write-Info 'Bound certificate to 0.0.0.0:443'
}

# ---------------------------------------------------------------------------
# Phase D: Reverse-proxy rule
# ---------------------------------------------------------------------------

function Enable-ArrProxy {
    Write-Step 'Enabling Application Request Routing proxy at server level'
    Import-Module WebAdministration -ErrorAction Stop

    $apphost = 'MACHINE/WEBROOT/APPHOST'
    Set-WebConfigurationProperty `
        -PSPath $apphost `
        -Filter 'system.webServer/proxy' `
        -Name 'enabled' `
        -Value 'True' `
        -ErrorAction Stop
    Write-Info 'ARR proxy enabled'
}

function Set-DagsterRewriteRule {
    Write-Step "Configuring URL Rewrite rule 'Dagster Reverse Proxy'"
    Import-Module WebAdministration -ErrorAction Stop

    $sitePath = "IIS:\Sites\Default Web Site"
    $rulesFilter = 'system.webServer/rewrite/rules'
    $ruleName = 'Dagster Reverse Proxy'

    # Remove any existing rule of the same name so the operation is idempotent.
    $existing = Get-WebConfigurationProperty `
        -PSPath $sitePath `
        -Filter "$rulesFilter/rule[@name='$ruleName']" `
        -Name '.' `
        -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Info "Removing existing rule '$ruleName'"
        Clear-WebConfiguration `
            -PSPath $sitePath `
            -Filter "$rulesFilter/rule[@name='$ruleName']" `
            -ErrorAction Stop
    }

    if ([string]::IsNullOrWhiteSpace($PathPrefix)) {
        $matchPattern = '(.*)'
    } else {
        $trimmed = $PathPrefix.Trim('/')
        $matchPattern = "^$trimmed(?:/(.*))?$"
    }
    $rewriteUrl = "http://localhost:$WebserverPort/{R:1}"

    Add-WebConfigurationProperty `
        -PSPath $sitePath `
        -Filter $rulesFilter `
        -Name '.' `
        -Value @{ name = $ruleName; stopProcessing = 'True' } `
        -ErrorAction Stop

    $ruleXPath = "$rulesFilter/rule[@name='$ruleName']"
    Set-WebConfigurationProperty -PSPath $sitePath -Filter "$ruleXPath/match" `
        -Name 'url' -Value $matchPattern
    Set-WebConfigurationProperty -PSPath $sitePath -Filter "$ruleXPath/action" `
        -Name 'type' -Value 'Rewrite'
    Set-WebConfigurationProperty -PSPath $sitePath -Filter "$ruleXPath/action" `
        -Name 'url' -Value $rewriteUrl
    Set-WebConfigurationProperty -PSPath $sitePath -Filter "$ruleXPath/action" `
        -Name 'appendQueryString' -Value 'True'

    Write-Info "Match pattern: $matchPattern"
    Write-Info "Rewrite URL:   $rewriteUrl"
}

# ---------------------------------------------------------------------------
# Phase D2: Clone the ArcGIS Pro arcgispro-py3 environment
# ---------------------------------------------------------------------------

function Get-ArcGisProConda {
    <#
    Resolves the ArcGIS Pro install directory from the registry, then returns
    the bundled conda.exe and the source `arcgispro-py3` env prefix.
    #>
    $regPaths = @(
        'HKLM:\SOFTWARE\ESRI\ArcGISPro',
        'HKCU:\SOFTWARE\ESRI\ArcGISPro'
    )

    $installDir = $null
    foreach ($p in $regPaths) {
        $prop = Get-ItemProperty -Path $p -ErrorAction SilentlyContinue
        if ($prop -and $prop.InstallDir) {
            $installDir = $prop.InstallDir.TrimEnd('\')
            break
        }
    }

    if (-not $installDir) {
        throw 'ArcGIS Pro install directory not found in registry (HKLM:\SOFTWARE\ESRI\ArcGISPro or HKCU). Is ArcGIS Pro installed?'
    }

    $conda  = Join-Path $installDir 'bin\Python\Scripts\conda.exe'
    $srcEnv = Join-Path $installDir 'bin\Python\envs\arcgispro-py3'

    if (-not (Test-Path -LiteralPath $conda)) {
        throw "ArcGIS Pro conda.exe not found at $conda"
    }
    if (-not (Test-Path -LiteralPath $srcEnv)) {
        throw "Source env arcgispro-py3 not found at $srcEnv"
    }

    return [pscustomobject]@{
        InstallDir      = $installDir
        Conda           = $conda
        SourceEnvPrefix = $srcEnv
    }
}

function New-ArcGisProEnvClone {
    Write-Step 'Cloning ArcGIS Pro arcgispro-py3 environment'

    $envPython = Join-Path $CondaEnvPath 'Scripts\python.exe'
    if (Test-Path -LiteralPath $envPython) {
        Write-Warning "Cloned env already present at $CondaEnvPath; skipping clone. Delete the directory manually to force a re-clone."
        return
    }

    if (Test-Path -LiteralPath $CondaEnvPath) {
        throw "$CondaEnvPath exists but does not look like a conda env (no Scripts\python.exe). Remove it manually before re-running."
    }

    $pro = Get-ArcGisProConda
    Write-Info "ArcGIS Pro install: $($pro.InstallDir)"
    Write-Info "Source env:        $($pro.SourceEnvPrefix)"
    Write-Info "Target prefix:     $CondaEnvPath"
    Write-Info 'Cloning the env can take 5–15 minutes and consume several GB of disk space...'

    Invoke-Native -FilePath $pro.Conda -ArgumentList @(
        'create',
        '--prefix', $CondaEnvPath,
        '--clone',  $pro.SourceEnvPrefix,
        '--yes'
    ) | Out-Null

    foreach ($name in @('python.exe', 'pip.exe')) {
        $exe = Join-Path $CondaEnvPath "Scripts\$name"
        if (-not (Test-Path -LiteralPath $exe)) {
            throw "Expected executable not found after clone: $exe"
        }
    }
    Write-Info 'Clone complete.'
}

# ---------------------------------------------------------------------------
# Phase E: pip install dagster
# ---------------------------------------------------------------------------

function Install-DagsterPackages {
    Write-Step "Installing dagster + dagster-webserver into $CondaEnvPath"

    $pip = Join-Path $CondaEnvPath 'Scripts\pip.exe'
    if (-not (Test-Path -LiteralPath $pip)) {
        throw "pip.exe not found at $pip (run without -SkipEnvClone to create the env first)."
    }

    Invoke-Native -FilePath $pip -ArgumentList @(
        'install', '--no-input', 'dagster', 'dagster-webserver'
    ) | Out-Null

    foreach ($exeName in @('dagster.exe', 'dagster-webserver.exe', 'dagster-daemon.exe')) {
        $exe = Join-Path $CondaEnvPath "Scripts\$exeName"
        if (-not (Test-Path -LiteralPath $exe)) {
            throw "Expected executable not found after install: $exe"
        }
        Invoke-Native -FilePath $exe -ArgumentList @('--version') | Out-Null
    }
}

# ---------------------------------------------------------------------------
# Phase F: DAGSTER_HOME + config files
# ---------------------------------------------------------------------------

function Initialize-DagsterHome {
    Write-Step 'Creating DAGSTER_HOME and config files'

    $dirs = @(
        $DagsterHome,
        (Join-Path $DagsterHome 'storage'),
        (Join-Path $DagsterHome 'compute_logs'),
        (Join-Path $ProjectRoot 'reports\logs')
    )
    foreach ($d in $dirs) {
        if (-not (Test-Path -LiteralPath $d)) {
            New-Item -ItemType Directory -Force -Path $d | Out-Null
            Write-Info "Created $d"
        }
    }

    # Escape backslashes for embedding inside double-quoted YAML strings.
    $storageEsc      = (Join-Path $DagsterHome 'storage')      -replace '\\', '\\'
    $computeLogsEsc  = (Join-Path $DagsterHome 'compute_logs') -replace '\\', '\\'

    $dagsterYaml = @"
storage:
  sqlite:
    base_dir: "$storageEsc"

compute_logs:
  local_directory:
    base_dir: "$computeLogsEsc"
"@

    $workspaceYaml = @"
load_from:
  - python_file:
      relative_path: "../scripts/dagster_definitions.py"
      attribute: defs
"@

    Write-YamlFile -Path (Join-Path $DagsterHome 'dagster.yaml')   -Body $dagsterYaml
    Write-YamlFile -Path (Join-Path $DagsterHome 'workspace.yaml') -Body $workspaceYaml

    $defsFile = Join-Path $ProjectRoot 'scripts\dagster_definitions.py'
    if (-not (Test-Path -LiteralPath $defsFile)) {
        Write-Warning "Expected definitions file not found: $defsFile (committed source per setup doc sec. 4)"
    }
}

function Write-YamlFile {
    param(
        [Parameter(Mandatory)][string] $Path,
        [Parameter(Mandatory)][string] $Body
    )
    if ((Test-Path -LiteralPath $Path) -and -not $Force) {
        Write-Info "$Path already exists; leaving in place (use -Force to overwrite)"
        return
    }
    Set-Content -LiteralPath $Path -Value $Body -Encoding UTF8 -NoNewline:$false
    Write-Info "Wrote $Path"
}

# ---------------------------------------------------------------------------
# Phase G: Servy install + service creation
# ---------------------------------------------------------------------------

function Install-Servy {
    Write-Step 'Installing Servy via WinGet'
    Invoke-WinGetInstall -PackageId 'servy'

    # WinGet adds Servy to PATH at the system level, but the current process
    # inherited the pre-install PATH. Refresh from the registry so servy-cli
    # is callable without a new shell.
    Update-PathFromRegistry

    if (-not (Test-Command -Name 'servy-cli')) {
        $fallback = Join-Path ${env:ProgramFiles} 'Servy\servy-cli.exe'
        if (Test-Path -LiteralPath $fallback) {
            $servyDir = Split-Path -Parent $fallback
            $env:Path = "$env:Path;$servyDir"
            Write-Info "Added $servyDir to PATH for current session"
        } else {
            throw 'servy-cli was not found on PATH after install. Open a new elevated PowerShell session and re-run.'
        }
    }
    Write-Info ('servy-cli located: ' + (Get-Command servy-cli).Source)
}

function Test-ServyServiceExists {
    param([Parameter(Mandatory)][string] $Name)
    $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
    return [bool] $svc
}

function Install-ServyService {
    param(
        [Parameter(Mandatory)][string]   $Name,
        [Parameter(Mandatory)][string]   $DisplayName,
        [Parameter(Mandatory)][string]   $Description,
        [Parameter(Mandatory)][string]   $ExePath,
        [Parameter(Mandatory)][string]   $Params,
        [Parameter()][string[]]          $Deps = @()
    )

    if (Test-ServyServiceExists -Name $Name) {
        if ($ReinstallServices) {
            Write-Info "Uninstalling existing service '$Name'"
            Invoke-Native -FilePath 'servy-cli' -ArgumentList @(
                'uninstall', '--name', $Name, '-q'
            ) | Out-Null
        } else {
            Write-Warning "Service '$Name' already exists; leaving in place. Pass -ReinstallServices to recreate it."
            $script:SkippedPhases.Add("Service install: $Name (already exists)") | Out-Null
            return
        }
    }

    $logsDir = Join-Path $ProjectRoot 'reports\logs'
    $stdout  = Join-Path $logsDir ($Name.ToLower() + '_stdout.log')
    $stderr  = Join-Path $logsDir ($Name.ToLower() + '_stderr.log')
    $envVars = "DAGSTER_HOME=$DagsterHome;PROJECT_ENV=prod"

    $args = @(
        'install',
        '--name',              $Name,
        '--displayName',       $DisplayName,
        '--description',       $Description,
        '--path',              $ExePath,
        '--startupDir',        $ProjectRoot,
        '--params',            $Params,
        '--startupType',       'Automatic',
        '--stdout',            $stdout,
        '--stderr',            $stderr,
        '--enableDateRotation',
        '--dateRotationType',  'Daily',
        '--maxRotations',      '14',
        '--enableHealth',
        '--heartbeatInterval', '30',
        '--maxFailedChecks',   '3',
        '--recoveryAction',    'RestartService',
        '--maxRestartAttempts','2',
        '--envVars',           $envVars,
        '-q'
    )

    if ($Deps.Count -gt 0) {
        $args += '--deps'
        $args += ($Deps -join ';')
    }

    Write-Info "Installing service '$Name'"
    Invoke-Native -FilePath 'servy-cli' -ArgumentList $args | Out-Null
}

function Install-DagsterServices {
    Write-Step 'Creating Dagster Windows services via Servy'

    $webserverExe = Join-Path $CondaEnvPath 'Scripts\dagster-webserver.exe'
    $daemonExe    = Join-Path $CondaEnvPath 'Scripts\dagster-daemon.exe'
    $workspace    = Join-Path $DagsterHome 'workspace.yaml'

    foreach ($p in @($webserverExe, $daemonExe, $workspace)) {
        if (-not (Test-Path -LiteralPath $p)) {
            throw "Required path not found: $p"
        }
    }

    $webParams = "-w `"$workspace`" -h 0.0.0.0 -p $WebserverPort"
    if ($PathPrefix) {
        $webParams += " --path-prefix $PathPrefix"
    }

    Install-ServyService `
        -Name        'DagsterWebserver' `
        -DisplayName 'Dagster Webserver' `
        -Description 'Dagster web UI for the ArcPy orchestration project.' `
        -ExePath     $webserverExe `
        -Params      $webParams

    Install-ServyService `
        -Name        'DagsterDaemon' `
        -DisplayName 'Dagster Daemon' `
        -Description 'Dagster schedule and sensor daemon for the ArcPy orchestration project.' `
        -ExePath     $daemonExe `
        -Params      "run -w `"$workspace`"" `
        -Deps        @('DagsterWebserver')

    Write-Step 'Starting Dagster services'
    foreach ($svcName in @('DagsterWebserver', 'DagsterDaemon')) {
        $svc = Get-Service -Name $svcName -ErrorAction SilentlyContinue
        if ($svc -and $svc.Status -eq 'Running') {
            Write-Info "$svcName is already running; skipping start."
            continue
        }
        Invoke-Native -FilePath 'servy-cli' -ArgumentList @('start', '--name', $svcName, '-q') | Out-Null
    }
}

# ---------------------------------------------------------------------------
# Phase H: enable schedule
# ---------------------------------------------------------------------------

function Enable-DagsterSchedule {
    Write-Step "Enabling Dagster schedule '$ScheduleName'"

    $dagsterExe = Join-Path $CondaEnvPath 'Scripts\dagster.exe'
    if (-not (Test-Path -LiteralPath $dagsterExe)) {
        throw "dagster.exe not found at $dagsterExe"
    }

    $env:DAGSTER_HOME = $DagsterHome

    # 'schedule start' may exit non-zero if already running; tolerate by
    # capturing output and inspecting for the known idempotent message.
    $output = & $dagsterExe schedule start $ScheduleName 2>&1
    $code = $LASTEXITCODE
    $output | ForEach-Object { Write-Info $_ }

    if ($code -ne 0) {
        $combined = ($output | Out-String)
        if ($combined -match 'already running' -or $combined -match 'already started') {
            Write-Info 'Schedule is already running; treating as success.'
        } else {
            throw "dagster schedule start exited $code"
        }
    }
}

# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------

function Write-Summary {
    Write-Step 'Setup complete'

    foreach ($name in @('DagsterWebserver', 'DagsterDaemon')) {
        $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
        if ($svc) {
            Write-Host ("    {0,-20} {1}" -f $name, $svc.Status)
        } else {
            Write-Host ("    {0,-20} (not installed)" -f $name)
        }
    }

    $hostname = [System.Net.Dns]::GetHostName()
    $url = "https://$hostname/" + ($PathPrefix.TrimStart('/'))
    Write-Host ''
    Write-Host "    Dagster URL: $url"
    Write-Host "    Logs:        $(Join-Path $ProjectRoot 'reports\logs')"
    Write-Host "    DAGSTER_HOME: $DagsterHome"

    if ($script:SkippedPhases.Count -gt 0) {
        Write-Host ''
        Write-Host '    Skipped phases:' -ForegroundColor Yellow
        foreach ($p in $script:SkippedPhases) {
            Write-Host "      - $p" -ForegroundColor Yellow
        }
    }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

try {
    Assert-Prerequisites

    if ($SkipIIS) {
        Write-Skip 'Phase B (IIS features + URL Rewrite + ARR)'
        Write-Skip 'Phase D (reverse-proxy rule)'
    } else {
        Enable-IISFeatures
        Install-IISProxyModules
    }

    if ($SkipCert) {
        Write-Skip 'Phase C (HTTPS certificate import + binding)'
    } else {
        Import-HttpsCertificate
    }

    if (-not $SkipIIS) {
        Enable-ArrProxy
        Set-DagsterRewriteRule
    }

    if ($SkipEnvClone) {
        Write-Skip 'Phase D2 (clone arcgispro-py3 conda env)'
    } else {
        New-ArcGisProEnvClone
    }

    if ($SkipDagsterInstall) {
        Write-Skip 'Phase E (pip install dagster + dagster-webserver)'
    } else {
        Install-DagsterPackages
    }

    Initialize-DagsterHome

    if ($SkipServy) {
        Write-Skip 'Phase G (Servy install + service creation)'
    } else {
        Install-Servy
        Install-DagsterServices
    }

    if ($SkipScheduleEnable -or $SkipServy) {
        if ($SkipScheduleEnable) {
            Write-Skip 'Phase H (enable Dagster schedule)'
        }
    } else {
        Enable-DagsterSchedule
    }

    Write-Summary
}
catch {
    Write-Host ''
    Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    if ($_.ScriptStackTrace) {
        Write-Host $_.ScriptStackTrace -ForegroundColor DarkRed
    }
    exit 1
}
