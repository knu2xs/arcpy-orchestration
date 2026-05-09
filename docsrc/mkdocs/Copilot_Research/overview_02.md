Great—this is a solid approach for a **customer-ready, supportable Windows deployment**, and you can absolutely do it cleanly **without NSSM** by using:

*   ✅ Native Windows Service (via `sc.exe` or scheduled service pattern)
*   ✅ IIS for HTTPS (port 443)
*   ✅ Reverse proxy to Plombery

Below is a **practical, step-by-step runbook** you can drop into an implementation doc.

***

# ✅ Architecture (what you’ll build)

    Windows Server
    ├── IIS (HTTPS :443, certificate-managed)
    │    └── Reverse proxy → http://localhost:8000
    │
    └── Windows Service (plombery via python)
         └── Runs plombery on port 8000
             └── Executes ArcPy scripts

***

# 🔧 Step 1 – Install & validate Plombery locally

```bash
pip install plombery
plombery run --host 127.0.0.1 --port 8000
```

✅ Confirm:

*   <http://localhost:8000> works

***

# 🔧 Step 2 – Create a Windows Service (no NSSM)

You have two solid native options:

***

## ✅ Option A (Recommended): Use `sc.exe` with a wrapper script

Because Plombery runs as a long-running process, create a small launcher.

### 1. Create a startup script

Example: `C:\plombery\start_plombery.bat`

```bat
@echo off
cd /d C:\plombery

REM Activate environment if needed
call C:\Python39\Scripts\activate.bat

python -m plombery run --host 127.0.0.1 --port 8000
```

***

### 2. Create service

```cmd
sc create PlomberyService ^
  binPath= "cmd /c C:\plombery\start_plombery.bat" ^
  start= auto
```

***

### 3. Start service

```cmd
sc start PlomberyService
```

👉 This is leveraging the Windows Service Control Manager  
👉 Python service patterns commonly rely on wrapper scripts or service frameworks [\[Setup Pyth...al testing \| Word\]](https://esriis.sharepoint.com/teams/desktopqa/docs/_layouts/15/Doc.aspx?sourcedoc=%7BB84F8931-A714-482D-96A3-2D4BEF8003B1%7D&file=Setup%20Python%203%20runtime%20for%20ArcGIS%20Server%20on%20Linux%20for%20internal%20testing.docx&action=default&mobileredirect=true&DefaultItemOpen=1)

***

## ✅ Option B (more “pure”): pywin32 Windows Service

If you want a **true service class (cleaner for enterprise)**:

Install:

```bash
pip install pywin32
```

Skeleton:

```python
import win32serviceutil
import win32service
import win32event
import subprocess

class PlomberyService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PlomberyService"
    _svc_display_name_ = "Plombery Scheduler Service"

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        subprocess.call([
            "python",
            "-m", "plombery",
            "run",
            "--host", "127.0.0.1",
            "--port", "8000"
        ])
```

Then install:

```cmd
python service.py install
python service.py start
```

👉 This follows the Windows Service Framework model described in pywin32 guidance [\[Setup Pyth...al testing \| Word\]](https://esriis.sharepoint.com/teams/desktopqa/docs/_layouts/15/Doc.aspx?sourcedoc=%7BB84F8931-A714-482D-96A3-2D4BEF8003B1%7D&file=Setup%20Python%203%20runtime%20for%20ArcGIS%20Server%20on%20Linux%20for%20internal%20testing.docx&action=default&mobileredirect=true&DefaultItemOpen=1)

***

# 🔧 Step 3 – Install and configure IIS (HTTPS)

## 3.1 Install IIS + features

*   Web Server (IIS)
*   URL Rewrite
*   Application Request Routing (ARR)

***

## 3.2 Create HTTPS binding (port 443)

```powershell
New-WebBinding -Name "Default Web Site" -Protocol https -Port 443
```

👉 This creates the HTTPS listener on port 443 [\[ArcGIS Enterprise \| SharePoint\]](https://esriis.sharepoint.com/sites/ProductManagement/SitePages/ArcGIS-Enterprise.aspx?web=1)

***

## 3.3 Bind SSL certificate

```powershell
$cert = Get-ChildItem Cert:\LocalMachine\My\<thumbprint>
$binding = Get-WebBinding -Name "Default Web Site" -Protocol https
$binding.AddSslCertificate($cert.Thumbprint, "My")
```

👉 IIS uses cert store + binding for HTTPS trust [\[2025 Produ...ysis Final \| PDF\]](https://esriis.sharepoint.com/sites/CustomerExperienceHub/Shared%20Documents/2025%20Product%20Survey%20Analysis%20Final.pdf?web=1)

***

# 🔧 Step 4 – Configure reverse proxy (IIS → Plombery)

## Enable ARR proxy:

*   IIS Manager → Server → **Application Request Routing Cache**
*   Enable proxy

***

## Add URL Rewrite rule

**Rule: ReverseProxyToPlombery**

*   Match:

<!---->

    (.*)

*   Action:

<!---->

    Rewrite → http://localhost:8000/{R:1}

***

✅ Result:

*   HTTPS traffic hits IIS on 443
*   IIS forwards to Plombery on 8000

***

# 🔧 Step 5 – Open Firewall Port 443

*   Allow inbound TCP 443

👉 Required because Windows blocks inbound traffic by default [\[9905_ArcGI...ook_Server \| PowerPoint\]](https://esriis.sharepoint.com/sites/DevSummit_Proceedings/_layouts/15/Doc.aspx?sourcedoc=%7B2774E2C9-1D77-4A3D-AF27-8981ED49D995%7D&file=9905_ArcGIS_Notebook_Server_An_Introduction_to_Notebooks_and_Notebook_Server.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)

***

# ✅ Optional Hardening (you’ll want this for customers)

## 🔒 Run service as a service account

*   Create `svc_plombery`
*   Assign:
    *   “Log on as a service”
    *   ArcGIS Pro licensing context (important!)

***

## 🔒 Restrict Plombery to localhost

You already did this:

    --host 127.0.0.1

✅ Ensures it is only accessible through IIS

***

## 🔒 Add IIS Authentication

*   Windows Auth (internal)
*   or OAuth proxy

***

# ✅ Final validation

✅ Confirm:

*   <https://yourserver> works
*   UI loads
*   Plombery runs jobs
*   ArcPy executes successfully

***

# 💡 Practical advice (from PS / Enterprise patterns)

This setup is **exactly what works best** for ArcGIS + Python automation:

*   ✅ IIS handles:
    *   TLS
    *   certificates
    *   exposure to network
*   ✅ Plombery handles:
    *   scheduling
    *   orchestration
*   ✅ Windows Service handles:
    *   persistence

***

# ✅ Executive summary (customer-ready)

> Plombery is deployed as a Windows service running on a local port, with IIS providing HTTPS exposure on port 443 via reverse proxy. This approach ensures secure access, simplifies certificate management, and aligns with enterprise Windows deployment standards while enabling reliable execution of ArcPy-based automation workflows.

***

If you want, I can next:

*   Provide a **one-page customer deployment checklist**
*   Or a **PowerShell script that fully automates IIS + service setup**
