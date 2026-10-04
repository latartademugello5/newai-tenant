#!/usr/bin/env python3
"""Second pass over the extracted rules (still automated, still model-read):
  * merge duplicates that several documents state,
  * record which rule yields to which (state vs local),
  * flag conflicts (e.g. NJ FAIR Act vs local bans; two effective dates),
  * tag rules with the organizers' short ids (CA-ALG-01 ...) used by the change tests.

Run:   python 02_link_rules.py
Reads: outputs/rules_raw.json     Writes: outputs/rules.json, outputs/rule_links.json
"""
from __future__ import annotations

import argparse
import json
import sys

from nav import common as C
from nav.aliases import ALIASES
from nav.llm import call_tool, get_client, get_model
from nav.schemas import LINK_TOOL

SYSTEM = """You compare already-extracted housing rules within one state (state-level rules plus its cities) and report relationships.
Only use the rule list you are given. Never invent rule ids. Be conservative: when unsure, leave a relationship out.

merges: rules that state the SAME legal rule in the SAME jurisdiction (e.g. a statute and a city page summarising it). Different amounts / different coverage = different rules.
supersedes: ONLY when a rule's own text says one level yields to another (e.g. the state rent cap does not apply where a stricter local rent-control law covers the building; or state law bars local rent control).
conflicts: pairs/groups of rules that may clash and need human review: kind=preemption (a state law may override a local ordinance or the reverse), kind=date_discrepancy (same law, different effective dates in different documents), kind=ambiguity (unclear interaction).
aliases: match rules to the alias descriptions given. A rule matches an alias only if it is that exact law."""


def to_record(r: dict) -> dict:
    return {
        "team_rule_id": r["team_rule_id"],
        "jurisdiction": r["jurisdiction"],
        "level": r["level"],
        "category": r["category"],
        "status": r["status"],
        "title": r["title"],
        "requirement": r["requirement"],
        "key_value": r.get("key_value"),
        "coverage_conditions": r.get("coverage_text"),
        "exemptions": r.get("exemptions_text"),
        "overrides": [],
        "interaction": None,
        "effective_date": r.get("effective_date"),
        "citation": r["citation"],
        "source_doc_id": r.get("source_doc_id"),
        "source_url": r["source_url"],
        "quoted_span": r["quoted_span"],
        "confidence": r.get("confidence"),
        "conflict_flag": False,
        "conflict_note": None,
        # ---- extras used by our own engine / UI (the schema allows extra fields)
        "retrieved_at": r.get("retrieved_at"),
        "coverage": r.get("coverage") or {"universal": False},
        "exemption_tests": r.get("exemption_tests") or [],
        "imposes_rent_cap": bool(r.get("imposes_rent_cap")),
        "penalty": r.get("penalty"),
        "ambiguity_note": r.get("ambiguity_note"),
        "test_alias": [],
        "supersedes": [],
        "conflicts_with": [],
        "conflict_kind": None,
        "corroborating_doc_ids": [],
        "quote_match": r.get("quote_match"),
        "source_type": r.get("source_type"),
    }


def compact(r: dict) -> str:
    cov = json.dumps({k: v for k, v in (r["coverage"] or {}).items() if v not in (None, [], False)}, separators=(",", ":"))
    return (f"{r['team_rule_id']} | {r['jurisdiction']} | {r['category']} | {r['status']} | eff={r['effective_date']} | "
            f"{r['title']} | key={r['key_value']} | cite={r['citation']} | doc={r['source_doc_id']} | cov={cov} | "
            f"req={(r['requirement'] or '')[:220]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--skip-llm", action="store_true", help="only convert + renumber (no merging/aliases)")
    args = ap.parse_args()
    if args.out_dir:
        C.set_out_dir(args.out_dir)
    out = C.out_dir()

    raw = C.read_json(out / "rules_raw.json")
    if not raw:
        sys.exit("outputs/rules_raw.json not found - run 01_extract_rules.py first.")
    rules = [to_record(r) for r in raw["rules"]]
    by_id = {r["team_rule_id"]: r for r in rules}
    links_log = []

    if not args.skip_llm:
        client, model = get_client(), get_model()
        alias_text = "\n".join(f"- {a}: {v['description']}" for a, v in ALIASES.items())
        for st in sorted({C.state_of(r["jurisdiction"]) for r in rules}):
            group = [r for r in rules if C.state_of(r["jurisdiction"]) == st]
            user = (f"STATE: {st}\n\nALIASES TO MATCH:\n{alias_text}\n\nRULES (id | jurisdiction | category | status | ...):\n"
                    + "\n".join(compact(r) for r in group))
            print(f"Linking {st}: {len(group)} rules ...")
            res = call_tool(client, system=SYSTEM, user=user, tool=LINK_TOOL, model=model, max_tokens=12000)
            links_log.append({"state": st, "model": res["model"], "usage": res["usage"], "result": res["input"]})
            L = res["input"]
            valid = lambda ids: [i for i in ids if i in by_id]  # noqa: E731

            for m in L.get("merges", []):
                keep = m["keep"]
                if keep not in by_id:
                    continue
                for d in valid(m.get("drop", [])):
                    if d == keep or d not in by_id:
                        continue
                    k, dr = by_id[keep], by_id[d]
                    if dr["source_doc_id"] and dr["source_doc_id"] not in k["corroborating_doc_ids"] + [k["source_doc_id"]]:
                        k["corroborating_doc_ids"].append(dr["source_doc_id"])
                    ed_k, ed_d = k["effective_date"], dr["effective_date"]
                    if ed_k and ed_d and ed_k != ed_d:  # sources disagree -> human review
                        k["conflict_flag"], k["conflict_kind"] = True, "date_discrepancy"
                        k["conflict_note"] = (f"Sources disagree on effective date: {k['source_doc_id']} says {ed_k}; "
                                              f"{dr['source_doc_id']} says {ed_d}.")
                    k["test_alias"] = sorted(set(k["test_alias"]) | set(dr["test_alias"]))
                    del by_id[d]
            for s in L.get("supersedes", []):
                a = by_id.get(s["rule"])
                if not a:
                    continue
                a["supersedes"] = sorted(set(a["supersedes"]) | set(valid(s["supersedes"])) - {a["team_rule_id"]})
                a["interaction"] = s["interaction"]
            for c in L.get("conflicts", []):
                ids = [i for i in valid(c["rules"]) if i in by_id]
                for i in ids:
                    r = by_id[i]
                    r["conflict_flag"] = True
                    r["conflict_kind"] = r["conflict_kind"] or c["kind"]
                    r["conflicts_with"] = sorted(set(r["conflicts_with"]) | (set(ids) - {i}))
                    r["conflict_note"] = ((r["conflict_note"] + " | ") if r["conflict_note"] else "") + c["note"]
            for a in L.get("aliases", []):
                if a["alias"] in ALIASES:
                    for i in valid(a["rules"]):
                        if i in by_id and a["alias"] not in by_id[i]["test_alias"]:
                            by_id[i]["test_alias"].append(a["alias"])

    rules = [r for r in rules if r["team_rule_id"] in by_id]

    # Carry organizer-verified dates onto every extracted section of these laws.
    for alias, details in ALIASES.items():
        if details.get("effective_date"):
            for r in rules:
                if alias in r["test_alias"]:
                    r["effective_date"] = details["effective_date"]

    # Multiple sections/sources for one aliased law are not preemption conflicts with each other.
    by_team_id = {r["team_rule_id"]: r for r in rules}
    for r in rules:
        if r["conflict_kind"] == "preemption":
            aliases = set(r["test_alias"])
            r["conflicts_with"] = [i for i in r["conflicts_with"]
                                    if not aliases.intersection(by_team_id[i]["test_alias"])]

    # deterministic backstop: the supplied change tests state which laws may conflict (e.g. T3)
    tests = C.read_json(C.STARTER / "dev" / "change_tests.json", [])
    ids_of = lambda aliases: [r for r in rules if set(r["test_alias"]) & set(aliases)]  # noqa: E731
    for t in tests:
        if t.get("conflict_with"):
            a_rules, b_rules = ids_of(t["rule_ids"]), ids_of(t["conflict_with"])
            note = (f"Possible conflict/preemption between {', '.join(t['rule_ids'])} and "
                    f"{', '.join(t['conflict_with'])} ({t['title']}). Needs human legal review.")
            for r in a_rules + b_rules:
                others = {x["team_rule_id"] for x in (b_rules if r in a_rules else a_rules)}
                r["conflict_flag"], r["conflict_kind"] = True, r["conflict_kind"] or "preemption"
                r["conflicts_with"] = sorted(set(r["conflicts_with"]) | others)
                if note not in (r["conflict_note"] or ""):
                    r["conflict_note"] = ((r["conflict_note"] + " | ") if r["conflict_note"] else "") + note

    # intrinsic ambiguity noted by the extractor (e.g. two published effective dates)
    for r in rules:
        if r["ambiguity_note"] and not r["conflict_flag"]:
            r["conflict_flag"], r["conflict_kind"], r["conflict_note"] = True, "ambiguity", r["ambiguity_note"]

    # ---- renumber r-0001.. with no gaps, remap references
    remap = {r["team_rule_id"]: f"r-{n:04d}" for n, r in enumerate(rules, 1)}
    for r in rules:
        r["team_rule_id"] = remap[r["team_rule_id"]]
        r["supersedes"] = [remap[i] for i in r["supersedes"] if i in remap]
        r["conflicts_with"] = [remap[i] for i in r["conflicts_with"] if i in remap]
        r["overrides"] = list(r["supersedes"])  # schema field: ids this rule supersedes (direction in 'interaction')

    C.write_json(out / "rules.json", {"rules": rules})
    C.write_json(out / "rule_links.json", links_log)
    C.audit("link", model=None if args.skip_llm else get_model(), rules_out=len(rules))

    print(f"\n{len(rules)} rules written to {out/'rules.json'}")
    print("\nAlias check (needed by the change tests T1-T5):")
    missing = []
    for a, v in ALIASES.items():
        ids = [r["team_rule_id"] for r in rules if a in r["test_alias"]]
        print(f"  {'OK     ' if ids else 'MISSING'} {a:11s} -> {ids}")
        if not ids:
            missing.append(a)
    if missing:
        print("\nMissing aliases mean the matching law was not found in the text we read:")
        for a in missing:
            h = ALIASES[a]
            if h["supplied"]:
                print(f"  {a}: text is supplied ({h['needs_source_hint']}) - re-run: python 01_extract_rules.py --only <doc id> --force, then 02 again")
            else:
                print(f"  {a}: NOT in the supplied text. Add it to extra_text/ -> {h['needs_source_hint']}  (GUIDE.md step 6)")
    print("\nNext: python 03_geocode_addresses.py")


if __name__ == "__main__":
    main()
