"""Address -> legal jurisdiction using the US Census Geocoder (public, no key)."""
from __future__ import annotations

import re
import time

import requests

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/geographies/address"

IN_SCOPE = {  # Census place base-name -> our jurisdiction string
    ("los angeles", "CA"): "Los Angeles, CA",
    ("san francisco", "CA"): "San Francisco, CA",
    ("san diego", "CA"): "San Diego, CA",
    ("berkeley", "CA"): "Berkeley, CA",
    ("santa ana", "CA"): "Santa Ana, CA",
    ("jersey city", "NJ"): "Jersey City, NJ",
    ("hoboken", "NJ"): "Hoboken, NJ",
    ("newark", "NJ"): "Newark, NJ",
    ("boston", "MA"): "Boston, MA",
    ("cambridge", "MA"): "Cambridge, MA",
}

# neighbourhood / district names that are mailing "cities" inside a legal city
NEIGHBORHOOD_TO_CITY = {
    ("dorchester", "MA"): "Boston", ("roxbury", "MA"): "Boston", ("east boston", "MA"): "Boston",
    ("brighton", "MA"): "Boston", ("allston", "MA"): "Boston", ("south boston", "MA"): "Boston",
    ("jamaica plain", "MA"): "Boston", ("hyde park", "MA"): "Boston", ("mattapan", "MA"): "Boston",
    ("west roxbury", "MA"): "Boston", ("roslindale", "MA"): "Boston", ("charlestown", "MA"): "Boston",
    ("san ysidro", "CA"): "San Diego", ("van nuys", "CA"): "Los Angeles",
}

# datasets that only contain parcels of ONE city -> a safe fallback if the geocoder is down
CITY_OWN_DATASETS = {
    "DataSF": "San Francisco, CA",
    "Boston Property Assessment": "Boston, MA",
    "Cambridge Property Database": "Cambridge, MA",
}


def hint_city(addr: dict) -> str | None:
    """Best guess from the mailing city (NOT trusted as the legal city)."""
    name = addr["postal_city"].strip().lower()
    st = addr["state"]
    name = NEIGHBORHOOD_TO_CITY.get((name, st), name).lower()
    return IN_SCOPE.get((name.lower(), st))


def query_city(addr: dict) -> str:
    name = addr["postal_city"].strip()
    mapped = NEIGHBORHOOD_TO_CITY.get((name.lower(), addr["state"]))
    return mapped or name


def clean_street(street: str) -> str:
    """'1031-1035 CLINTON ST' -> '1031 CLINTON ST' (the geocoder wants one house number)."""
    s = street.strip().rstrip(".")
    s = re.sub(r"^(\d+)[A-Za-z]?\s*-\s*[\d.]+[A-Za-z]?\s+", r"\1 ", s)
    s = re.sub(r"^(\d+)\.\d+\s+", r"\1 ", s)
    return s


def _request(params: dict, retries: int = 3) -> dict | None:
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(CENSUS_URL, params=params, timeout=40)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
        except Exception as e:  # network hiccup
            last = f"{type(e).__name__}: {e}"
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Census geocoder failed: {last}")


def census_lookup(street: str, city: str, state: str, zip_code: str = "") -> dict | None:
    """Return the first address match (dict) or None."""
    base = {"street": street, "city": city, "state": state, "benchmark": "Public_AR_Current",
            "vintage": "Current_Current", "format": "json", "layers": "all"}
    if zip_code:
        base["zip"] = zip_code
    for variant in (base, {k: v for k, v in base.items() if k != "zip"}):
        data = _request(variant)
        matches = (data or {}).get("result", {}).get("addressMatches") or []
        if matches:
            return matches[0]
        if "zip" not in variant:
            break
    return None


def parse_match(m: dict) -> dict:
    geos = m.get("geographies", {}) or {}
    place = None
    for key in geos:
        if key.lower().startswith("incorporated place"):
            if geos[key]:
                g = geos[key][0]
                place = g.get("BASENAME") or re.sub(r"\s+(city|town|village|borough)$", "", g.get("NAME", ""), flags=re.I)
            break
    county = None
    for key in geos:
        if key.lower().startswith("count"):
            if geos[key]:
                county = geos[key][0].get("BASENAME") or geos[key][0].get("NAME")
            break
    coords = m.get("coordinates", {}) or {}
    return {
        "matched_address": m.get("matchedAddress"),
        "lon": coords.get("x"),
        "lat": coords.get("y"),
        "place": place,  # None => not inside any incorporated place
        "county": county,
    }


def to_jurisdiction(place: str | None, state: str) -> tuple[str | None, bool]:
    """-> (jurisdiction string or None, in_scope)"""
    if not place:
        return None, False
    key = (place.strip().lower(), state)
    if key in IN_SCOPE:
        return IN_SCOPE[key], True
    return f"{place}, {state}", False
