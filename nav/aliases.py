"""The organizers refer to specific laws by short ids (CA-ALG-01 ...).
Our rule ids are our own (r-0001 ...). After extraction, a linking pass tags
each rule with the alias(es) it matches, so the change tests can find them.
"""

ALIASES = {
    "CA-ALG-01": {
        "description": "California AB 325 and/or SB 763: Cartwright Act amendments about common pricing algorithms / "
                       "coercive use of algorithmic pricing (rent-setting software). Effective 2026-01-01.",
        "effective_date": "2026-01-01",
        "needs_source_hint": "D022 (AB 325 bill text)", "supplied": True,
    },
    "HOB-ALG-01": {
        "description": "Hoboken, NJ local ordinance banning algorithmic / software rent-setting (RealPage-style).",
        "needs_source_hint": "D032, D033, D034 (Hoboken code pages, link-only)", "supplied": False,
    },
    "JC-ALG-01": {
        "description": "Jersey City, NJ local ordinance banning algorithmic / software rent-setting (RealPage-style).",
        "needs_source_hint": "D035 or D037 (link-only articles)", "supplied": False,
    },
    "NJ-ALG-01": {
        "description": "New Jersey FAIR Act (Forbidding the Algorithmic Inflation of Rent Act), P.L. 2026 c.43, "
                       "enacted 2026-07-20, effective 2027-07-01.",
        "effective_date": "2027-07-01",
        "needs_source_hint": "D069", "supplied": True,
    },
    "MA-ALG-P1": {
        "description": "Massachusetts Senate bill S.2983 'An Act prohibiting algorithmic rent setting' (pending bill).",
        "needs_source_hint": "D046 / D047", "supplied": True,
    },
    "MA-ALG-P2": {
        "description": "Massachusetts House bill H.5222 about algorithmic rent setting (pending bill).",
        "needs_source_hint": "D045", "supplied": True,
    },
    "MA-RENT-P1": {
        "description": "Massachusetts statewide rent-control ballot question (Initiative Petition 25-21), "
                       "struck by the Supreme Judicial Court on 2026-06-23 -> status 'failed'.",
        "needs_source_hint": "D059 (WBUR article, link-only)", "supplied": False,
    },
}
