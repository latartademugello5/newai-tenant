#!/usr/bin/env python3
"""MODULE B (part 1) - resolve every sample address to its LEGAL city / county with the Census Geocoder.

The mailing city ('postal_city') is NOT trusted. Example: a 'Los Angeles' mailing address can sit in another city.

Run:   python 03_geocode_addresses.py --self-test    (try 3 addresses first, prints what the Census returns)
       python 03_geocode_addresses.py                (all 500, ~5-10 minutes, cached - safe to re-run)
       python 03_geocode_addresses.py --offline      (no internet: uses the fallback guess, marks it low confidence)
Output: outputs/addresses_resolved.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from nav import common as C
from nav import geo

ADDR_CSV = C.STARTER / "data" / "sample_addresses.csv"


def load_addresses(path=ADDR_CSV):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fallback(addr: dict, note: str) -> dict:
    """No geocoder answer. Only a city-specific parcel dataset gives us a safe legal city."""
    for key, jur in geo.CITY_OWN_DATASETS.items():
        if addr["source_dataset"].startswith(key):
            return {"legal_city": jur, "in_scope": True, "method": "source_dataset_fallback",
                    "confidence": "medium", "note": f"{note}; parcel dataset only covers {jur}"}
    return {"legal_city": None, "in_scope": False, "method": "unresolved", "confidence": "none", "note": note}


def resolve_one(addr: dict, cache: dict, offline: bool) -> dict:
    street = geo.clean_street(addr["street_address"])
    city = geo.query_city(addr)
    key = f"{street}|{city}|{addr['state']}|{addr['zip']}"
    base = {
        "address_id": addr["address_id"],
        "query": {"street": street, "city": city, "state": addr["state"], "zip": addr["zip"]},
        "postal_city": addr["postal_city"],
        "hint_city": geo.hint_city(addr),
    }
    if offline:
        return {**base, **fallback(addr, "offline mode")}
    try:
        if key not in cache:
            m = geo.census_lookup(street, city, addr["state"], addr["zip"])
            cache[key] = geo.parse_match(m) if m else None
        parsed = cache[key]
    except Exception as e:
        return {**base, **fallback(addr, f"geocoder error: {e}")}
    if not parsed:
        return {**base, **fallback(addr, "Census geocoder found no match")}
    jur, in_scope = geo.to_jurisdiction(parsed["place"], addr["state"])
    return {
        **base, **parsed,
        "legal_city": jur,            # e.g. 'Hoboken, NJ'; None if outside any incorporated place
        "in_scope": in_scope,
        "method": "census_geocoder",
        "confidence": "high",
        "note": None if jur else "Address is not inside an incorporated place (state/county rules only).",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--addresses", default=str(ADDR_CSV))
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    if args.out_dir:
        C.set_out_dir(args.out_dir)
    out = C.out_dir()
    addrs = load_addresses(args.addresses)

    if args.self_test:
        picks = [next(a for a in addrs if a["state"] == s) for s in ("CA", "NJ", "MA")]
        for a in picks:
            street, city = geo.clean_street(a["street_address"]), geo.query_city(a)
            print(f"\n--- {a['address_id']}: {street}, {city}, {a['state']} {a['zip']}")
            m = geo.census_lookup(street, city, a["state"], a["zip"])
            if not m:
                print("NO MATCH (the script will fall back for this one)")
                continue
            print("geography layers returned:", list((m.get("geographies") or {}).keys()))
            print("parsed:", json.dumps(geo.parse_match(m)))
        print("\nIf 'place' above shows a city name for each, geocoding works. Now run it without --self-test.")
        return

    cache_path = out / "geocode_cache.json"
    cache = C.read_json(cache_path, {})
    print(f"Resolving {len(addrs)} addresses ({'OFFLINE' if args.offline else 'Census Geocoder'}) ...")
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(lambda a: resolve_one(a, cache, args.offline), addrs))
    C.write_json(cache_path, cache)
    C.write_json(out / "addresses_resolved.json", results)
    C.audit("geocode", offline=args.offline, n=len(results), methods=dict(Counter(r["method"] for r in results)),
            geocoder="https://geocoding.geo.census.gov (Public_AR_Current / Current_Current)")

    print("\nHow each address was resolved:", dict(Counter(r["method"] for r in results)))
    moved = [r for r in results if r["legal_city"] and r["hint_city"] and r["legal_city"] != r["hint_city"]]
    outside = [r for r in results if r["method"] == "census_geocoder" and not r["in_scope"]]
    print(f"Mailing city != legal city: {len(moved)} addresses (this is the trap the challenge warns about)")
    print(f"Outside all 10 in-scope cities: {len(outside)} addresses (state rules only)")
    for r in (moved + outside)[:8]:
        print(f"   {r['address_id']}: mailing '{r['postal_city']}' -> legal '{r['legal_city']}'")
    unresolved = [r for r in results if r["method"] == "unresolved"]
    if unresolved:
        print(f"Unresolved: {len(unresolved)} (city rules will be reported 'unknown' for them)")
    print(f"Wrote {out/'addresses_resolved.json'}\nNext: python 04_build_lookups.py")


if __name__ == "__main__":
    main()
