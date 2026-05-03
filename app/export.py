"""CSV and KML export writers for Google My Maps."""
from __future__ import annotations

import csv
import io
from html import escape as html_escape
from typing import Iterable, List
from xml.sax.saxutils import escape as xml_escape

from .scraper import Restaurant


def _description_lines(r: Restaurant) -> List[str]:
    """Plain-text multi-line description, skipping missing fields."""
    lines: List[str] = []
    if r.rating_stars is not None:
        rc = f" ({r.rating_count} reviews)" if r.rating_count is not None else ""
        lines.append(f"Rating: {r.rating_stars}/5{rc}")
    if r.safety_rating is not None:
        sc = (
            f" ({r.safety_rating_count} ratings)"
            if r.safety_rating_count is not None
            else ""
        )
        desc = f" - {r.safety_rating_description}" if r.safety_rating_description else ""
        lines.append(f"Safety: {r.safety_rating}/5{sc}{desc}")
    if r.tags:
        lines.append(r.tags)
    if r.gf_menu_items:
        lines.append(f"GF Menu: {r.gf_menu_items}")
    if r.featured_review:
        lines.append(f'Featured: "{r.featured_review}"')
    if r.distance:
        lines.append(f"Distance: {r.distance}")
    lines.append("")
    lines.append(f"More info: {r.fmgf_url}")
    return lines


def to_csv(restaurants: Iterable[Restaurant]) -> bytes:
    """Render restaurants as Google My Maps-compatible CSV (UTF-8 BOM)."""
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL)
    writer.writerow(["Name", "Address", "Description", "URL"])
    for r in restaurants:
        description = "\n".join(_description_lines(r))
        writer.writerow([
            r.name,
            r.address or "",
            description,
            r.fmgf_url,
        ])
    return buf.getvalue().encode("utf-8-sig")


def _description_html(r: Restaurant) -> str:
    """Rich HTML description for KML <description> CDATA."""
    parts: List[str] = []
    if r.rating_stars is not None:
        rc = (
            f" ({r.rating_count} reviews)" if r.rating_count is not None else ""
        )
        parts.append(f"<p><b>Rating:</b> {r.rating_stars}/5{html_escape(rc)}</p>")
    if r.safety_rating is not None:
        sc = (
            f" ({r.safety_rating_count} ratings)"
            if r.safety_rating_count is not None
            else ""
        )
        desc = (
            f" &mdash; {html_escape(r.safety_rating_description)}"
            if r.safety_rating_description
            else ""
        )
        parts.append(
            f"<p><b>Safety:</b> {r.safety_rating}/5{html_escape(sc)}{desc}</p>"
        )
    if r.tags:
        parts.append(f"<p>{html_escape(r.tags)}</p>")
    if r.gf_menu_items:
        parts.append(f"<p><b>GF Menu:</b> {html_escape(r.gf_menu_items)}</p>")
    if r.featured_review:
        parts.append(
            f"<p><i>&ldquo;{html_escape(r.featured_review)}&rdquo;</i></p>"
        )
    if r.distance:
        parts.append(f"<p><b>Distance:</b> {html_escape(r.distance)}</p>")
    parts.append(
        f'<p><a href="{html_escape(r.fmgf_url)}">View on findmeglutenfree.com</a></p>'
    )
    return "".join(parts)


def to_kml(restaurants: Iterable[Restaurant], *, document_name: str = "gf2map") -> bytes:
    """Render restaurants as KML 2.2 with one Placemark per restaurant."""
    out: List[str] = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append('<kml xmlns="http://www.opengis.net/kml/2.2">')
    out.append("  <Document>")
    out.append(f"    <name>{xml_escape(document_name)}</name>")
    for r in restaurants:
        out.append("    <Placemark>")
        out.append(f"      <name>{xml_escape(r.name)}</name>")
        if r.address:
            out.append(f"      <address>{xml_escape(r.address)}</address>")
        # CDATA-wrapped HTML description. Guard the unlikely "]]>" sequence.
        html = _description_html(r).replace("]]>", "]]]]><![CDATA[>")
        out.append(f"      <description><![CDATA[{html}]]></description>")
        out.append("    </Placemark>")
    out.append("  </Document>")
    out.append("</kml>")
    return ("\n".join(out) + "\n").encode("utf-8")
