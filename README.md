# ArcPy Orchestration

<!--start-->
Web-based Python script orchestration with access to an ArcPy environment through ArcGIS Pro.

## Executive Summary

Spatial analysts routinely build ArcPy workflows that need to run on a
schedule, survive reboots, and be monitored without remoting onto the server
each morning. This project is a reference implementation showing how to do
that with off-the-shelf, open-source components combined with ArcGIS Pro.

**What it delivers**

- A working ArcPy data pipeline (parcels within walking distance of a public
  park, summarized to an Excel workbook) that runs end-to-end on real Thurston
  County, WA open data.
- A web-based orchestration UI built on **[Dagster](https://dagster.io/)** —
  webserver + daemon split with first-class scheduling, sensors, and run
  observability. The UI lists pipelines, exposes a "run now" button, schedules
  recurring runs, and streams live logs to the browser.
- A deployment recipe — IIS as the HTTPS-terminating reverse proxy, Servy as
  the Windows-service wrapper — for hosting Dagster as a managed background
  service on any Windows server with ArcGIS Pro installed.
- A reusable Python package (`arcpy_orchestration`) demonstrating project
  conventions for logging, configuration, CRS handling, temporary-FGDB
  management, and integration with Dagster. Logs from any package module
  automatically surface in the Dagster UI for the active run.

**Who it is for**

- GIS managers evaluating how to move ArcPy work off analyst desktops and
  into a monitored, scheduled, multi-user environment.
- Developers looking for a concrete, opinionated example of structuring an
  ArcPy codebase for production use rather than ad-hoc scripting.

**Getting started**: production deployment of this project is a multi-step
process — it provisions IIS as an HTTPS reverse proxy, clones the ArcGIS Pro
`arcgispro-py3` conda environment, installs Dagster into the clone, and
registers the `dagster-webserver` and `dagster-daemon` processes as Windows
services via Servy. The complete walkthrough lives in
[`docsrc/mkdocs/dagster_setup_instructions.md`](docsrc/mkdocs/dagster_setup_instructions.md).
Additionally, an automated PowerShell installer 
([`scripts/setup_dagster.ps1`](scripts/setup_dagster.ps1))is included, which 
performs the same steps end-to-end on an elevated (administrator) PowerShell 
session.
<!--end-->

<p><small>Project based on the <a target="_blank" href="https://github.com/knu2xs/cookiecutter-geoai">cookiecutter 
GeoAI project template</a>. This template, in turn, is simply an extension and light modification of the 
<a target="_blank" href="https://drivendata.github.io/cookiecutter-data-science/">cookiecutter data science project 
template</a>. #cookiecutterdatascience</small></p>
