"""
TB Treatment & Therapy Tracker — GitHub Actions Edition
---------------------------------------------------------
Runs entirely on GitHub's free servers via GitHub Actions. Tracks two
official, free, no-key-required sources for new tuberculosis treatment
and therapy developments:

  1. ClinicalTrials.gov API v2 — new or recently-updated TB drug/therapy
     trials (official US government registry, no key needed)
  2. PubMed E-utilities — newly published TB treatment research papers
     (official NCBI/NIH API, no key needed at this volume)

Neither source involves scraping, billing, or terms-of-service risk —
both are official APIs explicitly built for exactly this kind of
programmatic access.

What it does each time it runs:
  1. Queries ClinicalTrials.gov for TB trials, sorted newest-updated-first
  2. Queries PubMed for TB treatment papers, sorted newest-first
  3. Adds any newly-seen trials/papers to data/trials.json and data/papers.json
  4. Updates data/status.json with a timestamp and summary

GitHub Actions runs this automatically once a day. You never need to run
this yourself, but you can with: python tb_tracker.py
"""

import json
import time
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── Paths ────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
TRIALS_PATH = DATA_DIR / "trials.json"
PAPERS_PATH = DATA_DIR / "papers.json"
STATUS_PATH = DATA_DIR / "status.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── ClinicalTrials.gov config ────────────────────────────────────────────
CTGOV_URL = "https://clinicaltrials.gov/api/v2/studies"
CTGOV_CONDITION = "tuberculosis"
CTGOV_PAGE_SIZE = 30  # newest 30 updated trials each run — plenty for a daily check

# ── PubMed E-utilities config ────────────────────────────────────────────
PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
# Searches title/abstract for TB combined with treatment-related terms
PUBMED_QUERY = "(tuberculosis[Title/Abstract]) AND (treatment[Title/Abstract] OR therapy[Title/Abstract] OR therapeutic[Title/Abstract])"
PUBMED_RETMAX = 25  # newest 25 matching papers each run


# ── Helpers ──────────────────────────────────────────────────────────────
def load_json(path: Path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def uid_hash(uid: str) -> str:
    return hashlib.md5(uid.encode()).hexdigest()


# ── ClinicalTrials.gov ────────────────────────────────────────────────────
def fetch_new_trials(seen_ids: set) -> tuple[list[dict], bool]:
    params = {
        "query.cond": CTGOV_CONDITION,
        "sort": "LastUpdatePostDate:desc",
        "pageSize": CTGOV_PAGE_SIZE,
        "format": "json",
    }
    try:
        resp = requests.get(CTGOV_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        log.error(f"ClinicalTrials.gov request failed: {e}")
        return [], False

    new_trials = []
    for study in data.get("studies", []):
        try:
            proto = study["protocolSection"]
            nct_id = proto["identificationModule"]["nctId"]
        except KeyError:
            continue

        if uid_hash(nct_id) in seen_ids:
            continue

        ident = proto.get("identificationModule", {})
        status_mod = proto.get("statusModule", {})
        design_mod = proto.get("designModule", {})
        sponsor_mod = proto.get("sponsorCollaboratorsModule", {})

        new_trials.append({
            "date_found": datetime.now(timezone.utc).isoformat(),
            "nct_id": nct_id,
            "title": ident.get("briefTitle", ""),
            "status": status_mod.get("overallStatus", ""),
            "phase": ", ".join(design_mod.get("phases", [])) or "N/A",
            "sponsor": sponsor_mod.get("leadSponsor", {}).get("name", ""),
            "last_update_posted": status_mod.get("lastUpdatePostDateStruct", {}).get("date", ""),
            "url": f"https://clinicaltrials.gov/study/{nct_id}",
        })

    return new_trials, True


# ── PubMed ────────────────────────────────────────────────────────────────
def fetch_new_papers(seen_ids: set) -> tuple[list[dict], bool]:
    # Step 1: ESearch — get the list of newest matching PMIDs
    search_params = {
        "db": "pubmed",
        "term": PUBMED_QUERY,
        "retmax": PUBMED_RETMAX,
        "sort": "most+recent",
        "retmode": "json",
    }
    try:
        resp = requests.get(PUBMED_ESEARCH_URL, params=search_params, timeout=20)
        resp.raise_for_status()
        pmids = resp.json().get("esearchresult", {}).get("idlist", [])
    except requests.RequestException as e:
        log.error(f"PubMed ESearch failed: {e}")
        return [], False

    if not pmids:
        return [], True

    new_pmids = [p for p in pmids if uid_hash(p) not in seen_ids]
    if not new_pmids:
        return [], True

    time.sleep(0.4)  # stay well under the 3 requests/second limit

    # Step 2: ESummary — get title/journal/date for the new PMIDs only
    summary_params = {
        "db": "pubmed",
        "id": ",".join(new_pmids),
        "retmode": "json",
    }
    try:
        resp = requests.get(PUBMED_ESUMMARY_URL, params=summary_params, timeout=20)
        resp.raise_for_status()
        summaries = resp.json().get("result", {})
    except requests.RequestException as e:
        log.error(f"PubMed ESummary failed: {e}")
        return [], False

    new_papers = []
    for pmid in new_pmids:
        doc = summaries.get(pmid)
        if not doc:
            continue
        new_papers.append({
            "date_found": datetime.now(timezone.utc).isoformat(),
            "pmid": pmid,
            "title": doc.get("title", ""),
            "journal": doc.get("fulljournalname", doc.get("source", "")),
            "pub_date": doc.get("pubdate", ""),
            "authors": ", ".join(a.get("name", "") for a in doc.get("authors", [])[:3]),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })

    return new_papers, True


# ── Main run ─────────────────────────────────────────────────────────────
def main():
    trials = load_json(TRIALS_PATH, [])
    papers = load_json(PAPERS_PATH, [])

    seen_trial_ids = {uid_hash(t["nct_id"]) for t in trials}
    seen_paper_ids = {uid_hash(p["pmid"]) for p in papers}

    new_trials, trials_ok = fetch_new_trials(seen_trial_ids)
    time.sleep(0.5)
    new_papers, papers_ok = fetch_new_papers(seen_paper_ids)

    trials.extend(new_trials)
    papers.extend(new_papers)

    save_json(TRIALS_PATH, trials)
    save_json(PAPERS_PATH, papers)

    for t in new_trials:
        log.info(f"  New trial: {t['nct_id']} — {t['title']}")
    for p in new_papers:
        log.info(f"  New paper: {p['pmid']} — {p['title']}")

    status = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "new_trials_this_run": len(new_trials),
        "new_papers_this_run": len(new_papers),
        "total_trials_tracked": len(trials),
        "total_papers_tracked": len(papers),
        "clinicaltrials_api_ok": trials_ok,
        "pubmed_api_ok": papers_ok,
        "status": "ok" if (trials_ok and papers_ok) else "one or both sources failed — check the Actions log",
    }
    save_json(STATUS_PATH, status)

    log.info(
        f"Done. {len(new_trials)} new trial(s), {len(new_papers)} new paper(s). "
        f"Total tracked: {len(trials)} trials, {len(papers)} papers."
    )


if __name__ == "__main__":
    main()
