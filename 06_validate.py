#!/usr/bin/env python3
"""Check your three submission files before you upload them.

Run:   python 06_validate.py
Checks: rules.json matches the official schema, every quoted_span really exists in its source document,
        lookups.json covers all 500 addresses with legal 'result' values, changes.json covers T1-T5.
Exit code is non-zero if anything is wrong.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from jsonschema import Draft202012Validator

from nav import common as C
from nav.data import load_addresses
from nav.textcheck import Haystack

RESULTS = {"applies", "unknown", "superseded", "not_yet_effective", "pending"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--skip-quote-check", action="store_true")
    args = ap.parse_args()
    if args.out_dir:
        C.set_out_dir(args.out_dir)
    out = C.out_dir()
    errors, warns = [], []

    schema = C.read_json(C.STARTER / "schema" / "rule_record.schema.json")
    rules = (C.read_json(out / "rules.json") or {}).get("rules")
    lookups = C.read_json(out / "lookups.json")
    changes = C.read_json(out / "changes.json")
    for name, obj in (("rules.json", rules), ("lookups.json", lookups), ("changes.json", changes)):
        if obj is None:
            errors.append(f"{name} is missing in {out}")
    if errors:
        print("\n".join("ERROR " + e for e in errors))
        sys.exit(1)

    # ---------------- rules.json
    v = Draft202012Validator(schema)
    ids = set()
    docs: dict[str, Haystack] = {}
    bad_quote = 0
    for r in rules:
        for e in v.iter_errors(r):
            errors.append(f"rules.json {r.get('team_rule_id')}: {'/'.join(map(str, e.path))}: {e.message[:120]}")
        if r["team_rule_id"] in ids:
            errors.append(f"duplicate team_rule_id {r['team_rule_id']}")
        ids.add(r["team_rule_id"])
        if not args.skip_quote_check and r.get("source_doc_id"):
            try:
                hay = docs.setdefault(r["source_doc_id"], Haystack(C.read_doc(r["source_doc_id"])["raw"]))
                span, _, _ = hay.locate(r["quoted_span"], fuzzy_threshold=101)  # exact only
                if span is None:
                    bad_quote += 1
                    errors.append(f"rules.json {r['team_rule_id']}: quoted_span NOT found in {r['source_doc_id']}")
            except FileNotFoundError:
                errors.append(f"rules.json {r['team_rule_id']}: source doc {r['source_doc_id']} has no text file")
    # ---------------- lookups.json
    addr_ids = [a["address_id"] for a in load_addresses()]
    L = lookups.get("lookups", {})
    if "as_of" not in lookups:
        errors.append("lookups.json has no 'as_of'")
    missing = [a for a in addr_ids if a not in L]
    if missing:
        errors.append(f"lookups.json is missing {len(missing)} addresses, e.g. {missing[:5]}")
    extra = [a for a in L if a not in set(addr_ids)]
    if extra:
        errors.append(f"lookups.json has unknown address ids {extra[:5]}")
    cnt = Counter()
    for aid, entries in L.items():
        for e in entries:
            cnt[e["result"]] += 1
            if e["team_rule_id"] not in ids:
                errors.append(f"lookups {aid}: unknown rule id {e['team_rule_id']}")
            if e["result"] not in RESULTS:
                errors.append(f"lookups {aid}: bad result '{e['result']}'")
            if not isinstance(e.get("conflict_flag"), bool):
                errors.append(f"lookups {aid}: conflict_flag must be true/false")
            if not e.get("explanation"):
                errors.append(f"lookups {aid}: empty explanation")
    # ---------------- changes.json
    for tid in ("T1", "T2", "T3", "T4", "T5"):
        c = changes.get(tid)
        if c is None:
            errors.append(f"changes.json missing {tid}")
            continue
        for key in ("affected_address_ids", "conflict_flag_address_ids"):
            if not isinstance(c.get(key), list):
                errors.append(f"changes {tid}: '{key}' must be a list")
            else:
                bad = [a for a in c[key] if a not in set(addr_ids)]
                if bad:
                    errors.append(f"changes {tid}: unknown address ids {bad[:5]}")
    # ---------------- soft checks
    juris = Counter(r["jurisdiction"] for r in rules)
    for j in ["CA", "NJ", "MA", "Los Angeles, CA", "San Francisco, CA", "San Diego, CA", "Berkeley, CA", "Santa Ana, CA",
              "Jersey City, NJ", "Hoboken, NJ", "Newark, NJ", "Boston, MA", "Cambridge, MA"]:
        if juris[j] == 0:
            warns.append(f"no rules extracted for {j}")
    cats = Counter(r["category"] for r in rules)
    for c in ["rent_increase_limits", "just_cause_eviction", "security_deposits", "application_screening_fees",
              "screening_restrictions", "algorithmic_rent_setting"]:
        if cats[c] == 0:
            warns.append(f"no rules in category {c}")
    total = sum(cnt.values()) or 1
    if cnt["unknown"] / total > 0.5:
        warns.append(f"{cnt['unknown']/total:.0%} of results are 'unknown' - check coverage extraction")

    print(f"rules.json   : {len(rules)} rules; by status {dict(Counter(r['status'] for r in rules))}")
    print(f"lookups.json : {len(L)}/{len(addr_ids)} addresses; results {dict(cnt)}")
    print(f"changes.json : {sorted(changes)}")
    for w in warns:
        print("WARN  " + w)
    for e in errors[:60]:
        print("ERROR " + e)
    if len(errors) > 60:
        print(f"... and {len(errors)-60} more errors")
    print("\nVALID - ready to submit" if not errors else f"\n{len(errors)} problem(s) - fix and re-run")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
