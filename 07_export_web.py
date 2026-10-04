#!/usr/bin/env python3
"""Bundle everything the demo website needs into web/data/app_data.json (+ copies of the 3 submission files).

Run:   python 07_export_web.py
Then preview:  python -m http.server 8000 --directory web   ->  open http://localhost:8000
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil

from nav import common as C
from nav import data
from nav.engine import lookup_all

WEB = C.ROOT / "web" / "data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--web-dir", default=str(WEB))
    args = ap.parse_args()
    if args.out_dir:
        C.set_out_dir(args.out_dir)
    out, web = C.out_dir(), C.Path(args.web_dir)
    web.mkdir(parents=True, exist_ok=True)
    rules = data.load_rules(args.rules)
    facts = data.load_facts()
    resolved = {r["address_id"]: r for r in C.read_json(out / "addresses_resolved.json")}
    base_date = C.parse_date(C.DEFAULT_AS_OF)

    # ---- dates where any answer can change (effective dates + yearly rolling-age boundaries)
    bps = {base_date}
    for r in rules:
        d = C.parse_partial_date(r.get("effective_date"))
        if d:
            bps.add(d)
    for y in range(2025, 2031):
        bps |= {dt.date(y, 1, 1), dt.date(y, 12, 31)}
    bps = sorted(bps)
    snap_dates = [bps[0] - dt.timedelta(days=1)] + bps

    strings, sidx = [], {}

    def intern(s):
        if s not in sidx:
            sidx[s] = len(strings)
            strings.append(s)
        return sidx[s]

    def pack(entries):
        return {e["team_rule_id"]: [e["result"], int(e["conflict_flag"]), e["confidence"], intern(e["explanation"])] for e in entries}

    base = {a: pack(v) for a, v in lookup_all(rules, facts, base_date).items()}
    snaps = []
    for d in snap_dates:
        cur = {a: pack(v) for a, v in lookup_all(rules, facts, d).items()}
        diff = {}
        for a, entries in cur.items():
            ch = {rid: e for rid, e in entries.items() if base[a].get(rid) != e}
            ch.update({rid: None for rid in base[a] if rid not in entries})
            if ch:
                diff[a] = ch
        snaps.append({"date": d.isoformat(), "diff": diff})

    addresses = []
    for aid, f in facts.items():
        r = resolved.get(aid, {})
        addresses.append({"id": aid, "street": f["street_address"], "postal_city": f["postal_city"], "state": f["state"],
                          "year_built": f["year_built"], "units": f["units"], "units_hint": f["units_src"] if f["units_lo"] and not f["units"] else None,
                          "use_description": f["use_description"], "legal_city": f["legal_city"], "county": f["county"],
                          "method": f["city_method"], "confidence": f["city_confidence"], "note": f["city_note"],
                          "lat": r.get("lat"), "lon": r.get("lon"), "matched_address": r.get("matched_address")})
    es = C.read_json(out / "rules_es.json", {})
    for r in rules:
        if r["team_rule_id"] in es:
            r["title_es"] = es[r["team_rule_id"]].get("title")
            r["requirement_es"] = es[r["team_rule_id"]].get("requirement")
    bundle = {
        "meta": {"as_of": C.DEFAULT_AS_OF, "generated": C.now_utc(), "n_rules": len(rules), "n_addresses": len(addresses),
                 "audit_tail": [l for l in (out / "audit_log.jsonl").read_text().splitlines()[-12:]] if (out / "audit_log.jsonl").exists() else []},
        "rules": rules, "addresses": addresses, "strings": strings, "base": base, "snapshots": snaps,
        "changes": C.read_json(out / "changes.json", {}), "test_report": C.read_json(out / "test_report.json", {}),
        "tests": C.read_json(C.STARTER / "dev" / "change_tests.json", []),
    }
    import json
    (web / "app_data.json").write_text(json.dumps(bundle, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    for n in ("rules.json", "lookups.json", "changes.json"):
        if (out / n).exists():
            shutil.copy(out / n, web / n)
    size = (web / "app_data.json").stat().st_size / 1e6
    print(f"Wrote {web/'app_data.json'} ({size:.1f} MB; {len(snaps)} date snapshots, {len(strings):,} unique explanations)")
    if size > 25:
        print("WARNING: file is large; the site will load slowly.")
    print("Preview:  python -m http.server 8000 --directory web   then open http://localhost:8000")


if __name__ == "__main__":
    main()
