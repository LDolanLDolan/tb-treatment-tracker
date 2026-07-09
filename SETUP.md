# TB Treatment & Therapy Tracker — Setup

This tracks new tuberculosis treatment developments from two official,
free, no-key sources:
- **ClinicalTrials.gov** — new or updated TB trials
- **PubMed** — new TB treatment research papers

No billing, no scraping, no terms-of-service risk — both are official
government/institutional APIs built for exactly this kind of use.

## 1. Create a new GitHub repo

```zsh
mkdir tb-treatment-tracker
cd tb-treatment-tracker
git init
```

## 2. Add these files

Copy in:
- `tb_tracker.py`
- `tb_dashboard.py`
- `requirements.txt`
- `.github/workflows/track-tb-updates.yml`
- `data/trials.json`, `data/papers.json`, `data/status.json` (empty starting files)

## 3. No secrets needed at all

Unlike the C venues project, there is genuinely nothing to configure here —
no API keys, no billing account, no GitHub Secrets. Both APIs are free
and keyless at this volume.

## 4. Push and create the GitHub repo

```zsh
git add .
git commit -m "Initial TB treatment tracker"
gh repo create tb-treatment-tracker --public --source=. --push
```

(If you'd rather keep it private: use `--private` instead of `--public`.)

## 5. Trigger a test run

```zsh
gh workflow run "Track TB Treatment Updates" --repo YOUR_USERNAME/tb-treatment-tracker
sleep 30
gh run list --repo YOUR_USERNAME/tb-treatment-tracker --limit 3
```

Once it shows a checkmark, check the log:
```zsh
gh run view <run-id> --log | grep -E "ERROR|Done\."
```

You should see something like "Done. X new trial(s), Y new paper(s)."
— the numbers will likely be modest on the first run, since this only
looks at the most recent 30 trials / 25 papers each time, not the full
historical archive.

## 6. Deploy the dashboard (optional)

Same as the C venues Streamlit app — deploy `tb_dashboard.py` to
Streamlit Community Cloud (free) pointing at this repo, or add it as a
page inside an existing Streamlit app.

## Adjusting scope later

- To track a different condition or drug class, change `CTGOV_CONDITION`
  in `tb_tracker.py`
- To widen or narrow the PubMed search, edit `PUBMED_QUERY`
- To check more/fewer results per run, adjust `CTGOV_PAGE_SIZE` and
  `PUBMED_RETMAX`
