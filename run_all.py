#!/usr/bin/env python3
"""Run the whole pipeline in order, stopping at the first problem.
  python run_all.py              -> steps 01..07
  python run_all.py --from 4     -> start at step 04 (e.g. after you changed something upstream)
"""
import argparse, subprocess, sys
STEPS = ["01_extract_rules.py", "02_link_rules.py", "03_geocode_addresses.py", "04_build_lookups.py",
         "05_build_changes.py", "06_validate.py", "07_export_web.py", "09_method_note.py"]
ap = argparse.ArgumentParser(); ap.add_argument("--from", dest="start", type=int, default=1); a = ap.parse_args()
for s in STEPS:
    if int(s[:2]) < a.start: continue
    print(f"\n===== {s} =====", flush=True)
    if subprocess.run([sys.executable, s]).returncode != 0:
        sys.exit(f"\nStopped: {s} reported a problem (see above). Fix it, then: python run_all.py --from {int(s[:2])}")
print("\nAll steps finished.")
