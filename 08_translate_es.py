#!/usr/bin/env python3
"""OPTIONAL stretch goal: Spanish titles + plain-language requirements for the website's EN/ES toggle.

Run:   python 08_translate_es.py        then re-run  python 07_export_web.py
Writes: outputs/rules_es.json   (rule explanations in the site's address view stay English)
"""
from __future__ import annotations

from nav import common as C
from nav import data
from nav.llm import call_tool, get_client, get_model

TOOL = {"name": "record_translations", "description": "Spanish translations", "input_schema": {
    "type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "string"}, "title": {"type": "string"}, "requirement": {"type": "string"}},
        "required": ["id", "title", "requirement"]}}}, "required": ["items"]}}
SYSTEM = ("Translate housing-law rule titles and plain-language requirements from English to clear, neutral Latin-American "
          "Spanish for tenants. Keep numbers, dates, section numbers and legal names exactly. Do not add or remove meaning. "
          "Do not translate statute citations.")


def main():
    rules, client, model = data.load_rules(), get_client(), get_model()
    out = {}
    for i in range(0, len(rules), 25):
        batch = rules[i:i + 25]
        user = "\n".join(f"{r['team_rule_id']} || {r['title']} || {r['requirement']}" for r in batch)
        res = call_tool(client, system=SYSTEM, user=user, tool=TOOL, model=model)
        for it in res["input"]["items"]:
            out[it["id"]] = {"title": it["title"], "requirement": it["requirement"]}
        print(f"translated {min(i + 25, len(rules))}/{len(rules)}")
    C.write_json(C.out_dir() / "rules_es.json", out)
    C.audit("translate_es", model=model, n=len(out))
    print("Wrote outputs/rules_es.json. Now run: python 07_export_web.py")


if __name__ == "__main__":
    main()
