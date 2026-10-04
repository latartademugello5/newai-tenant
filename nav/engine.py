"""Deterministic coverage engine (Modules B and C).

The language model only EXTRACTS structure from the law (script 01/02).
Deciding whether a rule covers an address is plain code with three-valued logic:
    True / False / None (= unknown, because a needed fact is missing).
Same input -> same output, and every decision keeps a trace of the facts it used.
"""
from __future__ import annotations

import datetime as dt
import re

from .common import parse_partial_date, years_before

KNOWN_FACTS = {"year_built", "units", "unit_count", "number_of_units", "use_code", "city", "jurisdiction",
               "property_type", "year_built_or_certificate_of_occupancy"}
CATEGORY_ORDER = ["rent_increase_limits", "just_cause_eviction", "security_deposits",
                  "application_screening_fees", "screening_restrictions", "algorithmic_rent_setting"]
RESULT_ORDER = {"applies": 0, "superseded": 1, "unknown": 2, "not_yet_effective": 3, "pending": 4}


# ------------------------------------------------------------------ facts
def to_int(v):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


def unit_range_hint(desc: str):
    """Assessor use descriptions like '4-8-UNIT-APT' or 'Apartment 5 to 14 Units' imply a unit range."""
    d = (desc or "").lower()
    m = re.search(r"(\d+)\s*(?:to|-)\s*(\d+)\s*[- ]?\s*units?", d)
    if m:
        return int(m[1]), int(m[2])
    m = re.search(r"(\d+)\s*units?\s*or\s*more", d)
    if m:
        return int(m[1]), None
    m = re.search(r"\(\s*(\d+)\+\s*units?\s*\)", d)
    if m:
        return int(m[1]), None
    if re.search(r"(?:five|5)\s*or\s*more", d):
        return 5, None
    m = re.search(r">\s*(\d+)\s*-?\s*unit", d)
    if m:
        return int(m[1]) + 1, None
    return None, None


def build_facts(addr: dict, resolved: dict | None) -> dict:
    year = to_int(addr.get("year_built"))
    units = to_int(addr.get("units"))
    if units:
        lo, hi, src = units, units, "assessor unit count"
    else:
        lo, hi = unit_range_hint(addr.get("use_description", ""))
        src = "assessor use description (range only)" if lo else None
    resolved = resolved or {}
    return {
        "address_id": addr["address_id"],
        "street_address": addr["street_address"],
        "postal_city": addr["postal_city"],
        "state": addr["state"],
        "year_built": year,
        "units": units,
        "units_lo": lo, "units_hi": hi, "units_src": src,
        "use_code": addr.get("use_code"),
        "use_description": addr.get("use_description"),
        "legal_city": resolved.get("legal_city"),
        "hint_city": resolved.get("hint_city"),
        "county": resolved.get("county"),
        "city_method": resolved.get("method", "none"),
        "city_confidence": resolved.get("confidence", "none"),
        "city_note": resolved.get("note"),
    }


# ------------------------------------------------------------------ constraints
def _tri_and(vals):
    if any(v is False for v in vals):
        return False
    if any(v is None for v in vals):
        return None
    return True


def _year_pred(kind: str, D: dt.date, facts: dict):
    y = facts["year_built"]
    if not y:
        return None, "year built is missing"
    lo, hi = dt.date(y, 1, 1), dt.date(y, 12, 31)
    if kind == "built_on_or_before":
        r = True if hi <= D else False if lo > D else None
    elif kind == "built_before":
        r = True if hi < D else False if lo >= D else None
    elif kind == "built_on_or_after":
        r = True if lo >= D else False if hi < D else None
    else:  # built_after
        r = True if lo > D else False if hi <= D else None
    if r is None:
        return None, f"built {y} is the same year as the cutoff {D.isoformat()}, so the exact date matters and is not in the data"
    return r, f"built {y}"


def _unit_pred(kind: str, N: int, facts: dict):
    lo, hi = facts["units_lo"], facts["units_hi"]
    if lo is None:
        return None, "unit count is missing"
    if kind == "min_units":
        r = True if lo >= N else False if (hi is not None and hi < N) else None
    else:
        r = True if (hi is not None and hi <= N) else False if lo > N else None
    shown = f"{lo}" if lo == hi else f"{lo}-{hi if hi is not None else '+'}"
    return r, f"{shown} units ({facts['units_src']})"


YEAR_KEYS = {"built_on_or_before": "built on or before", "built_before": "built before",
             "built_on_or_after": "built on or after", "built_after": "built after"}


def eval_constraints(cons: dict | None, facts: dict, as_of: dt.date):
    """-> (tri_state, trace[list of dict], measurable: bool)"""
    cons = cons or {}
    trace, vals, measurable = [], [], False

    def add(fact, required, r, note):
        trace.append({"fact": fact, "required": required,
                      "outcome": "met" if r is True else "not_met" if r is False else "unknown", "note": note})
        vals.append(r)

    for k in ("min_units", "max_units"):
        if cons.get(k) is not None:
            measurable = True
            r, note = _unit_pred(k, cons[k], facts)
            add("units", f"{'at least' if k == 'min_units' else 'at most'} {cons[k]} units", r, note)
    for k, label in YEAR_KEYS.items():
        if cons.get(k):
            D = parse_partial_date(cons[k])
            if D:
                measurable = True
                r, note = _year_pred(k, D, facts)
                if cons.get("cutoff_is_certificate_of_occupancy"):
                    note += "; the legal cutoff uses the certificate of occupancy, year built is only a proxy"
                add("year_built", f"{label} {D.isoformat()}", r, note)
    if cons.get("min_building_age_years"):
        measurable = True
        n = int(cons["min_building_age_years"])
        D = years_before(as_of, n)
        r, note = _year_pred("built_on_or_before", D, facts)
        add("year_built", f"at least {n} years old on {as_of.isoformat()} (built on or before {D.isoformat()})", r, note)
    missing = [f for f in (cons.get("needs_facts") or []) if f.lower() not in KNOWN_FACTS]
    if missing:
        trace.append({"fact": ", ".join(missing), "required": "needed to decide", "outcome": "unknown",
                      "note": "not available in the public data supplied"})
    tri = _tri_and(vals)
    if tri is True and missing:
        tri = None
    return tri, trace, measurable


# ------------------------------------------------------------------ time
def temporal_status(rule: dict, as_of: dt.date) -> str:
    st = rule["status"]
    if st in ("pending", "failed"):
        return st
    eff = parse_partial_date(rule.get("effective_date"))
    if eff is None:
        return st
    return "in_force" if as_of >= eff else "not_yet_effective"


# ------------------------------------------------------------------ one rule
def evaluate_rule(rule: dict, facts: dict, as_of: dt.date, unverified_city: bool = False) -> dict | None:
    """Return None if the rule does not apply to this address; else a result dict."""
    status = temporal_status(rule, as_of)
    if status == "failed":
        return None
    cov_state, trace, _ = eval_constraints(rule.get("coverage"), facts, as_of)
    if cov_state is False:
        return None

    # exemptions
    ex_notes, ex_unknown = [], False
    for ex in rule.get("exemption_tests") or []:
        kind = ex.get("kind")
        if kind == "not_applicable_to_multifamily":
            ex_notes.append(f"Exemption '{ex['description']}' cannot describe an apartment building.")
            continue
        etri, etrace, measurable = eval_constraints(ex.get("constraints"), facts, as_of)
        if measurable and etri is False:
            ex_notes.append(f"Exemption '{ex['description']}' does not apply ("
                            + "; ".join(t["note"] for t in etrace if t["outcome"] == "not_met") + ").")
        elif measurable and etri is True and kind == "measurable":
            return None  # exempt
        else:
            ex_unknown = True
            why = "; ".join(t["note"] for t in etrace if t["outcome"] == "unknown") or "depends on facts not in the data"
            ex_notes.append(f"Exemption '{ex['description']}' cannot be ruled out ({why}).")

    scope = "statewide" if rule["level"] == "state" else f"city of {rule['jurisdiction'].split(',')[0]}"
    cov_bits = [f"{t['fact']}: {t['note']} ({'meets' if t['outcome']=='met' else 'fails' if t['outcome']=='not_met' else 'unclear vs'} '{t['required']}')"
                for t in trace]
    if status == "pending":
        result = "pending"
        head = f"Pending bill/proposal ({scope}) - NOT law. This is who it would cover if enacted."
    elif status == "not_yet_effective":
        result = "not_yet_effective"
        eff = rule.get("effective_date") or "a future date"
        head = f"Enacted ({scope}) but not yet effective: takes effect {eff}, after the as-of date {as_of.isoformat()}."
    else:
        if cov_state is True and not ex_unknown:
            result = "applies"
            head = f"In force ({scope}) as of {as_of.isoformat()} and covers this building."
        else:
            result = "unknown"
            head = f"In force ({scope}) but coverage cannot be confirmed from the data we have."
    if cov_state is None and result in ("pending", "not_yet_effective"):
        head += " Coverage details are not fully confirmed."
    if unverified_city:
        result = "unknown" if result == "applies" else result
        head = ("The legal city of this address could not be verified (geocoder had no confident match), so this "
                f"{scope} rule may or may not apply. ") + head
    explanation = " ".join([head] + ([("Facts checked: " + "; ".join(cov_bits) + ".")] if cov_bits else [])
                           + ex_notes)
    return {"result": result, "explanation": explanation, "trace": trace + [], "coverage_state": cov_state,
            "exemption_unknown": ex_unknown}


# ------------------------------------------------------------------ one address
def candidate_rules(rules: list[dict], facts: dict):
    for r in rules:
        if r["jurisdiction"] == facts["state"]:
            yield r, False
        elif r["level"] == "city" and facts["legal_city"] and r["jurisdiction"] == facts["legal_city"]:
            yield r, False
        elif (r["level"] == "city" and not facts["legal_city"] and facts["city_confidence"] in ("none", "low")
              and facts["hint_city"] == r["jurisdiction"] and facts["city_method"] == "unresolved"):
            yield r, True  # city could not be verified


def lookup_address(rules: list[dict], facts: dict, as_of: dt.date) -> list[dict]:
    entries: dict[str, dict] = {}
    unverified_ids = set()
    for r, unverified in candidate_rules(rules, facts):
        ev = evaluate_rule(r, facts, as_of, unverified)
        if ev is None:
            continue
        if unverified:
            unverified_ids.add(r["team_rule_id"])
        conf = r.get("confidence") if r.get("confidence") is not None else 0.7
        if facts["units_src"] and "range" in (facts["units_src"] or ""):
            conf = min(conf, 0.75)
        if ev["result"] == "unknown":
            conf = min(conf, 0.5)
        entries[r["team_rule_id"]] = {
            "team_rule_id": r["team_rule_id"], "result": ev["result"], "explanation": ev["explanation"],
            "conflict_flag": False, "confidence": round(float(conf), 2), "_rule": r,
        }
    # ---- precedence: a rule that applies and supersedes another one overrides it
    for rid, e in list(entries.items()):
        for sid in e["_rule"].get("supersedes") or []:
            s = entries.get(sid)
            if not s:
                continue
            if e["result"] == "applies" and s["result"] in ("applies", "unknown"):
                s["result"] = "superseded"
                s["explanation"] = (f"Covered, but {e['_rule']['title']} ({e['_rule']['citation']}) governs instead at this "
                                    f"address. " + (e["_rule"].get("interaction") or "") + " | Original check: " + s["explanation"])
            elif e["result"] == "unknown" and s["result"] == "applies":
                s["result"] = "unknown"
                s["explanation"] = (f"This rule applies unless {e['_rule']['title']} ({e['_rule']['citation']}) covers "
                                    f"this building, and that cannot be confirmed from the data. | " + s["explanation"])
    # ---- conflicts: flag when conflicting rules are both live here, or the rule itself is ambiguous
        live = {rid for rid, e in entries.items()
            if e["result"] in ("applies", "unknown", "not_yet_effective", "pending") and rid not in unverified_ids}
    for rid, e in entries.items():
        r = e["_rule"]
        if r.get("conflict_flag"):
            if r.get("conflict_kind") in ("date_discrepancy", "ambiguity"):
                e["conflict_flag"] = True
            elif set(r.get("conflicts_with") or []) & live and rid in live:
                e["conflict_flag"] = True
            if e["conflict_flag"] and r.get("conflict_note"):
                e["explanation"] += " CONFLICT FLAG (human review): " + r["conflict_note"]
    out = []
    for e in sorted(entries.values(), key=lambda e: (CATEGORY_ORDER.index(e["_rule"]["category"])
                                                      if e["_rule"]["category"] in CATEGORY_ORDER else 99,
                                                      RESULT_ORDER.get(e["result"], 9), e["team_rule_id"])):
        e = {k: v for k, v in e.items() if k != "_rule"}
        out.append(e)
    return out


def lookup_all(rules, facts_by_id: dict, as_of: dt.date) -> dict[str, list[dict]]:
    return {aid: lookup_address(rules, f, as_of) for aid, f in facts_by_id.items()}
