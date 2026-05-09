Great question—this is exactly where people either **over-install IIS** or miss one critical checkbox and spend an hour troubleshooting ARR 😄

Here’s the **clean, minimal set of Windows Features** you actually need to enable in **“Turn Windows features on or off”** (or Server Manager → Add Roles and Features) for **IIS reverse proxy → Plombery**.

***

# ✅ ✅ Minimum Required IIS Features

## ✅ 1. Web Server (IIS)

**Must be enabled**

### Under **World Wide Web Services → Common HTTP Features**

✅ Enable:

*   ✔ Default Document
*   ✔ Static Content
*   ✔ HTTP Errors

👉 These are part of the base IIS site hosting.

***

## ✅ 2. Application Development Features

👉 This is the most important section people miss.

Enable:

*   ✔ **ISAPI Extensions**
*   ✔ **ISAPI Filters**

👉 These are explicitly required for ARR / reverse proxy scenarios [\[docs.microfocus.com\]](https://docs.microfocus.com/doc/SiteScope/24.4/IISReverseProxyARR)

***

## ✅ 3. Management Tools

Enable:

*   ✔ IIS Management Console

👉 Needed to configure reverse proxy rules in IIS Manager

***

# ✅ ⚠️ Optional but Recommended (safe defaults)

## ✔ Security

*   Basic Authentication (optional)
*   Windows Authentication (if internal environment)

***

## ✔ Health and Diagnostics

*   HTTP Logging

***

## ✔ Performance Features

*   Static Content Compression (nice-to-have)

***

# ❗ What you do NOT need

You **do NOT need**:

*   ASP.NET (unless hosting .NET apps)
*   .NET Extensibility
*   WebSockets (unless your backend uses it)
*   IIS CGI (not needed for reverse proxy to Python)
*   FTP Server

👉 Even though some docs mention ASP.NET as a prerequisite, that’s for **example apps**, not ARR itself [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/iis/extensions/url-rewrite-module/reverse-proxy-with-url-rewrite-v2-and-application-request-routing)

***

# ✅ Critical components NOT in Windows Features

This is where many setups fail 👇

These are **NOT in “Turn Windows Features”** and must be installed separately:

## 🔌 Required Extensions

You must install:

*   **URL Rewrite Module**
*   **Application Request Routing (ARR)**

👉 ARR depends on URL Rewrite to route requests [\[learn.microsoft.com\]](https://learn.microsoft.com/en-us/iis/extensions/planning-for-arr/using-the-application-request-routing-module)

***

# ✅ Final “Checklist View” (what to actually enable)

## ✅ In Windows Features:

    ☑ Internet Information Services
      ☑ Web Management Tools
        ☑ IIS Management Console

      ☑ World Wide Web Services
        ☑ Common HTTP Features
          ☑ Default Document
          ☑ Static Content
          ☑ HTTP Errors

        ☑ Application Development Features
          ☑ ISAPI Extensions
          ☑ ISAPI Filters

***

## ✅ Then install separately:

*   URL Rewrite (v2+)
*   Application Request Routing (ARR)

***

# 🧠 Practical tip (this saves real time)

If you want to avoid guessing entirely:

👉 The **safe enterprise pattern** is:

> Install IIS with defaults → add ISAPI Extensions + Filters → install URL Rewrite + ARR

Everything else is optional.

***

# ✅ How to verify it's set up correctly

After install, open **IIS Manager**, and confirm you see:

*   ✅ “URL Rewrite”
*   ✅ “Application Request Routing Cache”

If both are present → ✅ you’re good to go

***

# ✅ Bottom line

> The only IIS features you *must explicitly enable* for reverse proxy are **ISAPI Extensions and ISAPI Filters**, while URL Rewrite and ARR must be installed separately to provide the actual proxy capability.

***

If you want, I can give you:

*   a **single PowerShell command that installs exactly these features**
*   or a **pre-flight validation script** to confirm everything is ready before deployment
