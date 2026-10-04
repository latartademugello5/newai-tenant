#!/usr/bin/env python3
"""MODULE C - run the five supplied change tests (T1-T5) and report affected addresses.

Run:   python 05_build_changes.py
Reads: outputs/rules.json, outputs/addresses_resolved.json, starter_pack/dev/change_tests.json
Writes: outputs/changes.json (submission file) and outputs/test_report.json (PASS/FAIL self-check)
"""
from __future__ import annotations

import argparse
from collections import Counter

from nav import common as C
from nav import data
from nav.aliases import ALIASES
from nav.engine import lookup_all

TESTS = C.STARTER / "dev" / "change_tests.json"


def results_at(rules, facts, when, ids, states=None):
    """address_id -> {rule_id: (result, conflict_flag)} for the given rules on a date."""
    sel = {a: f for a, f in facts.items() if not states or f["state"] in states}
    snap = lookup_all(rules, sel, C.parse_date(when))
    out = {}
    for aid, entries in snap.items():
        out[aid] = {e["team_rule_id"]: (e["result"], e["conflict_flag"]) for e in entries if e["team_rule_id"] in ids}
    return out


def by_city(facts, ids):
    c = Counter(facts[a]["legal_city"] or "(outside in-scope cities)" for a in ids)
    return ", ".join(f"{k}: {v}" for k, v in sorted(c.items())) or "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default=None)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    if args.out_dir:
        C.set_out_dir(args.out_dir)
    rules = data.load_rules(args.rules)
    facts = data.load_facts()
    tests = C.read_json(TESTS)
    alias_to_ids = {a: [r["team_rule_id"] for r in rules if a in r.get("test_alias", [])] for a in ALIASES}

    changes, report = {}, {}
    for t in tests:
        tid = t["test_id"]
        missing = [a for a in t["rule_ids"] if not alias_to_ids.get(a)]
        ids = {i for a in t["rule_ids"] for i in alias_to_ids.get(a, [])}
        states = set(t.get("states") or [])
        affected, flagged, checks = [], [], []
        if missing:
            checks.append((False, f"rules for {missing} were not found - add their source text to extra_text/ (GUIDE step 6) and re-run 01 and 02"))

        if t["type"] == "as_of":
            before = results_at(rules, facts, t["as_of_before"], ids, states)
            after = results_at(rules, facts, t["as_of_after"], ids, states)
            for aid in before:
                rb = {v[0] for v in before[aid].values()}
                ra = {v[0] for v in after[aid].values()}
                if rb != ra:
                    affected.append(aid)
                if any(v[1] for v in list(before[aid].values()) + list(after[aid].values())):
                    flagged.append(aid)
            exp_b, exp_a = ("not_yet_effective", "applies")
            bad_b = [a for a in before if exp_b not in {v[0] for v in before[a].values()}]
            bad_a = [a for a in after if exp_a not in {v[0] for v in after[a].values()}]
            checks.append((not bad_b and bool(before), f"{t['as_of_before']}: every {'/'.join(sorted(states))} address is '{exp_b}' ({len(before)-len(bad_b)}/{len(before)})"))
            checks.append((not bad_a and bool(after), f"{t['as_of_after']}: every {'/'.join(sorted(states))} address is '{exp_a}' ({len(after)-len(bad_a)}/{len(after)})"))
            if tid == "T3":
                want = {a for a, f in facts.items() if f["legal_city"] in ("Jersey City, NJ", "Hoboken, NJ")}
                got = set(flagged)
                checks.append((want <= got and not (got - want), f"conflict flag on all Jersey City + Hoboken addresses and nothing else ({len(got & want)}/{len(want)} flagged, {len(got - want)} extra)"))
            notes = (f"{tid}: result changes between {t['as_of_before']} and {t['as_of_after']} for {len(affected)} "
                     f"addresses ({by_city(facts, affected)}). " + (f"{len(flagged)} flagged for human review (possible preemption)." if flagged else ""))

        elif t["type"] == "boundary":
            res = results_at(rules, facts, t["as_of"], ids)
            alias_of = {i: [a for a in t["rule_ids"] if i in alias_to_ids[a]][0] for i in ids}
            want_city = {"HOB-ALG-01": "Hoboken, NJ", "JC-ALG-01": "Jersey City, NJ"}
            wrong = []
            for aid, d in res.items():
                for rid, (result, _) in d.items():
                    if result == "applies" and facts[aid]["legal_city"] != want_city.get(alias_of[rid]):
                        wrong.append((aid, rid))
            affected = sorted(a for a, d in res.items() if any(v[0] == "applies" for v in d.values()))
            newark = [a for a in affected if facts[a]["legal_city"] == "Newark, NJ"]
            checks.append((bool(affected) and not wrong, f"each local ban appears only inside its own city (violations: {len(wrong)})"))
            checks.append((not newark, f"no local ban reported for Newark addresses ({len(newark)} found)"))
            notes = f"{tid}: ban applies only inside its own city limits. Affected: {by_city(facts, affected)}. Newark: 0."

        elif t["type"] == "pending":
            res = results_at(rules, facts, t["as_of"], ids, states)
            affected = sorted(a for a, d in res.items() if any(v[0] == "pending" for v in d.values()))
            ma = [a for a, f in facts.items() if f["state"] == "MA"]
            checks.append((set(affected) == set(ma) and bool(ma), f"all Massachusetts addresses listed as pending ({len(affected)}/{len(ma)})"))
            not_pending = [a for a, d in res.items() if any(v[0] in ("applies",) for v in d.values())]
            checks.append((not not_pending, "pending bills are never reported as 'applies'"))
            notes = f"{tid}: both bills are pending (NOT law). If enacted they would reach: {by_city(facts, affected)}."

        else:  # negative
            res = results_at(rules, facts, t["as_of"], ids, states)
            affected = sorted(a for a, d in res.items() if d)
            snap = lookup_all(rules, {a: f for a, f in facts.items() if f["state"] == "MA"}, C.parse_date(t["as_of"]))
            capped = [a for a, es in snap.items() for e in es
                      if next(r for r in rules if r["team_rule_id"] == e["team_rule_id"]).get("imposes_rent_cap")
                      and e["result"] in ("applies", "unknown", "superseded")]
            failed_ok = any(r["status"] == "failed" for r in rules if r["team_rule_id"] in ids)
            checks.append((not affected, f"affected set is empty ({len(affected)} found)"))
            checks.append((not capped, f"no rent cap reported for any Boston/Cambridge address ({len(capped)} found)"))
            checks.append((failed_ok, "the ballot question is recorded with status 'failed'"))
            notes = f"{tid}: the ballot question was struck (status failed), so no rent cap applies in Boston or Cambridge; affected set is empty."

        changes[tid] = {"affected_address_ids": sorted(affected), "conflict_flag_address_ids": sorted(set(flagged)), "notes": notes}
        report[tid] = {"title": t["title"], "pass": all(c[0] for c in checks), "checks": [{"ok": c[0], "what": c[1]} for c in checks],
                       "rule_ids_used": sorted(ids)}

    C.write_json(C.out_dir() / "changes.json", changes)
    C.write_json(C.out_dir() / "test_report.json", report)
    C.audit("changes", tests={k: {"affected": len(v["affected_address_ids"]), "pass": report[k]["pass"]} for k, v in changes.items()})

    print("Change tests\n" + "-" * 60)
    for tid, rep in report.items():
        print(f"{tid} {'PASS' if rep['pass'] else 'FAIL'}  {rep['title']}  (affected: {len(changes[tid]['affected_address_ids'])})")
        for c in rep["checks"]:
            print(f"     {'ok  ' if c['ok'] else 'FAIL'} {c['what']}")
    print(f"\nWrote {C.out_dir()/'changes.json'} and test_report.json\nNext: python 06_validate.py")


if __name__ == "__main__":
    main()
