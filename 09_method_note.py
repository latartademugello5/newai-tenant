#!/usr/bin/env python3
"""Fill the one-page method note with real numbers from your run.  Run: python 09_method_note.py
Writes outputs/METHOD_NOTE.md  (edit the 'Limitations' and 'Team' lines, then export to PDF if you like)."""
from __future__ import annotations

import json
from collections import Counter

from nav import common as C
from nav import data


def main():
    out = C.out_dir()
    rules = data.load_rules()
    lk = C.read_json(out / "lookups.json")["lookups"]
    rep = C.read_json(out / "test_report.json", {})
    audit = [json.loads(l) for l in (out / "audit_log.jsonl").read_text().splitlines()] if (out / "audit_log.jsonl").exists() else []
    ext = next((a for a in reversed(audit) if a["step"] == "extract"), {})
    geo = next((a for a in reversed(audit) if a["step"] == "geocode"), {})
    res = Counter(e["result"] for v in lk.values() for e in v)
    tot = sum(res.values()) or 1
    flags = sum(e["conflict_flag"] for v in lk.values() for e in v)
    conf = [r["team_rule_id"] for r in rules if r.get("conflict_flag")]
    md = f"""# Rental Housing Law Navigator - method note

**Not legal advice.** Prototype built only from public law text and public data; not reviewed by counsel.

## What it does
For each of {len(lk)} sample addresses (CA, NJ, MA) it lists which rental-housing rules apply on a query date (default {lk and C.read_json(out/'lookups.json')['as_of']}), with plain-language explanation, citation, quoted source text, retrieval date and as-of date. It also runs the five supplied change cases.

## Pipeline
1. **Extract (Module A, automated).** {ext.get('model','an LLM')} reads each of {len(ext.get('docs', []))} corpus documents (long ones in chunks) and returns structured records via a forced JSON schema: category, jurisdiction, requirement, coverage conditions, exemptions, effective date, status, penalty, citation, quoted span. **Guard:** a record is kept only if its quoted span is found in the source text (whitespace/quote-insensitive); otherwise it is dropped and logged. {ext.get('rules_rejected', '?')} candidate records were rejected this way. Source URL, retrieval date and jurisdiction come from the manifest in code, never from the model.
2. **Link (automated).** A second model pass merges duplicates, records which rule yields to which, flags possible conflicts and tags the organizers' test laws. Result: **{len(rules)} rules**.
3. **Resolve (Module B).** The US Census Geocoder maps each address to its legal city and county (mailing city is not trusted). Methods used: {geo.get('methods', {})}.
4. **Apply (Module B).** Deterministic code, not the model, tests coverage with three-valued logic (true / false / unknown). Missing year built or unit count, a building built in a cutoff year, or an exemption that depends on data we lack (e.g. owner type) yields **unknown**. State rules superseded by a covering local rule are reported as **superseded**.
5. **Track (Module C).** Rule status is recomputed for any as-of date from effective dates; enacted, not-yet-effective, pending and failed law are kept separate. T1-T5 self-check: {', '.join(f"{k} {'PASS' if v['pass'] else 'FAIL'}" for k, v in rep.items())}.

## Results (as of default date)
Rule results: {dict(res)}; {res['unknown']/tot:.0%} unknown; {flags} conflict flags for human review.

## Responsible design
Every answer cites source text and retrieval date and shows an as-of date; enacted vs pending is explicit; unknown is preferred to guessing; conflicts (e.g. NJ FAIR Act vs Jersey City/Hoboken bans, differing published effective dates) are flagged; every run is appended to `audit_log.jsonl` with model, prompt version and SHA-256 of each source document so another person can reproduce it. No non-public data is used.

## Limitations
- Extraction quality depends on the model; a quote guard prevents invented text but not every misreading. Human review is recommended for flagged and low-confidence rules.
- Parcel data lacks owner type, certificate-of-occupancy dates and some unit counts, so many coverage answers are honestly *unknown*.
- Rules flagged with conflicts: {', '.join(conf) or 'none'}.
- Link-only sources were added manually from public pages (see `extra_text/`).

## Reproduce
`pip install -r requirements.txt`; set `ANTHROPIC_API_KEY`; run scripts `01`..`07` in order. Team: <fill in>.
"""
    (out / "METHOD_NOTE.md").write_text(md, encoding="utf-8")
    print("Wrote", out / "METHOD_NOTE.md")


if __name__ == "__main__":
    main()
