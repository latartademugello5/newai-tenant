import datetime as dt, json, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from nav.engine import build_facts, lookup_address, evaluate_rule, unit_range_hint, temporal_status
from nav.textcheck import Haystack

RULES = json.loads((ROOT/"tests/fixtures/rules_fixture.json").read_text())["rules"]
D = dt.date.fromisoformat

def facts(state="CA", city="San Francisco, CA", year="", units="", desc="", method="census_geocoder"):
    a = {"address_id":"T","street_address":"1 Test St","postal_city":"X","state":state,"year_built":year,"units":units,"use_description":desc,"use_code":""}
    r = {"legal_city":city,"hint_city":city,"method":method,"confidence":"high" if method=="census_geocoder" else "none"}
    return build_facts(a, r)

def res(f, when="2026-10-01"):
    return {e["team_rule_id"]: e for e in lookup_address(RULES, f, D(when))}

class T(unittest.TestCase):
    def test_sf_precedence(self):
        r = res(facts(year="1971", units="6"))
        self.assertEqual(r["r-0005"]["result"], "applies")
        self.assertEqual(r["r-0001"]["result"], "superseded")
    def test_sf_new_building_state_cap_applies(self):
        r = res(facts(year="2005", units="6"))
        self.assertNotIn("r-0005", r)               # local rent control does not cover it
        self.assertEqual(r["r-0001"]["result"], "applies")
    def test_cutoff_year_is_unknown(self):
        r = res(facts(year="1979", units="6"))
        self.assertEqual(r["r-0005"]["result"], "unknown")
        self.assertEqual(r["r-0001"]["result"], "unknown")   # state cap depends on the local rule
    def test_missing_year_is_unknown_not_guess(self):
        r = res(facts(year="", units="6"))
        self.assertEqual(r["r-0005"]["result"], "unknown")
    def test_la_cutoff_1978(self):
        self.assertEqual(res(facts(city="Los Angeles, CA", year="1978", units="10"))["r-0006"]["result"], "unknown")
        self.assertEqual(res(facts(city="Los Angeles, CA", year="1960", units="10"))["r-0006"]["result"], "applies")
        self.assertNotIn("r-0006", res(facts(city="Los Angeles, CA", year="1990", units="10")))
    def test_mailing_city_not_legal_city(self):
        r = res(facts(city="Glendale, CA", year="1960", units="10"))
        self.assertNotIn("r-0006", r)                         # no LA rules for a Glendale address
        self.assertEqual(r["r-0001"]["result"], "applies")
    def test_exemption_ruled_out_by_units(self):
        self.assertEqual(res(facts("NJ","Newark, NJ",units="9"))["r-0010"]["result"], "applies")
        self.assertEqual(res(facts("NJ","Newark, NJ",units=""))["r-0010"]["result"], "unknown")
        self.assertEqual(res(facts("NJ","Newark, NJ",units="2"))["r-0010"]["result"], "unknown")
    def test_unit_hint_from_description(self):
        self.assertEqual(unit_range_hint("Apartment 5 to 14 Units"), (5, 14))
        self.assertEqual(unit_range_hint("4-8-UNIT-APT"), (4, 8))
        self.assertEqual(unit_range_hint(">8-UNIT-APT"), (9, None))
        self.assertEqual(unit_range_hint("Alameda County use code (5+ units)"), (5, None))
        self.assertEqual(unit_range_hint("3SB"), (None, None))
        r = res(facts("NJ","Newark, NJ",desc="Apartment 5 to 14 Units"))  # 5+ units -> min_units 3 is met
        self.assertEqual(r["r-0016"]["result"], "applies")
    def test_temporal_t1(self):
        self.assertEqual(res(facts(year="1900",units="9"),"2025-12-31")["r-0004"]["result"], "not_yet_effective")
        self.assertEqual(res(facts(year="1900",units="9"),"2026-01-02")["r-0004"]["result"], "applies")
    def test_t3_and_conflicts(self):
        f = facts("NJ","Hoboken, NJ")
        r = res(f)
        self.assertEqual(r["r-0009"]["result"], "not_yet_effective"); self.assertTrue(r["r-0009"]["conflict_flag"])
        self.assertEqual(r["r-0007"]["result"], "applies"); self.assertNotIn("r-0008", r)
        r2 = res(facts("NJ","Newark, NJ"))
        self.assertFalse(r2["r-0009"]["conflict_flag"]); self.assertNotIn("r-0007", r2)
        self.assertEqual(res(f,"2027-07-02")["r-0009"]["result"], "applies")

    def test_unverified_city_does_not_confirm_preemption_conflict(self):
        f = facts("NJ", "Hoboken, NJ", method="unresolved")
        f["legal_city"] = None
        r = res(f)
        self.assertEqual(r["r-0007"]["result"], "unknown")
        self.assertFalse(r["r-0007"]["conflict_flag"])
        self.assertFalse(r["r-0009"]["conflict_flag"])

    def test_ma(self):
        r = res(facts("MA","Boston, MA"))
        self.assertEqual(r["r-0011"]["result"], "pending"); self.assertEqual(r["r-0012"]["result"], "pending")
        self.assertNotIn("r-0013", r)                         # failed ballot question is never reported as a rule
    def test_unverified_city_is_unknown(self):
        f = facts("CA","San Francisco, CA",year="1950",units="9",method="unresolved"); f["legal_city"]=None
        self.assertEqual(res(f)["r-0005"]["result"], "unknown")
    def test_conflict_date_discrepancy_flagged(self):
        self.assertTrue(res(facts("CA","Los Angeles, CA",year="1950",units="9"))["r-0006"]["conflict_flag"])
    def test_quote_matching(self):
        h = Haystack("The  owner shall\nnot increase’s the rent  more than 5 percent.")
        self.assertEqual(h.locate("OWNER shall not increase's the rent more")[1], "exact")
        self.assertIsNone(h.locate("this sentence was invented by a model")[0])
        self.assertEqual(h.locate("The owner shall not increase's the rent more than 5 percent.")[0].count("\n"), 1)

if __name__ == "__main__":
    unittest.main(verbosity=1)
