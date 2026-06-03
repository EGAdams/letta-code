# Windows 10 Dashboard Operations Guide

## Purpose
This document captures the working process for editing and publishing the live dashboard served from the Windows 10 jewelry machine environment.

## Machines and addressing
- **DESKTOP-SHDBATI (Windows 10 host):** `100.69.80.89`
- **DESKTOP-SHDBATI Linux/WSL endpoint (preferred for automation):** `100.80.49.10`
- **DESKTOP-2OBSQMC (Windows 11 host):** `100.118.122.75`
- **DESKTOP-2OBSQMC Linux/WSL endpoint:** `100.72.158.63`

## Live web paths (Windows 10 environment)
- Apache docroot: `/var/www/html`
- Dashboard page: `/var/www/html/dashboard_spa.html`
- Windows 10 management page: `/var/www/html/windows_10_dashboard_management.html`
- Upload guide page: `/var/www/html/americanjewelry_live_upload_guide.html`

## Permission model
`/var/www/html` is root-owned, so agents should:
1. Build/update files in `/home/adamsl/`
2. Promote with sudo copy into `/var/www/html`

Recommended promotion commands:
```bash
sudo cp /home/adamsl/dashboard_spa.updated.html /var/www/html/dashboard_spa.html
sudo cp /home/adamsl/windows_10_dashboard_management.html /var/www/html/windows_10_dashboard_management.html
sudo cp /home/adamsl/americanjewelry_live_upload_guide.html /var/www/html/americanjewelry_live_upload_guide.html
```

## Link behavior rule
The dashboard instructions tab must use **context-aware links**:
- On jewelry domain deployment, links may target jewelry-domain pages.
- On temporary Cloudflare deployment (`*.trycloudflare.com`), links should be **relative links** so they stay on that temporary host.

Example (Cloudflare-safe):
```html
<a href="/americanjewelry_live_upload_guide.html">...</a>
<a href="/windows_10_dashboard_management.html">...</a>
```

## Cloudflare quick tunnel notes
- Quick tunnels are temporary and can rotate URLs.
- Validate tunnel domain resolves and origin port is reachable.
- Common failure: tunnel points to wrong local port (for example `localhost:80` when service is on `8080`).

## Verification checklist after each publish
1. Confirm files exist in `/var/www/html`.
2. Open dashboard and click **Instructions**.
3. Confirm both instruction links are clickable and load content.
4. Confirm no accidental cross-machine links.
5. If testing via Cloudflare URL, verify relative link targets return HTTP 200.
