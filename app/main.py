"""FastAPI application: form UI + /export endpoint for gf2map."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, ValidationError

from . import __version__
from .export import to_csv, to_kml
from .geocode import GeocodeError, geocode
from .scraper import search

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("gf2map")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="gf2map", version=__version__)


class ExportRequest(BaseModel):
    address: str = Field(..., min_length=1, max_length=500)
    sort: Literal["best", "rating", "distance"] = "best"
    count: int = Field(25, ge=1, le=50)
    format: Literal["csv", "kml"] = "csv"


def _safe_filename(address: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", address.strip())
    s = s.strip("_")
    return s.lower()[:60] or "export"


def _render_form(
    request: Request,
    *,
    error: Optional[str] = None,
    address: str = "",
    sort: str = "best",
    count: int = 25,
    fmt: str = "csv",
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "error": error,
            "address": address,
            "sort": sort,
            "count": count,
            "fmt": fmt,
            "version": __version__,
        },
        status_code=status_code,
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return _render_form(request)


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"ok": True})


@app.post("/export")
def export(
    request: Request,
    address: str = Form(...),
    sort: str = Form("best"),
    count: int = Form(25),
    format: str = Form("csv"),
) -> Response:
    try:
        req = ExportRequest(
            address=address, sort=sort, count=count, format=format
        )
    except ValidationError as e:
        msg = "; ".join(err.get("msg", "invalid input") for err in e.errors())
        return _render_form(
            request,
            error=f"Invalid input: {msg}",
            address=address,
            sort=sort if sort in ("best", "rating", "distance") else "best",
            count=count if isinstance(count, int) else 25,
            fmt=format if format in ("csv", "kml") else "csv",
            status_code=400,
        )

    with httpx.Client() as client:
        try:
            lat, lng = geocode(req.address, client=client)
        except GeocodeError as e:
            logger.warning("Geocode failed for %r: %s", req.address, e)
            return _render_form(
                request,
                error=str(e),
                address=req.address,
                sort=req.sort,
                count=req.count,
                fmt=req.format,
                status_code=400,
            )

        try:
            results = search(
                lat=lat,
                lng=lng,
                address=req.address,
                sort=req.sort,
                count=req.count,
                client=client,
            )
        except httpx.HTTPError as e:
            logger.exception("FMGF fetch failed")
            return _render_form(
                request,
                error=f"Failed to fetch findmeglutenfree.com: {e}",
                address=req.address,
                sort=req.sort,
                count=req.count,
                fmt=req.format,
                status_code=502,
            )

    logger.info(
        "search address=%r sort=%s count=%d -> %d results",
        req.address,
        req.sort,
        req.count,
        len(results),
    )

    if not results:
        return _render_form(
            request,
            error="No results found for that address.",
            address=req.address,
            sort=req.sort,
            count=req.count,
            fmt=req.format,
            status_code=404,
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base = _safe_filename(req.address)

    if req.format == "csv":
        body = to_csv(results)
        media_type = "text/csv; charset=utf-8"
        filename = f"gf2map_{base}_{timestamp}.csv"
    else:
        body = to_kml(results, document_name=f"gf2map: {req.address}")
        media_type = "application/vnd.google-earth.kml+xml"
        filename = f"gf2map_{base}_{timestamp}.kml"

    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
