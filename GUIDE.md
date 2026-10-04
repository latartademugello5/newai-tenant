# GUIDE: Rental Housing Law Navigator, start to finish

Follow the steps in order. Every command is copy-paste. If something prints an error, jump to **Troubleshooting** at the bottom.

**What you are building:** a system that (1) reads the 87-document law corpus with Claude and turns it into structured rules, (2) finds the legal city of ~500 addresses, (3) decides which rules apply to each address, (4) reports what five "change tests" affect, and (5) shows it all in a website.

**What you must hand in** (from the challenge PDF and your Hack Nation checklist):

| # | Item | Where it comes from |
|---|------|---------------------|
| 1 | `rules.json` | Step 8 output |
| 2 | `lookups.json` | Step 11 output |
| 3 | `changes.json` | Step 12 output |
| 4 | One-page method note | Step 16 (`outputs/METHOD_NOTE.md`) |
| 5 | Live demo link (Vercel) | Step 15 |
| 6 | Public GitHub repo link | Step 14 |
| 7 | Demo video | Step 17 |
| 8 | Tech video | Step 17 |
| 9 | Team video | Step 17 |

Upload everything to **app.hack-nation.ai AND the Google form** (your slide says both).

> **Check with the organizers today:** the submission deadline, whether API credits are provided, and whether you may read the "link-only" sources (Step 6). The challenge PDF says these are still "TBD by organizers."

---

## What was tested and what was not (be honest in your video)

Tested here, offline: the matching engine, the as-of-date logic, all five change tests (on hand-made test rules), the validator, the website (desktop and phone), and the extraction/linking scripts against a **fake** AI server.
**Not** tested here because this workspace has no API key and cannot reach the Census website: the real Claude extraction quality and the real Census geocoding. Steps 5 and 9 have "smoke tests" so you find out in 1 minute, not 1 hour, if anything is off.

---

## Step 1. Install the tools (15 min)

1. **Python 3.10 or newer.** Download from https://www.python.org/downloads/ . On Windows, tick **"Add python.exe to PATH"** in the installer.
   Check it: open a terminal (Mac: *Terminal*; Windows: *PowerShell*) and run
   ```
   python --version
   ```
   (On Mac, if that fails, use `python3` everywhere in this guide instead of `python`.)
2. **Git.** https://git-scm.com/downloads (Windows: accept the defaults). Check: `git --version`
3. **A GitHub account** (https://github.com) and a **Vercel account** (https://vercel.com, choose "Continue with GitHub").
4. **A code editor** (optional but nice): VS Code, https://code.visualstudio.com

## Step 2. Set up the project (5 min)

1. Unzip `housing-navigator.zip` somewhere easy, e.g. your Desktop. You get a folder `housing-navigator`.
2. Open a terminal **inside** that folder.
   Mac: `cd ~/Desktop/housing-navigator`  ·  Windows: `cd $HOME\Desktop\housing-navigator`
3. Create an isolated Python environment and install the libraries:

   **Mac / Linux**
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   **Windows (PowerShell)**
   ```
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
   (If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope Process Bypass` first.)
   Your prompt should now start with `(.venv)`. **Every time you open a new terminal, re-run the activate line.**
4. Run the self-tests. This proves everything installed correctly:
   ```
   python tests/test_engine.py
   python tests/test_extraction_mock.py
   ```
   Both should end with `OK`.

## Step 3. Get your Anthropic API key (10 min)

1. Go to https://console.anthropic.com , sign in, open **API keys**, click **Create key**, copy it (it starts with `sk-ant-`). You only see it once.
2. Make sure the account has credit (Settings → Billing), or use credits the organizers give you. This project costs very roughly a few dollars with a mid-size model. Use `claude-haiku-4-5-20251001` first if you want it cheap.
3. In the project folder, copy `.env.example` to a new file named `.env`:
   - Mac: `cp .env.example .env`   ·   Windows: `copy .env.example .env`
4. Open `.env` in your editor and paste the key right after `ANTHROPIC_API_KEY=` (no quotes, no spaces). Save.
   **Never upload `.env` to GitHub** (`.gitignore` already blocks it).

## Step 4. Look at what you were given (5 min)

Open these so you understand the data (all inside `starter_pack/`):

- `corpus/corpus_manifest.csv`: the 87 documents. 54 have text in `corpus/text/`; 33 are link-only.
- `data/sample_addresses.csv`: the 500 addresses. Notice: **no jurisdiction column**; `postal_city` is only the mailing city.
- `schema/rule_record.schema.json`: the exact shape each rule must have.
- `dev/change_tests.json`: tests T1 to T5.

## Step 5. Smoke-test the AI extraction on ONE document (3 min, pennies)

```
python 01_extract_rules.py --only D069
```
D069 is New Jersey's FAIR Act. You should see something like `D069: 3 rules kept, 0 rejected`.
Open `outputs/rules_raw.json` and check one record by eye: is the `quoted_span` a real sentence from `starter_pack/corpus/text/D069.txt`? Is the `status` `not_yet_effective` and `effective_date` `2027-07-01`?

- If it says `ANTHROPIC_API_KEY is not set`: redo Step 3.4.
- If it says model not found / 404: open `.env` and set `ANTHROPIC_MODEL=` to a model your account can use.
- If many rules are "rejected": that is the safety guard working; a few is normal. Look at `outputs/rejected_rules.jsonl`.

## Step 6. Add the sources the tests need but the pack didn't include (20-30 min) **IMPORTANT**

I checked: the text for **Hoboken's ban, Jersey City's ban and the Massachusetts ballot question is not in `corpus/text/`**. Tests T2 and T5 depend on them. They are listed in `links_only.csv`, so you add them by hand:

| Doc id | Why | URL (from `links_only.csv`) |
|---|---|---|
| D059 | T5: ballot question struck | https://www.wbur.org/news/2026/06/23/massachusetts-high-court-rent-control-ballot-question-struck |
| D035 | T2: Jersey City ban | https://hudsoncountyview.com/jersey-city-council-approves-realpage-ban-and-increasing-benefits-for-laborers/ |
| D032, D033, D034 | T2: Hoboken ban (code pages) | https://ecode360.com/15252438 · https://ecode360.com/15252470 · https://ecode360.com/46833413 |
| D037 | Jersey City + Berkeley + others (law-firm article), optional but useful | https://www.morganlewis.com/pubs/2026/08/algorithmic-rent-pricing-litigation-expands-under-new-state-and-local-laws |
| D060 | NJ FAIR Act summary, optional | https://daypitney.com/new-jersey-enacts-fair-act-to-prohibit-algorithmic-rent-setting-practices |

For each one:
1. Open the URL in your browser and read the page normally (no scraping tools; the challenge says to respect site terms). If a page is blocked or behind a paywall, skip it and ask a mentor.
2. Copy the article / ordinance text.
3. Create `extra_text/D059.txt` (use the doc id as the file name) with this at the top, then paste the text under it:
   ```
   SOURCE: https://www.wbur.org/news/2026/06/23/massachusetts-high-court-rent-control-ballot-question-struck
   RETRIEVED: 2026-10-03 14:00 UTC

   <paste the text here, unchanged>
   ```
   Use today's real date/time for `RETRIEVED`. **Do not edit the pasted text.**
4. The code reads these exactly like the supplied files. Say in your method note that these were added manually from public pages.

If you cannot get one of them, the pipeline will tell you at Step 8 which test is missing and T2/T5 will show FAIL. That is an honest result; mention it in your video.

## Step 7. Run the full extraction (10-30 min)

```
python 01_extract_rules.py
```
You'll see one line per document. It is safe to stop and re-run: finished chunks are cached in `outputs/extraction_cache/`, so you don't pay twice.
At the end you should have roughly 100-250 rules kept. Typical cause of a `FAILED` document line: a temporary API error, so just re-run the same command.

## Step 8. Link the rules (2 min)

```
python 02_link_rules.py
```
This merges duplicates, records "state rule yields to local rent control", flags conflicts, and matches the organizers' law names (CA-ALG-01 etc.). Read the **Alias check** at the bottom:

- `OK` for all seven aliases: great.
- `MISSING HOB-ALG-01` etc.: the printed hint tells you which document to add (Step 6) or re-extract. Fix, then re-run `python 01_extract_rules.py` and `python 02_link_rules.py`.

Output: `outputs/rules.json` (**submission file #1**).

## Step 9. Find each address's legal city (5-10 min)

First the 1-minute test:
```
python 03_geocode_addresses.py --self-test
```
You should see a `place` (a city name) for each of three addresses. If you see `NO MATCH` or a network error, check your internet and try again (the Census service is occasionally slow).
Then the real run:
```
python 03_geocode_addresses.py
```
It prints how many addresses have a mailing city that differs from the legal city. That number is the trap the challenge talks about, and a good thing to mention in your demo.
No internet? `python 03_geocode_addresses.py --offline` works but marks most addresses unresolved, so city rules become "unknown". Use it only for development.

## Step 10. Decide which rules apply to each address

```
python 04_build_lookups.py
```
This writes `outputs/lookups.json` (**submission file #2**) for as-of date 2026-10-01. Read the summary: you should see all five result types, and very few addresses with "NO rules at all".
Try another date to see the law change: `python 04_build_lookups.py --as-of 2027-07-02 --out-name lookups_2027.json` (this extra file is only for you).

## Step 11. Run the five change tests

```
python 05_build_changes.py
```
Goal: **T1 to T5 all say PASS.** This writes `outputs/changes.json` (**submission file #3**).

| If this fails | Usually means | What to do |
|---|---|---|
| T1 | AB 325 rule has wrong `effective_date` or wasn't tagged | Open `outputs/rules.json`, search `CA-ALG-01`; check the date. Re-run extraction for D022 with `--only D022 --force`. |
| T2 | Hoboken/Jersey City text missing | Step 6. |
| T3 | FAIR Act date wrong, or conflict flags missing | Check `NJ-ALG-01` rule: `effective_date` should be `2027-07-01`. |
| T4 | Bills not tagged pending | Check D045/D046 rules have status `pending`. |
| T5 | Ballot rule missing or not `failed` | Step 6 (D059). |

**Rule of the event: do not hand-edit `rules.json` to make a test pass.** Instead improve the prompt in `01_extract_rules.py` (the `SYSTEM` text) and re-run with `--force`. Extraction must be automated.

## Step 12. Quality check by hand (30 min; this is where you win)

1. **Quotes are real:** `python 06_validate.py` checks that every `quoted_span` exists in its source. Fix any ERROR lines.
2. **Spot-check 10 rules:** open `rules.json`, pick 10 at random, and compare each to the source text. Note any mistakes for your "limitations" slide.
3. **Open questions (bonus points).** Search `rules.json` for these and confirm they carry `conflict_flag: true`:
   - Berkeley's algorithmic ban: two effective dates (March 1, 2026 vs "January 2026").
   - LA's RSO formula: 2026-02-02 vs 2026-01-24.
   - California's screening-fee cap: no single official 2026 dollar figure.
   - NJ FAIR Act vs Jersey City / Hoboken (preemption).
   If one is missing, the second source (a law-firm page) probably isn't in `extra_text/` yet (D002, D037 are the Berkeley ones).
4. **Unknown is honest:** open the website (Step 14) and look at a San Francisco building built in 1979 and one with a missing year. They should say **Unknown**.

## Step 13. Validate the three submission files

```
python 06_validate.py
```
It must end with `VALID - ready to submit`. It checks the official schema, that all 500 addresses are present, that every result value is legal, and that T1 to T5 exist.

## Step 14. Build and preview the website (10 min)

```
python 07_export_web.py
python -m http.server 8000 --directory web
```
Open http://localhost:8000 . Try: the example buttons, the date chips ("Before AB 325" / "After AB 325" / "FAIR Act in effect"), clicking the 3D layer slabs, the **Audit** panel on a rule, the **Change tests** tab, and the **ES** button. Press `Ctrl+C` in the terminal to stop.
Optional Spanish rule titles: `python 08_translate_es.py` then `python 07_export_web.py` again.

## Step 15. Put the code on GitHub and the site on Vercel (20 min)

1. On github.com click **New repository**, name it `rental-housing-navigator`, set it **Public**, don't add a README (you have one). Create it.
2. In your terminal, in the project folder:
   ```
   git init
   git add .
   git commit -m "Rental Housing Law Navigator"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/rental-housing-navigator.git
   git push -u origin main
   ```
   Check `.env` did **not** upload (it shouldn't appear on GitHub).
3. On vercel.com: **Add New → Project → Import** your repo.
   - **Framework Preset:** Other
   - **Root Directory:** click Edit and choose `web`
   - Leave Build Command and Output Directory empty. Click **Deploy**.
4. Open the URL Vercel gives you. It must show the website with data. That URL is your **live demo link**.
   (After any change: re-run `python 07_export_web.py`, `git add . && git commit -m update && git push`; Vercel redeploys by itself.)

## Step 16. The one-page method note

```
python 09_method_note.py
```
Open `outputs/METHOD_NOTE.md`, fill in the `Team:` line and edit the limitations to match what you actually found in Step 12. Paste it into a Google Doc or export to PDF; keep it to one page.

## Step 17. Record the three videos (about 1 hour total)

Use any screen recorder (Mac: QuickTime or Cmd+Shift+5; Windows: Win+G or Loom). Keep each short (check the required length with the organizers; 2 to 3 minutes is a safe target).

**Demo video** (shows the project)
1. 0:00 Problem: "Rental law is layered: state, county, city, and the right answer depends on the exact address and date."
2. Pick a Hoboken address → show rules, the **3D layer stack**, an **Audit** panel (quote, source link, retrieval date).
3. Click **Before AB 325 / After AB 325**: California rule flips from *Not yet effective* to *Applies*.
4. Show a San Francisco 1979 building → **Unknown**, and say why (cutoff year; we refuse to guess).
5. **Change tests** tab: T1 to T5 all PASS; mention T5 is empty on purpose.
6. Say clearly: "Not legal advice."

**Tech video** (explains the build)
1. Show the pipeline diagram (README) and run `python 01_extract_rules.py --only D069` live.
2. Explain the **quote guard**: a rule is dropped if its quoted text isn't in the source.
3. Explain **AI extracts, code decides**: the coverage engine is deterministic with true / false / unknown.
4. Explain Census geocoding vs mailing city (show the count from Step 9).
5. Show the audit log and `python 06_validate.py`.
6. Name the tradeoffs: unknown over guessing; manual add of link-only sources; no owner-type data.

**Team video:** each person says name, role, one line on why housing law matters to them.

## Step 18. Submit

1. Create your account / sign in at **app.hack-nation.ai** and pick **Challenge 2: Rental Housing Law Navigator**.
2. Upload / paste, matching your checklist slide: Demo video · Tech video · Team video · GitHub repo link · Live demo link (Vercel).
3. Attach `rules.json`, `lookups.json`, `changes.json` and the method note where the form asks (the challenge organizers will confirm the exact method).
4. Fill in the **Google form** with the same links.

**Final checklist**
- [ ] `python 06_validate.py` says VALID
- [ ] T1 to T5 all PASS (or you can explain any FAIL)
- [ ] Repo is public, `.env` not in it
- [ ] Vercel link opens and shows data
- [ ] Every screen says "not legal advice"
- [ ] 3 videos uploaded
- [ ] Submitted on app.hack-nation.ai AND the Google form

---

## Suggested schedule (adjust to your real deadline)

| Block | Steps |
|---|---|
| First hour | 1 to 5 |
| Hours 1-3 | 6, 7, 8 |
| Hours 3-5 | 9 to 12 (fix prompts, re-run) |
| Hours 5-7 | 13 to 15 |
| Last hours | 16 to 18 |

## Troubleshooting

| Problem | Fix |
|---|---|
| `python: command not found` | Use `python3`; on Windows reinstall Python with "Add to PATH". |
| `ModuleNotFoundError` | The virtual environment isn't active. Re-run the activate line from Step 2. |
| `ANTHROPIC_API_KEY is not set` | Step 3.4. The file must be named `.env` (not `.env.txt`). |
| API 429 / overloaded | Wait a minute and re-run the same command; it resumes from cache. Lower load with `--workers 2`. |
| Extraction is slow or costly | Set `ANTHROPIC_MODEL=claude-haiku-4-5-20251001` in `.env` for a trial; use the stronger model for the final run (then `--force`). |
| Geocoder errors | Retry later; results are cached so it only fetches what's missing. |
| Website says "Could not load data" | You must run `python 07_export_web.py` first, and open it via `http://localhost:8000`, not by double-clicking `index.html`. |
| Vercel shows 404 | Root Directory must be `web`, and `web/data/app_data.json` must be committed (run Step 14 before `git add`). |
| A test says FAIL | See the table in Step 11. |

## Ideas if you have spare time (after everything above is done)

1. Run `python 08_translate_es.py` for the Spanish rule text.
2. Add a new jurisdiction (stretch goal): put its law text in `extra_text/`, add it to `starter_pack/corpus/corpus_manifest.csv`, and add its addresses; the same pipeline handles it.
3. Upgrade the 3D slabs in `web/app.js` into a Three.js building with the layers floating above it.
