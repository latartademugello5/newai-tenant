"""Load addresses + their resolved jurisdictions and turn them into engine facts."""
from __future__ import annotations

import csv

from . import common as C
from .engine import build_facts

ADDR_CSV = C.STARTER / "data" / "sample_addresses.csv"


def load_addresses(path=ADDR_CSV) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_facts(addresses_path=ADDR_CSV, resolved_path=None) -> dict[str, dict]:
    addrs = load_addresses(addresses_path)
    resolved = C.read_json(resolved_path or (C.out_dir() / "addresses_resolved.json"))
    if resolved is None:
        raise SystemExit("outputs/addresses_resolved.json not found - run 03_geocode_addresses.py first.")
    rmap = {r["address_id"]: r for r in resolved}
    return {a["address_id"]: build_facts(a, rmap.get(a["address_id"])) for a in addrs}


def load_rules(path=None) -> list[dict]:
    d = C.read_json(path or (C.out_dir() / "rules.json"))
    if d is None:
        raise SystemExit("outputs/rules.json not found - run 01_extract_rules.py and 02_link_rules.py first.")
    return d["rules"]
