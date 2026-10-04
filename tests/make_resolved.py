"""TEST-ONLY: pretend the Census geocoder succeeded (legal city = guessed city) so we can test offline."""
import csv, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from nav import geo
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
rows = list(csv.DictReader(open(ROOT/"starter_pack/data/sample_addresses.csv")))
res = []; la_seen = 0
for a in rows:
    h = geo.hint_city(a); legal = h
    if a["postal_city"] == "Los Angeles" and la_seen < 3:   # simulate the "mailing city != legal city" trap
        legal = "Glendale, CA"; la_seen += 1
    res.append({"address_id": a["address_id"], "postal_city": a["postal_city"], "hint_city": h, "legal_city": legal,
                "in_scope": legal in geo.IN_SCOPE.values(), "county": "TestCounty", "method": "census_geocoder",
                "confidence": "high", "note": None})
(out/"addresses_resolved.json").write_text(json.dumps(res))
print("resolved", len(res))
