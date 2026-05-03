# gf2map

A small personal-use web tool that scrapes
[findmeglutenfree.com](https://www.findmeglutenfree.com) search results and
exports them as CSV or KML so they can be imported into Google My Maps.
Designed to run in Docker behind a Tailscale sidecar so it is only reachable
from your own tailnet.

## Quickstart (Docker + Tailscale)

1. Generate a Tailscale auth key at
   <https://login.tailscale.com/admin/settings/keys>. A reusable, ephemeral,
   pre-approved key works well; tag it (e.g. `tag:gf2map`) if you use ACLs.
2. Configure the environment:
   ```bash
   cp .env.example .env
   # edit .env and set TS_AUTHKEY=tskey-auth-...
   ```
3. Start the stack:
   ```bash
   docker compose up -d
   ```
4. From any device on your tailnet, visit <http://gf2map:8000>.

The `app` container shares the `tailscale` container's network namespace, so
no port is published to the host by default. To debug locally without a
tailnet, uncomment the `ports:` block on the `tailscale` service in
`docker-compose.yml` and visit <http://127.0.0.1:8000>.

## Local development (no Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open <http://localhost:8000>.

## How it works

1. You enter free-form address text (e.g. `Portland, Oregon`).
2. The address is geocoded to lat/lng via the OpenStreetMap
   [Nominatim](https://nominatim.openstreetmap.org/) API. Results are cached
   in-process so repeat searches don't re-hit Nominatim.
3. The corresponding `findmeglutenfree.com/search` page is fetched and
   parsed. Up to 50 results per page are available.
4. The results are exported as CSV (default) or KML and returned as a
   downloadable file.

## Importing into Google My Maps

1. Go to <https://mymaps.google.com/> and create a new map.
2. On a layer, click **Import** and upload your `gf2map_*.csv` file.
3. When prompted, choose:
   - **Address column**: `Address` (Google geocodes this to place pins)
   - **Marker title column**: `Name`
4. Click through. The `Description` column carries ratings, GF menu items
   and a featured review; clicking a pin shows that text. The `URL` column
   links each pin back to its FMGF page.

KML works similarly: choose **Import** and upload the `.kml` file. KML is
useful if you also want to view the data in Google Earth.

## Notes / etiquette

- This is a personal tool, used in moderation. Each export issues one
  request to Nominatim and one request to findmeglutenfree.com.
- Nominatim's
  [usage policy](https://operations.osmfoundation.org/policies/nominatim/)
  requires a descriptive User-Agent (the app sends `gf2map/0.1
  (personal use)`) and asks that you cache results — we do.
- findmeglutenfree.com search pages are publicly visible and their
  `<meta name="robots">` is `noindex,follow`. Be courteous: don't run
  large batch jobs against the site from this tool.
