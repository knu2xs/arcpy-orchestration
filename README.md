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
- A web-based orchestration UI in two interchangeable flavors — pick whichever
  fits your team:
    - **[Plombery](https://lucafaggianelli.com/plombery/)** — single-process,
      lightweight FastAPI app; minimal moving parts and a fast path to a
      working UI.
    - **[Dagster](https://dagster.io/)** — webserver + daemon split with
      richer scheduling, sensors, and run observability for teams that want
      first-class data-orchestration tooling.

  Both list pipelines, expose a "run now" button, schedule recurring runs,
  and stream live logs to the browser.
- A deployment recipe — IIS as the HTTPS-terminating reverse proxy, Servy as
  the Windows-service wrapper — for hosting either orchestrator as a managed
  background service on any Windows server with ArcGIS Pro installed.
- A reusable Python package (`arcpy_orchestration`) demonstrating project
  conventions for logging, configuration, CRS handling, temporary-FGDB
  management, and integration with both Plombery and Dagster. Logs from any
  package module automatically surface in whichever orchestrator UI is
  active for the run.

**Who it is for**

- GIS managers evaluating how to move ArcPy work off analyst desktops and
  into a monitored, scheduled, multi-user environment.
- Developers looking for a concrete, opinionated example of structuring an
  ArcPy codebase for production use rather than ad-hoc scripting.

**Getting started in five minutes**: clone, `make env`, then run
`python scripts/setup_data.py` to download sample data. From there, pick an
orchestrator:

- **Plombery** — `python scripts/plombery_orchestrator.py`, then open
  [http://localhost:8000](http://localhost:8000). Full deployment instructions
  live under
  [`docsrc/mkdocs/plombery_setup_instructions.md`](docsrc/mkdocs/plombery_setup_instructions.md).
- **Dagster** — set `DAGSTER_HOME` to the project's `dagster_home/` directory,
  then run `dagster dev -f scripts/dagster_definitions.py` and open
  [http://localhost:3000](http://localhost:3000). Full deployment instructions
  live under
  [`docsrc/mkdocs/dagster_setup_instructions.md`](docsrc/mkdocs/dagster_setup_instructions.md).
<!--end-->

<p><small>Project based on the <a target="_blank" href="https://github.com/knu2xs/cookiecutter-geoai">cookiecutter 
GeoAI project template</a>. This template, in turn, is simply an extension and light modification of the 
<a target="_blank" href="https://drivendata.github.io/cookiecutter-data-science/">cookiecutter data science project 
template</a>. #cookiecutterdatascience</small></p>
