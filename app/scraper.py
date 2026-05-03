"""findmeglutenfree.com search scraper."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

FMGF_SEARCH_URL = "https://www.findmeglutenfree.com/search"
FMGF_BASE_URL = "https://www.findmeglutenfree.com"

# Use a reasonable browser-like UA. FMGF is OK with crawlers (robots meta says
# noindex,follow) and this tool is personal-use only.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 gf2map/0.1"
)

SORT_PARAM_MAP = {
    "best": None,        # Best Match: omit param
    "rating": "rating",
    "distance": "distance",
}

_RATING_RE = re.compile(r"(\d+(?:\.\d+)?)")
_INT_RE = re.compile(r"(\d+)")


@dataclass
class Restaurant:
    id: str
    name: str
    fmgf_url: str
    address: Optional[str] = None
    distance: Optional[str] = None
    rating_stars: Optional[float] = None
    rating_count: Optional[int] = None
    safety_rating: Optional[float] = None
    safety_rating_description: Optional[str] = None
    safety_rating_count: Optional[int] = None
    tags: Optional[str] = None
    gf_menu_items: Optional[str] = None
    featured_review: Optional[str] = None
    has_gf_menu: bool = False
    extra: dict = field(default_factory=dict)


def _safe_text(node: Optional[Tag]) -> Optional[str]:
    if node is None:
        return None
    text = node.get_text(strip=True)
    return text or None


def _parse_float(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    m = _RATING_RE.search(s)
    return float(m.group(1)) if m else None


def _parse_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    m = _INT_RE.search(s)
    return int(m.group(1)) if m else None


def _parse_listing(li: Tag) -> Optional[Restaurant]:
    """Parse a single <li data-id> entry. Returns None on fatal failures."""
    try:
        rid = li.get("data-id")
        title_a = li.select_one(".sl-title h2 a")
        if not rid or not title_a:
            return None

        name = title_a.get_text(strip=True)
        href = title_a.get("href") or ""
        fmgf_url = FMGF_BASE_URL + href if href.startswith("/") else href

        r = Restaurant(id=str(rid), name=name, fmgf_url=fmgf_url)

        # address + distance
        try:
            r.address = _safe_text(li.select_one(".sl-addr"))
        except Exception:
            pass
        try:
            r.distance = _safe_text(li.select_one(".sl-dist"))
        except Exception:
            pass

        # rating stars (title="4.5 star rating") + count
        try:
            stars_node = li.select_one(".rating-stars")
            if stars_node and stars_node.get("title"):
                r.rating_stars = _parse_float(stars_node["title"])
                # The next-sibling-ish span.ml-1 like "(9)"
                count_span = stars_node.find_next("span", class_="ml-1")
                if count_span is not None:
                    txt = count_span.get_text(strip=True).strip("()")
                    r.rating_count = _parse_int(txt)
        except Exception:
            pass

        # safety rating (hearts) + description + count
        try:
            hearts_node = li.select_one(".rating-hearts")
            if hearts_node and hearts_node.get("title"):
                title = hearts_node["title"]
                r.safety_rating = _parse_float(title)
                # Keep the descriptive sentence after the leading number phrase.
                # e.g. "4.7 safety rating out of 5. Likely celiac friendly..."
                # Split on the first ". " (period+space) to skip the decimal in "4.7".
                m = re.match(
                    r"^\s*[\d.]+\s+safety rating(?:\s+out of\s+\d+)?\.?\s*(.*)$",
                    title,
                    flags=re.I | re.S,
                )
                if m:
                    rest = m.group(1).strip()
                    r.safety_rating_description = rest or None
            count_node = li.select_one("span.ml-2.text-muted.small")
            if count_node is not None:
                r.safety_rating_count = _parse_int(count_node.get_text(strip=True))
        except Exception:
            pass

        # tags (price + category) - inline div, not h3
        try:
            for div in li.select("div.sl-tags"):
                txt = div.get_text(strip=True)
                if txt:
                    r.tags = txt
                    break
        except Exception:
            pass

        # GF menu items (h3.sl-tags)
        try:
            h3 = li.select_one("h3.sl-tags")
            if h3 is not None:
                txt = h3.get_text(" ", strip=True)
                # Strip leading "GF menu items:" label if present
                txt = re.sub(r"^\s*GF menu items:\s*", "", txt, flags=re.I)
                r.gf_menu_items = txt or None
        except Exception:
            pass

        # featured review (italic blurb), strip leading sr-only icon text
        try:
            fr = li.select_one("div.font-italic.small")
            if fr is not None:
                # Remove sr-only spans so they don't pollute the text
                for sr in fr.select(".fa-sr-only, .sr-only"):
                    sr.extract()
                # Remove icon <i> tags
                for icon in fr.find_all("i"):
                    icon.extract()
                txt = fr.get_text(" ", strip=True)
                # Normalize whitespace and strip surrounding quotes/whitespace
                txt = re.sub(r"\s+", " ", txt).strip()
                # Strip surrounding curly or straight quotes
                txt = txt.strip('"').strip("'").strip("“”").strip()
                r.featured_review = txt or None
        except Exception:
            pass

        # has GF Menu flag - look for a div.mt-2 containing literal "GF Menu"
        try:
            for div in li.select("div.mt-2"):
                if "GF Menu" in div.get_text(" ", strip=True):
                    # Avoid h3.sl-tags "GF menu items:" matches (different tag).
                    r.has_gf_menu = True
                    break
        except Exception:
            pass

        return r
    except Exception as e:
        logger.warning("Failed to parse listing: %s", e)
        return None


def parse_search_html(html: str, limit: int) -> List[Restaurant]:
    """Parse FMGF search HTML and return up to `limit` restaurants."""
    soup = BeautifulSoup(html, "lxml")
    ul = soup.select_one("ul#locations-list")
    if ul is None:
        logger.warning("No #locations-list element found in HTML")
        return []

    results: List[Restaurant] = []
    for li in ul.select("li[data-id]"):
        r = _parse_listing(li)
        if r is not None:
            results.append(r)
        if len(results) >= limit:
            break
    return results


def fetch_search(
    *,
    lat: float,
    lng: float,
    address: str,
    sort: str,
    client: httpx.Client,
) -> str:
    """Fetch FMGF search HTML. `sort` is one of: best, rating, distance."""
    params: dict[str, str] = {
        "lat": f"{lat}",
        "lng": f"{lng}",
        "a": address,
    }
    sort_val = SORT_PARAM_MAP.get(sort)
    if sort_val:
        params["sort"] = sort_val

    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    resp = client.get(FMGF_SEARCH_URL, params=params, headers=headers, timeout=30.0)
    resp.raise_for_status()
    return resp.text


def search(
    *,
    lat: float,
    lng: float,
    address: str,
    sort: str,
    count: int,
    client: Optional[httpx.Client] = None,
) -> List[Restaurant]:
    """High-level helper: fetch + parse + truncate."""
    owns_client = client is None
    if owns_client:
        client = httpx.Client()
    try:
        html = fetch_search(
            lat=lat, lng=lng, address=address, sort=sort, client=client
        )
    finally:
        if owns_client:
            client.close()
    return parse_search_html(html, limit=count)
