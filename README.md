# Rental Housing Law Navigator

Turns state and city housing law (CA, NJ, MA; 10 cities) into **address-level, cited answers**: which rules apply today, how pending or new laws change the result, and where the system honestly says **unknown**.

> **Not legal advice.** Prototype built from public law text that has not been reviewed by counsel.

**New here? Open [GUIDE.md](GUIDE.md) and follow it step by step.**

```
corpus text ─▶ 01 Claude extracts rules ─▶ 02 link/merge/flag ─▶ outputs/rules.json
                       │ quote must exist in source (guard)
addresses.csv ─▶ 03 Census geocoder ─▶ legal city ─┐
                                                    ▼
          04 deterministic coverage engine (true / false / unknown) ─▶ outputs/lookups.json
          05 change tests T1-T5 (as-of date logic)               ─▶ outputs/changes.json
          06 validate · 07 export website · 09 method note
```

## Design in one paragraph
The AI **extracts** structured rules from law text (every record must carry a quoted span that is verified verbatim against the source). Plain code **decides** coverage using the building facts in the public parcel data, so answers are reproducible. Missing facts, cutoff-year ties and owner-dependent exemptions return `unknown`. Enacted, not-yet-effective, pending and failed laws are kept apart, conflicts are flagged for human review, and every run is appended to `outputs/audit_log.jsonl`.

## Layout
| Path | What |
|---|---|
| `01_extract_rules.py` … `09_method_note.py` | pipeline steps (run in order, or `python run_all.py`) |
| `nav/` | library: engine (`engine.py`), quote check (`textcheck.py`), geocoding, schemas |
| `starter_pack/` | organizers' corpus, addresses, schema, tests |
| `extra_text/` | text you add for link-only sources |
| `outputs/` | `rules.json`, `lookups.json`, `changes.json`, audit log, method note |
| `web/` | static demo site (deploy folder for Vercel) |
| `tests/` | offline tests (`python tests/test_engine.py`) |

## Quick start
```
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                                   # then paste your ANTHROPIC_API_KEY
python run_all.py
python -m http.server 8000 --directory web
```
