:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
:: LICENSING                                                                    :
:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
::
:: Copyright 2026 Esri
::
:: Licensed under the Apache License, Version 2.0 (the "License"); You
:: may not use this file except in compliance with the License. You may
:: obtain a copy of the License at
::
:: http://www.apache.org/licenses/LICENSE-2.0
::
:: Unless required by applicable law or agreed to in writing, software
:: distributed under the License is distributed on an "AS IS" BASIS,
:: WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
:: implied. See the License for the specific language governing
:: permissions and limitations under the License.
::
:: A copy of the license is available in the repository's
:: LICENSE file.

:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
:: VARIABLES                                                                    :
:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

SETLOCAL
SET PROJECT_DIR=%cd%
SET PROJECT_NAME=arcpy-orchestration
SET SUPPORT_LIBRARY = arcpy_orchestration
SET CONDA_DIR="%~dp0env"

:: Get ArcGIS Pro installation path from registry
FOR /F "tokens=2*" %%A IN ('REG QUERY "HKEY_LOCAL_MACHINE\SOFTWARE\ESRI\ArcGISPro" /v InstallDir 2^>nul') DO SET ARCGIS_PRO_DIR=%%B

:: If registry query fails, fall back to default location
IF NOT DEFINED ARCGIS_PRO_DIR (
    SET ARCGIS_PRO_DIR="C:\Program Files\ArcGIS\Pro"
)

:: Set the ArcGIS Pro Python environment path
SET ARCGIS_PRO_PYTHON="%ARCGIS_PRO_DIR%\bin\Python\envs\arcgispro-py3"

:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
:: COMMANDS                                                                     :
:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

:: Jump to command
GOTO %1

:: Run the data pipeline once, serverless (no Prefect server/worker).
:data
    CALL conda run -p %CONDA_DIR% python scripts/make_data_prefect.py run
    GOTO end

:: Serve Prefect orchestration. Second arg is the action:
::   start-all | start-server | start-worker | serve-flow | show-config  (default: start-all)
:prefect
    SET PREFECT_ACTION=%2
    IF "%PREFECT_ACTION%"=="" SET PREFECT_ACTION=start-all
    IF "%PREFECT_ACTION%"=="start-all" GOTO prefect_all
    CALL conda run --no-capture-output -p %CONDA_DIR% powershell -ExecutionPolicy Bypass -File "%~dp0scripts\setup_prefect.ps1" -Action %PREFECT_ACTION%
    GOTO end

:: Full web-UI experience from one call: launch the server and worker in their own windows,
:: then serve the managed flow in this window. The server hosts the Prefect UI.
:prefect_all
    START "Prefect Server" conda run --no-capture-output -p %CONDA_DIR% powershell -ExecutionPolicy Bypass -File "%~dp0scripts\setup_prefect.ps1" -Action start-server
    START "Prefect Worker" conda run --no-capture-output -p %CONDA_DIR% powershell -ExecutionPolicy Bypass -File "%~dp0scripts\setup_prefect.ps1" -Action start-worker
    SET PREFECT_API_HEALTH_URL=http://127.0.0.1:4200/api/health
    SET PREFECT_API_TIMEOUT_SEC=%PREFECT_API_STARTUP_TIMEOUT_SEC%
    IF "%PREFECT_API_TIMEOUT_SEC%"=="" SET PREFECT_API_TIMEOUT_SEC=90
    SET /A PREFECT_WAIT_ELAPSED=0
    ECHO Waiting for Prefect API at %PREFECT_API_HEALTH_URL% (timeout: %PREFECT_API_TIMEOUT_SEC%s)...

:wait_prefect_api
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%PREFECT_API_HEALTH_URL%' -TimeoutSec 5; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300) { exit 0 } else { exit 1 } } catch { exit 1 }"
    IF %ERRORLEVEL%==0 GOTO prefect_serve_flow
    IF %PREFECT_WAIT_ELAPSED% GEQ %PREFECT_API_TIMEOUT_SEC% GOTO prefect_api_timeout
    TIMEOUT /T 2 /NOBREAK >NUL
    SET /A PREFECT_WAIT_ELAPSED+=2
    GOTO wait_prefect_api

:prefect_serve_flow
    ECHO Prefect API is reachable.
    CALL conda run --no-capture-output -p %CONDA_DIR% powershell -ExecutionPolicy Bypass -File "%~dp0scripts\setup_prefect.ps1" -Action serve-flow
    GOTO end

:prefect_api_timeout
    ECHO ERROR: Prefect API did not become reachable at %PREFECT_API_HEALTH_URL% within %PREFECT_API_TIMEOUT_SEC%s.
    EXIT /B 1

:: Delete all compiled Python files
:clean
    FOR /R %%f IN (*.pyc *.pyo) DO DEL /Q "%%f" 2>nul
    FOR /D /R %%d IN (__pycache__) DO IF EXIST "%%d" RD /S /Q "%%d"
    GOTO end

:: Make documentation using MkDocs!
:docs
    CALL conda run --no-capture-output -p %CONDA_DIR% mkdocs build -f ./docsrc/mkdocs.yml
    GOTO end

:: MkDocs live documentation server
:docserve
    CALL conda run --no-capture-output -p %CONDA_DIR% mkdocs serve -f ./docsrc/mkdocs.yml
    GOTO end

:: Build the local environment by cloning the ArcGIS Pro Python env
:env
    :: Create new environment by cloning the ArcGIS Pro environment
    CALL conda create -p %CONDA_DIR% --clone %ARCGIS_PRO_PYTHON% -y
    GOTO add_dependencies

:: Install the local package (with dev and mkdocs extras) into the project environment
:add_dependencies

    :: Install the local package in editable mode with dev and mkdocs extras
    CALL conda run -p %CONDA_DIR% python -m pip install -e .[dev,mkdocs]

    GOTO end

:: Initialize SpecKit in the project
:speckit
    CALL specify init --here
    GOTO end

:: Start Jupyter Label
:jupyter
    CALL conda run -p %CONDA_DIR% python -m jupyterlab --ip=0.0.0.0 --allow-root --NotebookApp.token=""
    GOTO end

:: Make *.pyt zipped archive with requirements
:pytzip
    CALL conda run -p %CONDA_DIR% python -m scripts/make_pyt_archive.py
    GOTO end

:: Make the package for uploading
:wheel

    :: Build the pip package
    CALL conda run -p %CONDA_DIR% python -m build --wheel

    GOTO end

:: Run all tests in module
:test
	CALL conda run -p %CONDA_DIR% pytest "%~dp0testing"
	GOTO end

:: black formatting
:black
    CALL conda run -p %CONDA_dIR% black src/ --verbose
    GOTO end

:lint
    GOTO black

:linter
    GOTO black

:end
    EXIT /B
