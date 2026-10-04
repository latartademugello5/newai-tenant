"""JSON schemas given to the model as 'tools' so its output is always well-formed."""

CATEGORIES = [
    "rent_increase_limits",
    "just_cause_eviction",
    "security_deposits",
    "application_screening_fees",
    "screening_restrictions",
    "algorithmic_rent_setting",
]

CONSTRAINT_PROPS = {
    "min_units": {"type": ["integer", "null"], "description": "Covered only if the building has AT LEAST this many units."},
    "max_units": {"type": ["integer", "null"], "description": "Covered only if the building has AT MOST this many units."},
    "built_on_or_before": {"type": ["string", "null"], "description": "ISO date. Covered only if first built / certificate of occupancy ON OR BEFORE this date (e.g. 1979-06-13)."},
    "built_before": {"type": ["string", "null"], "description": "ISO date. Covered only if built strictly BEFORE this date."},
    "built_on_or_after": {"type": ["string", "null"], "description": "ISO date. Covered only if built ON OR AFTER this date."},
    "built_after": {"type": ["string", "null"], "description": "ISO date. Covered only if built strictly AFTER this date."},
    "min_building_age_years": {"type": ["integer", "null"], "description": "Rolling rule: covered only if the building is at least N years old on the query date (e.g. 15 for 'issued a certificate of occupancy more than 15 years ago')."},
    "cutoff_is_certificate_of_occupancy": {"type": "boolean", "description": "True if the date cutoff is defined by certificate of occupancy / first occupancy rather than year built."},
    "needs_facts": {"type": "array", "items": {"type": "string"}, "description": "Facts needed to decide coverage that are NOT unit count or year built, e.g. owner_type, owner_occupied, tenancy_start_date, rent_amount, tenant_income, landlord_unit_total_in_state, subsidy_status."},
}

EXTRACT_TOOL = {
    "name": "record_rules",
    "description": "Record every housing rule found in the document text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "rules": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "jurisdiction": {"type": "string", "description": "Must be one of the allowed jurisdictions given in the user message."},
                        "category": {"type": "string", "enum": CATEGORIES},
                        "status": {"type": "string", "enum": ["in_force", "not_yet_effective", "pending", "failed"],
                                   "description": "As of 2026-10-01."},
                        "title": {"type": "string"},
                        "requirement": {"type": "string", "description": "One or two plain-language sentences."},
                        "key_value": {"type": ["string", "null"], "description": "Headline number or formula."},
                        "coverage_text": {"type": ["string", "null"], "description": "Plain-language summary of who/what is covered."},
                        "coverage": {
                            "type": "object",
                            "description": "Machine-readable coverage. Leave a constraint null when the text does not state it. 'universal' = true when the rule covers all residential rentals in the jurisdiction with no unit-count or age limit.",
                            "properties": {"universal": {"type": "boolean"}, **CONSTRAINT_PROPS},
                            "required": ["universal"],
                        },
                        "exemptions_text": {"type": ["string", "null"]},
                        "exemption_tests": {
                            "type": "array",
                            "description": "One entry per exemption. Be honest: if an exemption depends on a fact we do not have (owner type, tenancy date...), kind = unavailable_fact.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "description": {"type": "string"},
                                    "kind": {"type": "string", "enum": ["measurable", "unavailable_fact", "not_applicable_to_multifamily"],
                                             "description": "measurable = decided by unit count / building age alone; unavailable_fact = needs data like owner type; not_applicable_to_multifamily = could never apply to an assessor-classified apartment building (hotels, dorms, seasonal, mobile homes, single-family...)."},
                                    "constraints": {"type": "object", "properties": CONSTRAINT_PROPS,
                                                    "description": "Conditions under which the exemption APPLIES (e.g. max_units 2 for 'owner-occupied buildings with 2 or fewer units')."},
                                },
                                "required": ["description", "kind"],
                            },
                        },
                        "effective_date": {"type": ["string", "null"], "description": "YYYY, YYYY-MM or YYYY-MM-DD as stated in the text."},
                        "citation": {"type": "string"},
                        "quoted_span": {"type": "string", "description": "EXACT sentence(s) copied from the text. At least 20 characters."},
                        "penalty": {"type": ["string", "null"]},
                        "imposes_rent_cap": {"type": "boolean", "description": "True only for rent_increase_limits rules that actually cap rent increases (not for rules that ban caps)."},
                        "ambiguity_note": {"type": ["string", "null"], "description": "Mention conflicting dates or unclear text, else null."},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["jurisdiction", "category", "status", "title", "requirement", "coverage",
                                 "exemption_tests", "citation", "quoted_span", "confidence", "imposes_rent_cap"],
                },
            }
        },
        "required": ["rules"],
    },
}

LINK_TOOL = {
    "name": "record_links",
    "description": "Record duplicates, precedence relationships, conflicts and law aliases among the extracted rules.",
    "input_schema": {
        "type": "object",
        "properties": {
            "merges": {
                "type": "array",
                "description": "Groups of rules that state the SAME legal rule (same jurisdiction, same requirement). keep = best (official source, most complete).",
                "items": {"type": "object", "properties": {
                    "keep": {"type": "string"}, "drop": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"}}, "required": ["keep", "drop"]},
            },
            "supersedes": {
                "type": "array",
                "description": "Use ONLY when the text says one level yields to another (e.g. state cap does not apply where a stricter local rent-control law covers the building).",
                "items": {"type": "object", "properties": {
                    "rule": {"type": "string"}, "supersedes": {"type": "array", "items": {"type": "string"}},
                    "interaction": {"type": "string"}}, "required": ["rule", "supersedes", "interaction"]},
            },
            "conflicts": {
                "type": "array",
                "items": {"type": "object", "properties": {
                    "rules": {"type": "array", "items": {"type": "string"}},
                    "kind": {"type": "string", "enum": ["preemption", "date_discrepancy", "ambiguity"]},
                    "note": {"type": "string"}}, "required": ["rules", "kind", "note"]},
            },
            "aliases": {
                "type": "array",
                "description": "For each alias that matches a rule, list the rule id(s). Omit aliases with no matching rule.",
                "items": {"type": "object", "properties": {
                    "alias": {"type": "string"}, "rules": {"type": "array", "items": {"type": "string"}}},
                    "required": ["alias", "rules"]},
            },
        },
        "required": ["merges", "supersedes", "conflicts", "aliases"],
    },
}
