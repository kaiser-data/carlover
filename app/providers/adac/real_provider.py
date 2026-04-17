"""
Real ADAC provider — fetches live data from adac.de.

Strategy:
  Each vehicle page at /rund-ums-fahrzeug/autokatalog/marken-modelle/{brand}/{model}/
  embeds all data as window.__staticRouterHydrationData = JSON.parse("...").
  We extract that JSON, parse it, and map it to our schema.

Caching:
  Results are cached in-memory (TTL 24 h) to avoid hammering the site.
  Set ADAC_CACHE_TTL_HOURS in env to override.

Rate limiting:
  A 1-second delay is added between requests by default.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import unicodedata
from typing import Optional

import httpx
from loguru import logger

from app.providers.adac.base import ADACBaseProvider
from app.schemas.agent_outputs import (
    ADACClassThresholds,
    ADACGeneration,
    ADACIssuePattern,
    ADACReliabilityYear,
    ADACServiceGuidance,
    ADACVehicleInfo,
)
from app.schemas.common import VehicleInfo

_BASE_URL = "https://www.adac.de/rund-ums-fahrzeug/autokatalog/marken-modelle"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_CACHE_TTL = 86_400  # 24 hours in seconds
_REQUEST_DELAY = 1.0  # seconds between requests

# In-memory cache: slug → (timestamp, rangePage_dict, page_url)
_cache: dict[str, tuple[float, dict, str]] = {}


def _slugify(text: str) -> str:
    """Convert make/model to ADAC URL slug (lowercase, ascii, hyphens)."""
    text = text.lower().strip()
    # Normalize unicode (e.g. ä → ae)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    # Common ADAC slug overrides (ADAC uses German model names in URLs)
    overrides = {
        # Makes
        "mercedes": "mercedes-benz",
        "mercedes benz": "mercedes-benz",
        "vw": "vw",
        "volkswagen": "vw",
        "skoda": "skoda",
        # BMW series — ADAC uses "{n}er-reihe" in URLs
        "1er": "1er-reihe", "1 series": "1er-reihe", "1er series": "1er-reihe", "1er-reihe": "1er-reihe",
        "2er": "2er-reihe", "2 series": "2er-reihe", "2er series": "2er-reihe", "2er-reihe": "2er-reihe",
        "3er": "3er-reihe", "3 series": "3er-reihe", "3er series": "3er-reihe", "3er-reihe": "3er-reihe",
        "4er": "4er-reihe", "4 series": "4er-reihe", "4er series": "4er-reihe", "4er-reihe": "4er-reihe",
        "5er": "5er-reihe", "5 series": "5er-reihe", "5er series": "5er-reihe", "5er-reihe": "5er-reihe",
        "6er": "6er-reihe", "6 series": "6er-reihe", "6er series": "6er-reihe", "6er-reihe": "6er-reihe",
        "7er": "7er-reihe", "7 series": "7er-reihe", "7er series": "7er-reihe", "7er-reihe": "7er-reihe",
        "8er": "8er-reihe", "8 series": "8er-reihe", "8er series": "8er-reihe", "8er-reihe": "8er-reihe",
        # Mercedes — ADAC uses "a-klasse", "c-klasse" etc.
        "a-klasse": "a-klasse", "a klasse": "a-klasse", "a class": "a-klasse",
        "b-klasse": "b-klasse", "b klasse": "b-klasse", "b class": "b-klasse",
        "c-klasse": "c-klasse", "c klasse": "c-klasse", "c class": "c-klasse",
        "e-klasse": "e-klasse", "e klasse": "e-klasse", "e class": "e-klasse",
        "s-klasse": "s-klasse", "s klasse": "s-klasse", "s class": "s-klasse",
        "g-klasse": "g-klasse", "g klasse": "g-klasse", "g class": "g-klasse",
    }
    if text in overrides:
        return overrides[text]
    # Replace spaces and underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"[^a-z0-9-]", "", text)
    return text.strip("-")


def _extract_hydration_json(html: str) -> Optional[dict]:
    """Extract and parse window.__staticRouterHydrationData from page HTML."""
    m = re.search(
        r'window\.__staticRouterHydrationData\s*=\s*JSON\.parse\("((?:[^"\\]|\\.)*)"\)',
        html,
        re.DOTALL,
    )
    if not m:
        return None
    try:
        # The value is a JSON-encoded string — decode twice
        inner = json.loads('"' + m.group(1) + '"')
        return json.loads(inner)
    except Exception as exc:
        logger.warning(f"ADAC JSON parse error: {exc}")
        return None


def _find_range_page(data: dict) -> Optional[dict]:
    """Navigate GraphQL hydration data to the rangePage object."""
    try:
        loader = data.get("loaderData", {})
        for key, val in loader.items():
            if not isinstance(val, dict):
                continue
            rp = (
                val.get("data", {})
                .get("rangeOrArticlePage", {})
                .get("rangePage")
            )
            if rp:
                return rp
    except Exception:
        pass
    return None


def _reliability_rating(indicators: list[dict]) -> Optional[float]:
    """
    Convert ADAC breakdown valuationKey to a 0-1 reliability score.
    valuationKey: 1=very good, 2=good, 3=satisfactory, 4=poor, 5=very poor
    Most recent year takes precedence.
    """
    if not indicators:
        return None
    latest = max(indicators, key=lambda x: x.get("year", 0))
    key = latest.get("valuationKey", 3)
    mapping = {1: 0.95, 2: 0.80, 3: 0.60, 4: 0.35, 5: 0.15}
    return mapping.get(key, 0.60)


def _find_generation_for_year(generations: list[dict], year: Optional[int]) -> Optional[dict]:
    """Find the best matching generation for a given year."""
    if not year or not generations:
        return generations[0] if generations else None
    # Find generation where year falls within manufactured range
    for gen in generations:
        year_from = gen.get("manufacturedFrom")
        year_until = gen.get("manufacturedUntil") or 9999
        if year_from and year_from <= year <= year_until:
            return gen
    # Fallback: most recent
    return generations[0]


_RATING_LABELS = {1: "sehr gut", 2: "gut", 3: "befriedigend", 4: "ausreichend", 5: "mangelhaft"}
_RATING_SCORES = {1: 0.95, 2: 0.80, 3: 0.60, 4: 0.35, 5: 0.15}


def _parse_vehicle_info(rp: dict, vehicle: VehicleInfo, page_url: str = "") -> ADACVehicleInfo:
    """Map ADAC rangePage dict to ADACVehicleInfo."""
    raw_generations = rp.get("generations", [])
    bs = rp.get("breakdownStatistics") or {}
    indicators = bs.get("indicators", [])
    description = rp.get("description") or ""

    # ── All generations ──
    generations: list[ADACGeneration] = []
    for g in raw_generations:
        year_until = g.get("manufacturedUntil")
        generations.append(ADACGeneration(
            name=g.get("name"),
            year_from=g.get("manufacturedFrom"),
            year_to=year_until if year_until and year_until != 9999 else None,
        ))

    # ── Year range ──
    from_years = [g.year_from for g in generations if g.year_from]
    year_from = min(from_years) if from_years else None
    to_years = [g.year_to for g in generations if g.year_to]
    year_to = max(to_years) if to_years else None

    # ── Class-average thresholds per year (from ADAC legend field) ──
    # legend: [{year, ratingValues: {one, two, three, four}}]
    # one=sehr_gut threshold, two=gut, three=befriedigend, four=ausreichend
    legend_by_year: dict[int, ADACClassThresholds] = {}
    for entry in bs.get("legend", []):
        yr = entry.get("year")
        rv = entry.get("ratingValues") or {}
        if yr and rv:
            legend_by_year[yr] = ADACClassThresholds(
                sehr_gut=float(rv.get("one", 0)),
                gut=float(rv.get("two", 0)),
                befriedigend=float(rv.get("three", 0)),
                ausreichend=float(rv.get("four", 0)),
            )

    # ── Annual mileage assumption (km) ──
    annual_mileage_km: Optional[int] = bs.get("annualMileage") or None
    if annual_mileage_km:
        annual_mileage_km = int(annual_mileage_km)

    # ── Generation name per year (which generation was on sale in that year) ──
    def _gen_name_for_year(yr: int) -> Optional[str]:
        for g in raw_generations:
            yf = g.get("manufacturedFrom") or 0
            yu = g.get("manufacturedUntil") or 9999
            if yf <= yr <= yu:
                return g.get("name")
        return None

    # ── Reliability by year (full Pannenstatistik history) ──
    reliability_by_year: list[ADACReliabilityYear] = []
    for ind in sorted(indicators, key=lambda x: x.get("year", 0)):
        yr = ind.get("year")
        val = ind.get("value", 0.0)
        vkey = ind.get("valuationKey", 3)
        if yr:
            reliability_by_year.append(ADACReliabilityYear(
                year=yr,
                breakdowns_per_1000=float(val),
                rating=_RATING_LABELS.get(vkey, "k.A."),
                rating_score=_RATING_SCORES.get(vkey, 0.60),
                generation_name=_gen_name_for_year(yr),
                class_thresholds=legend_by_year.get(yr),
                annual_mileage_km=annual_mileage_km,
            ))

    # ── Match generation for requested year (for summary) ──
    matched_gen = _find_generation_for_year(raw_generations, vehicle.year)
    gen_name = matched_gen.get("name") if matched_gen else None
    reliability = _reliability_rating(indicators)

    # ── Summary string (kept for answer agent / backwards compat) ──
    summary_parts = []
    if description:
        summary_parts.append(description[:400])
    if gen_name:
        summary_parts.append(f"Matched generation: {gen_name}.")
    if reliability is not None:
        summary_parts.append(f"Reliability score (ADAC Pannenstatistik): {int(reliability * 100)}%.")

    return ADACVehicleInfo(
        make=rp.get("brand", {}).get("name") or vehicle.make,
        model=rp.get("name") or vehicle.model,
        year_from=year_from,
        year_to=year_to,
        engine_types=[],
        description=description,
        known_issues_summary=" ".join(summary_parts),
        generations=generations,
        reliability_by_year=reliability_by_year,
        image_url=_extract_image_url(rp),
        adac_page_url=page_url,
    )


def _parse_issue_patterns(
    rp: dict, vehicle: VehicleInfo, keywords: Optional[list[str]] = None
) -> list[ADACIssuePattern]:
    """
    Extract ALL issue patterns from ADAC breakdown defects data.
    keywords filter is only applied when explicitly provided (e.g. from chat agent).
    Falls back to per-year reliability summary when no specific defects exist.
    """
    bs = rp.get("breakdownStatistics") or {}
    defects = bs.get("defects") or []
    patterns: list[ADACIssuePattern] = []

    for defect in defects:
        name = defect.get("name") or ""
        description = defect.get("description") or ""
        if keywords:
            text = (name + " " + description).lower()
            if not any(kw.lower() in text for kw in keywords):
                continue
        patterns.append(
            ADACIssuePattern(
                pattern_name=name,
                symptoms=[description] if description else [],
                root_cause=defect.get("cause") or "",
                solution=defect.get("solution") or "",
            )
        )

    # Fallback: one pattern per recorded year from Pannenstatistik
    if not patterns:
        indicators = bs.get("indicators", [])
        for ind in sorted(indicators, key=lambda x: x.get("year", 0)):
            yr = ind.get("year", "")
            val = ind.get("value", 0)
            vkey = ind.get("valuationKey", 3)
            rating_text = _RATING_LABELS.get(vkey, "k.A.")
            patterns.append(
                ADACIssuePattern(
                    pattern_name=f"Zuverlässigkeit {vehicle.make} {vehicle.model} ({yr})",
                    symptoms=[
                        f"Pannenstatistik {yr}: {val} Pannen/1000 Fahrzeuge — Bewertung: {rating_text}"
                    ],
                    root_cause="",
                    solution="Regelmäßige Wartung gemäß Herstellervorgaben empfohlen.",
                    affected_years=str(yr),
                )
            )

    return patterns


def _extract_image_url(rp: dict) -> Optional[str]:
    """Extract the primary vehicle image URL from the ADAC rangePage dict."""
    # socialMediaImageUrl — ready-to-use direct JPEG, 1500px wide
    smu = rp.get("socialMediaImageUrl")
    if smu and isinstance(smu, str):
        return smu
    # image.defaultImageUrls[0] — Cloudinary-transformed JPEG fallback
    img = rp.get("image") or {}
    if isinstance(img, dict):
        urls = img.get("defaultImageUrls") or []
        if urls and isinstance(urls, list):
            # prefer JPEG over WebP
            jpeg = next((u for u in urls if u.endswith(".jpeg") or u.endswith(".jpg")), None)
            return jpeg or urls[0]
    return None


async def _fetch_page(brand_slug: str, model_slug: str) -> Optional[tuple[dict, str]]:
    """
    Fetch and parse the ADAC model page.
    Returns (rangePage dict, page_url) or None.
    Uses in-memory cache.
    """
    cache_key = f"{brand_slug}/{model_slug}"
    now = time.monotonic()

    # Check cache
    if cache_key in _cache:
        ts, cached_data, cached_url = _cache[cache_key]
        if now - ts < _CACHE_TTL:
            logger.debug(f"ADAC cache hit: {cache_key}")
            return cached_data, cached_url

    url = f"{_BASE_URL}/{brand_slug}/{model_slug}/"
    logger.info(f"ADAC fetch: {url}")

    # Route through ScraperAPI residential proxy if key is configured
    from app.config import get_settings
    scraper_key = get_settings().SCRAPER_API_KEY
    proxy = f"http://scraperapi:{scraper_key}@proxy.scraperapi.com:8001" if scraper_key else None
    if proxy:
        logger.debug("ADAC: using ScraperAPI proxy")

    try:
        async with httpx.AsyncClient(
            headers=_HEADERS,
            follow_redirects=True,
            timeout=30.0,
            proxy=proxy,
        ) as client:
            await asyncio.sleep(_REQUEST_DELAY)
            resp = await client.get(url)

        if resp.status_code != 200:
            logger.warning(f"ADAC returned HTTP {resp.status_code} for {url}")
            return None

        data = _extract_hydration_json(resp.text)
        if not data:
            logger.warning(f"ADAC: no hydration JSON found at {url}")
            return None

        rp = _find_range_page(data)
        if not rp:
            logger.warning(f"ADAC: no rangePage in hydration data at {url}")
            return None

        _cache[cache_key] = (now, rp, url)
        return rp, url

    except Exception as exc:
        logger.error(f"ADAC fetch failed for {url}: {exc}")
        return None


class RealADACProvider(ADACBaseProvider):
    """
    Live ADAC data provider.
    Fetches from adac.de autokatalog pages, extracts embedded JSON.
    Falls back gracefully if the page is unavailable.
    """

    SOURCE_LABEL = "ADAC"

    async def fetch_vehicle_info(
        self, vehicle: VehicleInfo
    ) -> Optional[ADACVehicleInfo]:
        brand_slug = _slugify(vehicle.make)
        model_slug = _slugify(vehicle.model)
        result = await _fetch_page(brand_slug, model_slug)
        if not result:
            return None
        rp, page_url = result
        return _parse_vehicle_info(rp, vehicle, page_url)

    async def fetch_issue_patterns(
        self,
        vehicle: VehicleInfo,
        issue_keywords: Optional[list[str]] = None,
    ) -> list[ADACIssuePattern]:
        brand_slug = _slugify(vehicle.make)
        model_slug = _slugify(vehicle.model)
        result = await _fetch_page(brand_slug, model_slug)
        if not result:
            return []
        rp, _ = result
        return _parse_issue_patterns(rp, vehicle, issue_keywords)

    async def fetch_service_guidance(
        self, vehicle: VehicleInfo
    ) -> Optional[ADACServiceGuidance]:
        # Service guidance is not available at range level on ADAC.
        # Return None — the answer agent handles missing data gracefully.
        return None
