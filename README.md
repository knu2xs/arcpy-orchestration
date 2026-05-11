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
- A web-based orchestration UI ([Plombery](https://lucafaggianelli.com/plombery/))
  that lists pipelines, exposes a "run now" button, schedules recurring runs,
  and streams live logs to the browser.
- A deployment recipe — IIS as the HTTPS-terminating reverse proxy, Servy as
  the Windows-service wrapper — for hosting the orchestrator as a managed
  background service on any Windows server with ArcGIS Pro installed.
- A reusable Python package (`arcpy_orchestration`) demonstrating project
  conventions for logging, configuration, CRS handling, temporary-FGDB
  management, and Plombery integration. Logs from any package module
  automatically surface in the Plombery UI for the active run.

**Who it is for**

- GIS managers evaluating how to move ArcPy work off analyst desktops and
  into a monitored, scheduled, multi-user environment.
- Developers looking for a concrete, opinionated example of structuring an
  ArcPy codebase for production use rather than ad-hoc scripting.

**Getting started in five minutes**: clone, `make env`, run
`python scripts/setup_data.py` to download sample data, then
`python scripts/plombery_orchestrator.py` and open
[http://localhost:8000](http://localhost:8000). Full deployment instructions
live under [`docsrc/mkdocs/03_setup.md`](docsrc/mkdocs/03_setup.md).

## Getting Started

1 - Clone this repo.

2 - Create an environment with the requirements.
    
```
        > make env
```

3 - Start Building - If you are more into Python, a good place to start is `jupyter lab` from the root of the project, and 
  start experimenting with Jupyter in the `./notebooks` directory, and move code logic to the `./src` directory. If GIS is 
  more your schtick, open the project `./arcgis/arcpy-orchestration.aprx`.
<!--end-->

<p><small>Project based on the <a target="_blank" href="https://github.com/knu2xs/cookiecutter-geoai">cookiecutter 
GeoAI project template</a>. This template, in turn, is simply an extension and light modification of the 
<a target="_blank" href="https://drivendata.github.io/cookiecutter-data-science/">cookiecutter data science project 
template</a>. #cookiecutterdatascience</small></p>
