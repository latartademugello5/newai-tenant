# extra_text/ - add text for the link-only sources here

Some laws the tests need (Hoboken ban, Jersey City ban, the Massachusetts ballot question) are listed in
`starter_pack/corpus/links_only.csv` but NO text was supplied. To let the pipeline read them:

1. Open the URL in your browser (respect the site's terms; read the page normally - no bulk scraping).
2. Select the relevant article/ordinance text and copy it.
3. Make a file named after the doc id, e.g. `D059.txt`, with this header and the pasted text:

```
SOURCE: <the exact URL from links_only.csv>
RETRIEVED: 2026-10-03 14:00 UTC

<paste the text here, unchanged>
```

Do NOT edit, summarise or fix the pasted text - the pipeline checks that quotes match it exactly.
Then re-run `python 01_extract_rules.py` (only new files are processed) and `python 02_link_rules.py`.
See GUIDE.md step 6 for which ids to add.
