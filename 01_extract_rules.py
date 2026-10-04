#!/usr/bin/env python3
"""MODULE A - read every corpus document with Claude and output structured rule records.

Run:   python 01_extract_rules.py                 (all documents)
       python 01_extract_rules.py --only D069     (one document - do this first as a smoke test)
Output: outputs/rules_raw.json   (+ outputs/rejected_rules.jsonl, outputs/extraction_cache/*)

Safe to re-run: finished chunks are cached, so a crash never costs you money twice.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from nav import common as C
from nav.llm import TruncatedOutput, call_tool, get_client, get_model
from nav.schemas import CATEGORIES, EXTRACT_TOOL
from nav.textcheck import Haystack

CHUNK_CHARS = 26000
OVERLAP = 1500

SYSTEM = f"""You are a careful legal-text extraction engine for a rental-housing-law research prototype.
You read ONE document (or one chunk of a longer document) and record one structured record for every distinct rule it states in six categories:
{', '.join(CATEGORIES)}.

STRICT RULES
1. Use ONLY the text provided. Never add rules, numbers, section numbers or dates from outside knowledge. Unknown -> null.
2. Skip anything outside the six categories (habitability, zoning, general discrimination law, eviction procedure details that are not just-cause rules, etc.).
3. The document's issuing jurisdiction is given in the user message. Record only rules THAT jurisdiction imposes. If a city web page merely explains state law, skip it unless the page is clearly the primary source for that rule.
4. One record per distinct rule (one requirement / prohibition / limit with its own coverage). Do not split one sentence into many records and do not merge unrelated requirements.
5. quoted_span = 1-3 consecutive sentences copied EXACTLY from the text that directly support the record (line breaks and extra spaces do not matter). Never paraphrase, never join pieces from different places, minimum 20 characters.
6. status is as of 2026-10-01:
   in_force = law in effect today; not_yet_effective = enacted but effective date is after 2026-10-01;
   pending = a bill/proposal that has not become law; failed = struck down, rejected or withdrawn.
7. effective_date uses ISO form (YYYY, YYYY-MM or YYYY-MM-DD) exactly as the text states it; null if not stated. If the text gives conflicting dates, put the date from the official text in effective_date and describe the conflict in ambiguity_note.
8. citation = the official cite as written in the document or its standard form (e.g. 'Cal. Civ. Code § 1947.12', 'N.J.S.A. 46:8-21.2', 'P.L. 2026, c.43', 'Bill S.2983'). If none is given, use the document title. Never invent section numbers.
9. coverage: fill machine-readable limits ONLY when the text states them (units, year-built / certificate-of-occupancy cutoffs, rolling building age). Use universal=true when the rule covers every residential rental in the jurisdiction. List in needs_facts any OTHER facts coverage depends on (owner type, tenancy start date, etc.).
10. exemption_tests: one per exemption. kind=measurable only if unit count or building age alone decides it (put the conditions under which the exemption APPLIES in constraints). kind=unavailable_fact if it needs owner type, rent level, tenant status, etc. kind=not_applicable_to_multifamily for exemptions that could never describe an assessor-classified apartment building (hotels, dorms, seasonal/transient, mobile homes, single-family homes...).
11. confidence is 0-1. Use below 0.6 for summary pages, ambiguous text or incomplete rules.
12. If the text contains no rules in scope, return an empty rules array.
"""


def chunk_text(body: str) -> list[str]:
    if len(body) <= CHUNK_CHARS:
        return [body]
    chunks, start = [], 0
    while start < len(body):
        end = min(start + CHUNK_CHARS, len(body))
        if end < len(body):  # break on a line boundary
            nl = body.rfind("\n", start + CHUNK_CHARS // 2, end)
            if nl != -1:
                end = nl
        chunks.append(body[start:end])
        if end >= len(body):
            break
        start = max(end - OVERLAP, start + 1)
    return chunks


def build_user_message(doc: dict, row: dict, allowed: list[str], chunk: str, i: int, n: int) -> str:
    return (
        f"DOCUMENT METADATA\n"
        f"doc_id: {doc['doc_id']}\n"
        f"source_url: {doc['url']}\n"
        f"source_type: {row.get('source_type', '')}\n"
        f"allowed jurisdiction values: {allowed}\n"
        f"chunk: {i + 1} of {n}\n\n"
        f"TEXT (between the markers)\n<<<BEGIN>>>\n{chunk}\n<<<END>>>"
    )


def extract_chunk(client, model, doc, row, allowed, chunk, i, n, cache_dir: Path, force: bool, depth=0):
    key = C.sha256_text(f"{C.PROMPT_VERSION}|{model}|{SYSTEM}|{chunk}")[:16]
    cache = cache_dir / f"{doc['doc_id']}__{i}__{key}.json"
    if cache.exists() and not force:
        return json.loads(cache.read_text(encoding="utf-8")), True
    user = build_user_message(doc, row, allowed, chunk, i, n)
    try:
        res = call_tool(client, system=SYSTEM, user=user, tool=EXTRACT_TOOL, model=model)
    except TruncatedOutput:
        if depth >= 3 or len(chunk) < 4000:
            raise
        mid = chunk.rfind("\n", 0, len(chunk) // 2)
        mid = mid if mid > 0 else len(chunk) // 2
        out = {"rules": [], "model": model, "usage": {"in": 0, "out": 0}}
        for j, part in enumerate((chunk[:mid], chunk[mid:])):
            sub, _ = extract_chunk(client, model, doc, row, allowed, part, i, n, cache_dir, force, depth + 1)
            out["rules"] += sub["rules"]
        cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return out, False
    out = {"rules": res["input"].get("rules", []), "model": res["model"], "usage": res["usage"]}
    cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out, False


def process_doc(client, model, doc_id, manifest, cache_dir, force):
    row = manifest[doc_id]
    doc = C.read_doc(doc_id)
    allowed = C.doc_jurisdictions(row)
    hay = Haystack(doc["raw"])
    chunks = chunk_text(doc["body"])
    kept, rejected, usage, cached = [], [], {"in": 0, "out": 0}, 0
    for i, chunk in enumerate(chunks):
        out, was_cached = extract_chunk(client, model, doc, row, allowed, chunk, i, len(chunks), cache_dir, force)
        cached += was_cached
        usage["in"] += out["usage"]["in"]
        usage["out"] += out["usage"]["out"]
        for r in out["rules"]:
            # ---- anti-hallucination: the quoted span must exist in the document
            span, method, score = hay.locate(r.get("quoted_span", ""))
            if span is None:
                rejected.append({"doc_id": doc_id, "reason": "quoted_span not found in source", "score": score, "rule": r})
                continue
            r = dict(r)
            r["quoted_span"] = span  # the document's own characters
            r["quote_match"] = method
            # ---- metadata comes from the manifest in CODE, never from the model
            jur = r.get("jurisdiction")
            if jur not in allowed:
                jur = allowed[0]
            r["jurisdiction"] = jur
            r["level"] = C.level_of(jur)
            r["source_doc_id"] = doc_id
            r["source_url"] = doc["url"] or row["url"]
            r["retrieved_at"] = C.iso_retrieved(doc["retrieved"] or row.get("retrieved_at", ""))
            r["source_type"] = row.get("source_type", "")
            r["chunk"] = i
            kept.append(r)
    return doc_id, kept, rejected, usage, len(chunks), cached


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="doc ids, e.g. D069 D022")
    ap.add_argument("--force", action="store_true", help="ignore cache")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    if args.out_dir:
        C.set_out_dir(args.out_dir)
    out = C.out_dir()
    cache_dir = out / "extraction_cache"
    cache_dir.mkdir(exist_ok=True)

    manifest = C.load_manifest()
    doc_ids = C.iter_doc_ids(args.only)
    if not doc_ids:
        sys.exit("No documents found. Did you copy the starter pack into starter_pack/ ?")
    extra = [d for d in doc_ids if C.read_doc(d)["is_extra"]]
    model = get_model()
    client = get_client()
    print(f"Model: {model}\nDocuments to read: {len(doc_ids)} (of which {len(extra)} from extra_text/)")

    results, lock = {}, threading.Lock()
    rejected_all, total_usage = [], {"in": 0, "out": 0}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process_doc, client, model, d, manifest, cache_dir, args.force): d for d in doc_ids}
        for fut in as_completed(futs):
            d = futs[fut]
            try:
                doc_id, kept, rejected, usage, nchunks, cached = fut.result()
            except Exception as e:  # keep going; report at the end
                print(f"  !! {d} FAILED: {type(e).__name__}: {e}")
                results[d] = None
                continue
            with lock:
                results[doc_id] = kept
                rejected_all += rejected
                total_usage["in"] += usage["in"]
                total_usage["out"] += usage["out"]
            print(f"  {doc_id}: {len(kept):3d} rules kept, {len(rejected)} rejected  ({nchunks} chunk(s), {cached} cached)")

    failed = sorted(d for d, v in results.items() if v is None)
    rules = []
    for d in sorted(k for k, v in results.items() if v is not None):
        rules += results[d]
    for n, r in enumerate(rules, 1):
        r["team_rule_id"] = f"r-{n:04d}"

    C.write_json(out / "rules_raw.json", {"model": model, "prompt_version": C.PROMPT_VERSION, "rules": rules})
    with open(out / "rejected_rules.jsonl", "w", encoding="utf-8") as f:
        for r in rejected_all:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    C.audit("extract", model=model, prompt_version=C.PROMPT_VERSION, docs=doc_ids, rules_kept=len(rules),
            rules_rejected=len(rejected_all), failed_docs=failed, tokens=total_usage,
            doc_sha256={d: C.sha256_text(C.read_doc(d)["raw"]) for d in doc_ids})
    print(f"\nKept {len(rules)} rules, rejected {len(rejected_all)} (quote not found in source).")
    print(f"Tokens used: {total_usage['in']:,} in / {total_usage['out']:,} out")
    if failed:
        print(f"FAILED documents (re-run to retry): {failed}")
    print(f"Wrote {out/'rules_raw.json'}\nNext: python 02_link_rules.py")


if __name__ == "__main__":
    main()
