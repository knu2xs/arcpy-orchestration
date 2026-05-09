You’re very close at this point—what remains is **pure IIS configuration**. Below is a clean, **operator-style checklist** for setting up the reverse proxy from:

    https://yourserver → http://localhost:8000 (Plombery)

***

# ✅ Step-by-Step: Configure IIS Reverse Proxy to Plombery

***

# 🔧 1. Verify prerequisites (quick check)

Before configuring anything, confirm:

*   ✅ IIS installed
*   ✅ URL Rewrite installed
*   ✅ Application Request Routing (ARR) installed
*   ✅ Plombery running at `http://localhost:8000`

👉 ARR relies on URL Rewrite to forward requests, so both must be present [\[Python & GP IRL  \| Meeting\]](https://teams.microsoft.com/l/meeting/details?eventId=AAMkADI0YThmOWU3LTQwNGMtNDYwNC1hYzY4LTJkYzM2YjgwZmFiMQFRAAgI3o64c7vAAEYAAAAAynjQsn7XoESgnp4wv6hM8wcAUYqcv4RooUiM1k-Oy0LmAgAAAUX0UwAA-fcsrAcOuUqv5qbYM6OEDAAHNWbfegAAEA%3d%3d)

***

# 🔧 2. Enable ARR proxy (required, often missed)

This step is **mandatory**.

### In IIS Manager:

1.  Click the **server node** (top level)
2.  Open:
    **Application Request Routing Cache**
3.  On the right, click:
    **Server Proxy Settings**
4.  Check:
        ✅ Enable Proxy
5.  Click **Apply**

👉 ARR must be explicitly enabled to forward requests [\[RivCo + Es...eekly Sync \| Meeting\]](https://teams.microsoft.com/l/meeting/details?eventId=AAMkADI0YThmOWU3LTQwNGMtNDYwNC1hYzY4LTJkYzM2YjgwZmFiMQBGAAAAAADKeNCyftegRKCenjC-qEzzBwBRipy-hGihSIzWT87LQuYCAAABRfRTAAD99yysBw65Sq-mptgzo4QMAAcvAWRbAAA%3d)

***

# 🔧 3. Create (or select) your IIS site

You can use:

*   **Default Web Site**
    OR
*   A new site (recommended for clarity)

### If creating a new site:

*   Site name: `Plombery`
*   Physical path: `C:\inetpub\plombery`
*   Binding:
    *   HTTP: 80 (optional)
    *   HTTPS: 443 (primary)

***

# 🔧 4. Configure HTTPS binding (if not already)

In IIS:

1.  Select your site → **Bindings**
2.  Add/Edit:

<!---->

    Type: https
    Port: 443
    Hostname: plombery.yourdomain.com (optional)
    SSL cert: your certificate

***

# 🔧 5. Create the reverse proxy rule

## ✅ Option A — GUI (recommended first setup)

### In IIS Manager:

1.  Select your site
2.  Open:
    **URL Rewrite**
3.  Click:
    **Add Rule(s)…**
4.  Choose:
    **Reverse Proxy**

👉 This template is built specifically for ARR scenarios [\[ArcGIS Notebooks \| PowerPoint\]](https://esriis.sharepoint.com/teams/GlobalNG/_layouts/15/Doc.aspx?sourcedoc=%7B0799CB73-294E-4633-8009-02808DCC4C49%7D&file=ArcGIS%20Notebooks.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)

***

### Configure:

*   Backend server:
        localhost:8000

*   If prompted:
        ✅ Enable SSL offloading (checked)

👉 This creates the rewrite rule automatically

***

## ✅ Option B — Manual rule (your case for scripting)

Edit `web.config` in your site root:

```xml
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="ReverseProxyToPlombery" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite" url="http://localhost:8000/{R:1}" />
        </rule>
      </rules>
    </rewrite>
  </system.webServer>
</configuration>
```

👉 This rule forwards all incoming requests to your Plombery backend

***

# 🔧 6. Optional (but recommended): HTTP → HTTPS redirect

Add this rule above your proxy rule:

```xml
<rule name="RedirectToHTTPS" stopProcessing="true">
  <match url="(.*)" />
  <conditions>
    <add input="{HTTPS}" pattern="^OFF$" />
  </conditions>
  <action type="Redirect" url="https://{HTTP_HOST}/{R:1}" redirectType="Permanent" />
</rule>
```

***

# 🔧 7. Restart IIS

```cmd
iisreset
```

***

# ✅ 8. Test end-to-end

## Local test

    https://localhost

## Expected result:

*   Loads Plombery UI
*   No redirect loops
*   No 502 errors

***

# ✅ Troubleshooting (very relevant for your setup)

## ❌ 502.3 Bad Gateway

👉 Usually means:

*   Plombery NOT running
*   Wrong port
*   Firewall blocking localhost

***

## ❌ Blank page / partial UI

👉 Often:

*   Missing rewrite rule
*   Static assets not proxied correctly

***

## ❌ Proxy not working at all

👉 Check:

*   ARR proxy **enabled**
*   URL Rewrite rule exists

***

## ❌ Certificate errors

👉 Fix:

*   correct binding
*   trusted cert in LocalMachine store

***

# ✅ Recommended “production tweaks” (important for ArcPy scenarios)

## 🔒 Restrict backend access

Keep:

    --host 127.0.0.1

✅ Ensures Plombery is only reachable through IIS

***

## ⚙️ Increase timeout (ArcPy jobs can be long)

In IIS:

    Site → Advanced Settings → Limits → Connection Timeout → increase

***

## 🔧 Preserve host header (optional but good practice)

Set:

    system.webServer/proxy → preserveHostHeader = True

***

# ✅ Final architecture after setup

    Client → https://server
            ↓
          IIS (443)
            ↓
    Reverse proxy (ARR + URL Rewrite)
            ↓
    Plombery (http://localhost:8000)
            ↓
    ArcPy jobs

***

# ✅ Executive summary

> Once IIS, URL Rewrite, and ARR are installed, configuring a reverse proxy requires enabling ARR proxy mode and creating a URL Rewrite rule that forwards incoming requests to the backend service (Plombery on localhost:8000). HTTPS should be terminated at IIS, providing secure, managed access to the automation service.

***

# 👍 If you want next

I can:

*   Validate your **web.config + bindings**
*   Provide a **health-check endpoint test script**
*   Or give a **troubleshooting checklist specifically for Plombery + ArcPy workloads**

This is a solid enterprise-grade pattern—you’re doing it exactly right.
