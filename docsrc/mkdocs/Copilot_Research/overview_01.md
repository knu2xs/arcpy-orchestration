Short answer: **don’t run Plombery directly on port 443 in Windows**—the reliable pattern is to:

> ✅ Run Plombery on a high port (e.g., 8000)  
> ✅ Put a Windows-native HTTPS front-end (IIS or reverse proxy) on port 443  
> ✅ Run everything as a Windows service

Below is a **practical, production-ready pattern** that works well for ArcPy automation.

***

# ✅ Recommended Architecture (Windows-friendly)

    [ Internet / Users ]
            ↓ https :443
         IIS (or reverse proxy)
            ↓ http :8000
       Plombery (FastAPI/Uvicorn backend)
            ↓
       ArcPy scripts

### Why this pattern:

*   Python apps (Plombery → FastAPI/Uvicorn) are **not ideal for direct 443 binding**
*   Windows + HTTPS is best handled by **IIS**
*   You avoid:
    *   certificate handling complexity in Python
    *   privilege issues (port 443 requires admin)
*   You gain:
    *   proper TLS termination
    *   central cert management
    *   easier ops

***

# 🔧 Step-by-Step Implementation

## 1️⃣ Install and run Plombery (internal port)

```bash
pip install plombery
plombery run --host 127.0.0.1 --port 8000
```

👉 Plombery runs a FastAPI backend + web UI [\[deepwiki.com\]](https://deepwiki.com/lucafaggianelli/plombery)

***

## 2️⃣ Convert Plombery to a Windows service (persistent)

**Best option: NSSM (Non-Sucking Service Manager)**

```bash
nssm install Plombery
```

Configure:

*   Path: `python.exe`
*   Arguments: `-m plombery run --host 127.0.0.1 --port 8000`
*   Startup: Automatic

👉 Running Python as a Windows service ensures it survives logouts and runs continually [\[sqlpey.com\]](https://sqlpey.com/python/effective-methods-for-running-python-scripts-as-windows-services/)

***

## 3️⃣ Set up IIS as HTTPS front-end (port 443)

### Install IIS features:

*   Web Server (IIS)
*   URL Rewrite (recommended)
*   ARR (Application Request Routing)

***

### Create HTTPS binding

```powershell
New-WebBinding -Name "Default Web Site" -Protocol https -Port 443
```

👉 IIS supports port 443 HTTPS bindings with certificates [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/powershell/module/webadministration/new-webbinding?view=windowsserver2025-ps)

***

### Assign SSL certificate

*   Import cert into:  
    `Cert:\LocalMachine\My`
*   Bind to IIS site

👉 IIS uses certificate store + bindings for HTTPS [\[shellgeek.com\]](https://shellgeek.com/powershell-bind-certificate-to-iis-site/)

***

## 4️⃣ Configure reverse proxy (critical step)

In IIS:

*   Enable ARR proxy
*   Add URL Rewrite rule:

<!---->

    Match URL: (.*)
    Rewrite to: http://localhost:8000/{R:1}

👉 This forwards HTTPS traffic from IIS → Plombery

***

## 5️⃣ Open firewall port 443

*   Allow inbound TCP 443

👉 Windows blocks inbound ports by default unless explicitly allowed [\[geekchamp.com\]](https://geekchamp.com/how-to-allow-port-443-in-windows-firewall/)

***

# ✅ Alternative (NOT recommended but possible)

You *can* bind Python directly to 443 using SSL:

```python
uvicorn.run(
    app,
    host="0.0.0.0",
    port=443,
    ssl_keyfile="key.pem",
    ssl_certfile="cert.pem"
)
```

👉 Python servers can use SSL cert + key to serve HTTPS directly [\[stackoverflow.com\]](https://stackoverflow.com/questions/69138537/uvicorn-fastapi-python-run-both-http-and-https)

But this approach has issues:

*   Requires admin privileges (port 443)
*   Poor certificate lifecycle management
*   Not ideal for production on Windows

***

# 🧠 Practical guidance (based on your use case)

Given:

*   ArcPy workloads
*   Windows environments
*   Customer deployments
*   Need for reliability

👉 **Use IIS reverse proxy + Plombery**

***

# 💡 Bonus: hardened enterprise pattern

For your consulting scenarios, I’d standardize on:

*   ✅ Dedicated automation VM
*   ✅ ArcGIS Pro (Single Use license)
*   ✅ Plombery (service on port 8000)
*   ✅ IIS (TLS termination on 443)
*   ✅ Domain cert (internal CA or public)
*   ✅ Service account for execution

***

# ✅ Executive summary (what you’d tell a customer)

> Plombery should be deployed as a backend service on a non-privileged port, with IIS providing HTTPS termination on port 443. This ensures secure, persistent operation, simplifies certificate management, and aligns with Windows-native best practices for production deployments.

***

# 👍 If you want next

I can:

*   give you a **copy/paste NSSM + IIS setup script**
*   or a **customer-ready deployment runbook (1–2 pages)**
*   or show how to integrate this with **Active Directory / service accounts for ArcPy execution**