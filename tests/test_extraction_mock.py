"""Runs 01_extract_rules.py and 02_link_rules.py against a local FAKE Anthropic server.
Tests the plumbing (API call shape, tool-use parsing, quote verification, caching, linking) - not legal quality."""
import json, os, re, subprocess, sys, threading, shutil, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

class H(BaseHTTPRequestHandler):
    calls = []
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        H.calls.append(body)
        tool = body["tool_choice"]["name"]; user = body["messages"][0]["content"]
        assert body["tools"][0]["name"] == tool and "api_key" not in body
        if tool == "record_rules":
            text = user.split("<<<BEGIN>>>")[1].split("<<<END>>>")[0]
            doc = re.search(r"doc_id: (\w+)", user)[1]
            lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 70]
            real = lines[0]
            jur = re.search(r"allowed jurisdiction values: \['([^']+)'", user)[1]
            mk = lambda span, title: {"jurisdiction": jur, "category": "security_deposits", "status": "in_force", "title": title,
                "requirement": "req", "coverage": {"universal": True}, "exemption_tests": [], "citation": "Cite 1",
                "quoted_span": span, "confidence": 0.9, "imposes_rent_cap": False}
            rules = [mk(real, "exact quote"),
                     mk(real.replace("'", "’").replace("  ", " ").upper(), "case/quote drift quote"),
                     mk("This sentence was fabricated by the fake model and is not in the document at all.", "fabricated")]
            inp = {"rules": rules}
        else:
            ids = re.findall(r"^(r-\d{4}) \|", user, re.M)
            inp = {"merges": [{"keep": ids[0], "drop": [ids[1]], "reason": "dup"}] if len(ids) > 1 else [],
                   "supersedes": [], "conflicts": [], "aliases": [{"alias": "CA-ALG-01", "rules": [ids[0]]}] if "STATE: CA" in user else []}
        out = {"id": "msg_1", "type": "message", "role": "assistant", "model": "mock-model", "stop_reason": "tool_use", "stop_sequence": None,
               "content": [{"type": "tool_use", "id": "toolu_1", "name": tool, "input": inp}], "usage": {"input_tokens": 5, "output_tokens": 5}}
        b = json.dumps(out).encode()
        self.send_response(200); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(b))); self.end_headers(); self.wfile.write(b)

class T(unittest.TestCase):
    def test_flow(self):
        srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
        env = dict(os.environ, ANTHROPIC_API_KEY="test-key", ANTHROPIC_BASE_URL=f"http://127.0.0.1:{srv.server_port}")
        out = ROOT/"tests/out_mock"; shutil.rmtree(out, ignore_errors=True)
        run = lambda *a: subprocess.run([sys.executable, *a, "--out-dir", str(out)], cwd=ROOT, env=env, capture_output=True, text=True)
        r = run("01_extract_rules.py", "--only", "D069", "D024", "D046"); print(r.stdout[-700:], r.stderr[-500:])
        self.assertEqual(r.returncode, 0)
        raw = json.loads((out/"rules_raw.json").read_text())["rules"]
        self.assertEqual(len(raw), 6)                       # 2 kept per doc, fabricated one rejected
        self.assertEqual(len((out/"rejected_rules.jsonl").read_text().splitlines()), 3)
        self.assertTrue(all(len(x["quoted_span"]) >= 20 and x["source_doc_id"] and x["retrieved_at"] for x in raw))
        n = len(H.calls)
        r = run("01_extract_rules.py", "--only", "D069", "D024", "D046")           # second run must hit the cache
        self.assertEqual(len(H.calls), n, "cache should prevent new API calls")
        r = run("02_link_rules.py"); print(r.stdout[-900:], r.stderr[-500:])
        self.assertEqual(r.returncode, 0)
        rules = json.loads((out/"rules.json").read_text())["rules"]
        self.assertLess(len(rules), 6)                      # a merge happened in at least one state
        self.assertTrue(any("CA-ALG-01" in x["test_alias"] for x in rules))
        self.assertEqual([x["team_rule_id"] for x in rules], [f"r-{i:04d}" for i in range(1, len(rules)+1)])
        srv.shutdown()

if __name__ == "__main__":
    unittest.main()
