#!/usr/bin/env python3
"""MODULE B (part 2) - for every sample address, list every rule that applies (or might), with an explanation.

Run:   python 04_build_lookups.py                     (default as-of date 2026-10-01)
       python 04_build_lookups.py --as-of 2027-07-02  (what would apply on another date?)
Reads: outputs/rules.json, outputs/addresses_resolved.json
Writes: outputs/lookups.json
"""
from __future__ import annotations

import argparse
from collections import Counter

from nav import common as C
from nav import data
from nav.engine import lookup_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default=C.DEFAULT_AS_OF)
    ap.add_argument("--rules", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--out-name", default="lookups.json")
    args = ap.parse_args()
    if args.out_dir:
        C.set_out_dir(args.out_dir)
    as_of = C.parse_date(args.as_of)
    rules = data.load_rules(args.rules)
    facts = data.load_facts()
    res = lookup_all(rules, facts, as_of)

    # submission format: {"as_of": ..., "lookups": {address_id: [{team_rule_id, result, explanation, conflict_flag}]}}
    out = {"as_of": args.as_of, "lookups": res}
    C.write_json(C.out_dir() / args.out_name, out)
    C.audit("lookups", as_of=args.as_of, addresses=len(res), rules=len(rules))

    tot = Counter(e["result"] for v in res.values() for e in v)
    flags = sum(e["conflict_flag"] for v in res.values() for e in v)
    empty = [a for a, v in res.items() if not v]
    print(f"As of {args.as_of}: {len(res)} addresses, {sum(tot.values())} rule results")
    for k, v in tot.most_common():
        print(f"   {k:18s} {v}")
    print(f"   conflict flags     {flags}")
    if empty:
        print(f"WARNING: {len(empty)} addresses have NO rules at all, e.g. {empty[:5]} - check your rules/geocoding")
    print(f"Wrote {C.out_dir()/args.out_name}\nNext: python 05_build_changes.py")


if __name__ == "__main__":
    main()
