"""TEST-ONLY: writes hand-made rule records so the engine can be tested without calling an LLM.
These are NOT the submission rules - the real rules.json must come from 01_extract_rules.py."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from nav import common as C
from nav.textcheck import Haystack

def quote(doc, needle, n=160):
    raw = C.read_doc(doc)["raw"]
    i = raw.lower().find(needle.lower())
    assert i >= 0, (doc, needle)
    return raw[i:i+n]

def R(i, jur, cat, status, title, req, cov, cite, doc, q, eff=None, ex=None, **kw):
    base = dict(team_rule_id=f"r-{i:04d}", jurisdiction=jur, level="city" if "," in jur else "state", category=cat,
        status=status, title=title, requirement=req, key_value=None, coverage_conditions=None, exemptions=None,
        overrides=[], interaction=None, effective_date=eff, citation=cite, source_doc_id=doc,
        source_url=C.read_doc(doc)["url"] if doc else "https://example.org", quoted_span=q, confidence=0.9,
        conflict_flag=False, conflict_note=None, retrieved_at="2026-10-01T22:37Z", coverage=cov,
        exemption_tests=ex or [], imposes_rent_cap=False, penalty=None, ambiguity_note=None, test_alias=[],
        supersedes=[], conflicts_with=[], conflict_kind=None, corroborating_doc_ids=[], quote_match="exact", source_type="official")
    base.update(kw); return base

DUMMY = "TEST ONLY placeholder quotation text for a source that is not in the supplied corpus."
rules = [
 R(1,"CA","rent_increase_limits","in_force","Tenant Protection Act rent cap","Rent increases limited to 5% + CPI or 10%, whichever is lower.",
   {"universal":False,"min_building_age_years":15},"Cal. Civ. Code § 1947.12","D024",quote("D024","shall not, over the course of any 12-month period"),eff="2020-01-01",imposes_rent_cap=True),
 R(2,"CA","security_deposits","in_force","Security deposit cap","Deposit may not exceed one month's rent.",{"universal":True},"Cal. Civ. Code § 1950.5","D025",
   quote("D025","a landlord shall not demand or receive security"),eff="2024-07-01",
   ex=[{"description":"Natural-person owner of no more than two properties with four units total","kind":"unavailable_fact","constraints":{"max_units":4}}]),
 R(3,"CA","just_cause_eviction","in_force","Just cause eviction","Tenants of 12+ months need just cause.",{"universal":False,"min_building_age_years":15},"Cal. Civ. Code § 1946.2","D023",
   quote("D023","1946.2",120) if False else C.read_doc("D023")["raw"][200:330],eff="2020-01-01"),
 R(4,"CA","algorithmic_rent_setting","in_force","AB 325 common pricing algorithms","Using or distributing a common pricing algorithm to coordinate prices is unlawful.",{"universal":True},"Cal. Bus. & Prof. Code § 16729","D022",
   C.read_doc("D022")["raw"][300:420],eff="2026-01-01",test_alias=["CA-ALG-01"]),
 R(5,"San Francisco, CA","rent_increase_limits","in_force","SF Rent Ordinance","Annual allowable increase set by the Rent Board.",
   {"universal":False,"built_on_or_before":"1979-06-13","cutoff_is_certificate_of_occupancy":True},"S.F. Admin. Code ch. 37","D080",C.read_doc("D080")["raw"][200:320],
   supersedes=["r-0001"],interaction="Local rent control governs; the state cap does not apply to covered units.",imposes_rent_cap=True),
 R(6,"Los Angeles, CA","rent_increase_limits","in_force","LA Rent Stabilization Ordinance","Annual increase limit under the RSO.",
   {"universal":False,"min_units":2,"built_on_or_before":"1978-10-01","cutoff_is_certificate_of_occupancy":True},"L.A.M.C. § 151.00","D041",quote("D041","first built on or before October 1, 1978"),eff="2026-02-02",
   supersedes=["r-0001"],interaction="RSO governs over the state cap.",imposes_rent_cap=True,conflict_flag=True,conflict_kind="ambiguity",
   conflict_note="Two published effective dates: 2026-02-02 (LAHD) vs 2026-01-24 (landlord association).",ambiguity_note="two dates"),
 R(7,"Hoboken, NJ","algorithmic_rent_setting","in_force","Hoboken algorithmic rent ban","Landlords may not use algorithmic rent-setting software.",{"universal":True},"Hoboken Code (TEST)",None,DUMMY,eff="2025-12-01",
   test_alias=["HOB-ALG-01"],conflict_flag=True,conflict_kind="preemption",conflicts_with=["r-0009"],conflict_note="NJ FAIR Act may preempt."),
 R(8,"Jersey City, NJ","algorithmic_rent_setting","in_force","Jersey City algorithmic rent ban","Landlords may not use algorithmic rent-setting software.",{"universal":True},"Jersey City Ord. (TEST)",None,DUMMY,eff="2025-10-01",
   test_alias=["JC-ALG-01"],conflict_flag=True,conflict_kind="preemption",conflicts_with=["r-0009"],conflict_note="NJ FAIR Act may preempt."),
 R(9,"NJ","algorithmic_rent_setting","not_yet_effective","NJ FAIR Act","Bans algorithmic inflation of rent.",{"universal":True},"P.L. 2026, c.43","D069",quote("D069","shall be known and may be cited as the"),eff="2027-07-01",
   test_alias=["NJ-ALG-01"],conflict_flag=True,conflict_kind="preemption",conflicts_with=["r-0007","r-0008"],conflict_note="May preempt local bans."),
 R(10,"NJ","security_deposits","in_force","Rent Security Deposit Act","Deposit capped at 1.5 months' rent.",{"universal":True},"N.J.S.A. 46:8-21.2",None,DUMMY,
   ex=[{"description":"Owner-occupied premises with two or fewer units","kind":"unavailable_fact","constraints":{"max_units":2}},
       {"description":"Seasonal rentals","kind":"not_applicable_to_multifamily"}]),
 R(11,"MA","algorithmic_rent_setting","pending","S.2983 bill","Would prohibit algorithmic rent setting.",{"universal":True},"Bill S.2983","D046",quote("D046","An Act prohibiting algorithmic rent setting"),test_alias=["MA-ALG-P1"]),
 R(12,"MA","algorithmic_rent_setting","pending","H.5222 bill","Would restrict algorithmic rent setting.",{"universal":True},"Bill H.5222","D045",C.read_doc("D045")["raw"][250:380],test_alias=["MA-ALG-P2"]),
 R(13,"MA","rent_increase_limits","failed","Rent control ballot question (IP 25-21)","Would have allowed local rent control; struck.",{"universal":True},"IP 25-21",None,DUMMY,test_alias=["MA-RENT-P1"],imposes_rent_cap=True),
 R(14,"MA","rent_increase_limits","in_force","Local rent control prohibited","State law bars cities from adopting rent control.",{"universal":True},"M.G.L. c.40P § 4","D048",C.read_doc("D048")["raw"][150:300]),
 R(15,"Berkeley, CA","algorithmic_rent_setting","in_force","Berkeley algorithmic ban","Prohibits algorithmic rent-setting devices.",{"universal":True},"BMC 13.63","D001",C.read_doc("D001")["raw"][400:520],eff="2026-03-01",
   conflict_flag=True,conflict_kind="ambiguity",conflict_note="Two published effective dates (March 2026 vs January 2026)."),
 R(16,"NJ","screening_restrictions","in_force","Fair Chance in Housing Act","Limits criminal-history screening.",{"universal":False,"min_units":3},"N.J.S.A. 46:8-52","D065",quote("D065","shall be known and may be cited as the"),eff="2021-08-01"),
]
for r in rules: 
    if r["source_doc_id"]: assert Haystack(C.read_doc(r["source_doc_id"])["raw"]).locate(r["quoted_span"],101)[0], r["team_rule_id"]
Path(ROOT/"tests/fixtures/rules_fixture.json").write_text(json.dumps({"rules":rules},indent=1))
print("fixture rules:",len(rules))
