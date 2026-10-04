"""Shared helpers: paths, .env loading, dates, corpus reading, audit log."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STARTER = ROOT / "starter_pack"
CORPUS_DIR = STARTER / "corpus"
CORPUS_TEXT = CORPUS_DIR / "text"
EXTRA_TEXT = ROOT / "extra_text"
DEFAULT_AS_OF = "2026-10-01"
PROMPT_VERSION = "v1"

_out_dir = ROOT / "outputs"


def set_out_dir(path) -> Path:
    global _out_dir
    _out_dir = Path(path).resolve()
    _out_dir.mkdir(parents=True, exist_ok=True)
    return _out_dir


def out_dir() -> Path:
    _out_dir.mkdir(parents=True, exist_ok=True)
    return _out_dir


def load_env() -> None:
    """Tiny .env loader (KEY=value per line). Existing env vars win."""
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path, obj) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def audit(step: str, **fields) -> None:
    """Append one line to outputs/audit_log.jsonl so another person can reproduce the run."""
    rec = {"ts": now_utc(), "step": step, **fields}
    with open(out_dir() / "audit_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- dates
_DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$")


def parse_partial_date(s) -> dt.date | None:
    """'2026', '2026-07', '2026-07-20' -> date (missing parts default to 1)."""
    if not s:
        return None
    m = _DATE_RE.match(str(s).strip())
    if not m:
        return None
    return dt.date(int(m[1]), int(m[2] or 1), int(m[3] or 1))


def parse_date(s) -> dt.date:
    d = parse_partial_date(s)
    if d is None:
        raise ValueError(f"Bad date '{s}'. Use YYYY-MM-DD.")
    return d


def years_before(d: dt.date, n: int) -> dt.date:
    try:
        return d.replace(year=d.year - n)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - n, day=28)


# ---------------------------------------------------------------- corpus
def load_manifest() -> dict[str, dict]:
    with open(CORPUS_DIR / "corpus_manifest.csv", newline="", encoding="utf-8") as f:
        return {r["doc_id"]: r for r in csv.DictReader(f)}


def doc_text_path(doc_id: str) -> Path | None:
    """Supplied text first, then anything you added in extra_text/."""
    for p in (CORPUS_TEXT / f"{doc_id}.txt", EXTRA_TEXT / f"{doc_id}.txt"):
        if p.exists():
            return p
    return None


def read_doc(doc_id: str) -> dict:
    """Return {doc_id, url, retrieved, body, raw, path, is_extra}.

    Every text file starts with 'SOURCE: <url>' and 'RETRIEVED: <date>' lines.
    """
    p = doc_text_path(doc_id)
    if p is None:
        raise FileNotFoundError(doc_id)
    raw = p.read_text(encoding="utf-8", errors="replace")
    url = retrieved = ""
    m = re.search(r"^SOURCE:\s*(.+)$", raw, re.M)
    if m:
        url = m.group(1).strip()
    m = re.search(r"^RETRIEVED:\s*(.+)$", raw, re.M)
    if m:
        retrieved = m.group(1).strip()
    return {
        "doc_id": doc_id,
        "url": url,
        "retrieved": retrieved,
        "raw": raw,
        "body": raw,
        "path": str(p),
        "is_extra": p.parent == EXTRA_TEXT,
    }


def iter_doc_ids(only: list[str] | None = None) -> list[str]:
    manifest = load_manifest()
    ids = []
    for doc_id in sorted(manifest):
        if only and doc_id not in only:
            continue
        if doc_text_path(doc_id):
            ids.append(doc_id)
    return ids


def doc_jurisdictions(row: dict) -> list[str]:
    return [j.strip() for j in re.split(r";|\|", row["jurisdictions"]) if j.strip()]


def iso_retrieved(s: str) -> str:
    """'2026-10-01 22:37 UTC' -> '2026-10-01T22:37Z' (best effort)."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})", s or "")
    return f"{m[1]}T{m[2]}Z" if m else (s or "")


def level_of(jurisdiction: str) -> str:
    return "city" if "," in jurisdiction else "state"


def state_of(jurisdiction: str) -> str:
    return jurisdiction.split(",")[-1].strip() if "," in jurisdiction else jurisdiction
