import json
from pathlib import Path

import streamlit as st
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"


def load_json(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


st.set_page_config(page_title="TB Treatment Tracker", page_icon="🧬", layout="wide")
st.title("🧬 TB Treatment & Therapy Tracker")
st.caption(
    "Tracks new clinical trials (ClinicalTrials.gov) and new research papers (PubMed) "
    "on tuberculosis treatment and therapy. Both official, free sources — no scraping."
)

status = load_json(DATA_DIR / "status.json", {})
trials = load_json(DATA_DIR / "trials.json", [])
papers = load_json(DATA_DIR / "papers.json", [])

col1, col2, col3 = st.columns(3)
last_run = status.get("last_run") or "never"
col1.metric("Last checked", last_run[:16].replace("T", " ") if last_run != "never" else "never")
col2.metric("Trials tracked", status.get("total_trials_tracked", 0))
col3.metric("Papers tracked", status.get("total_papers_tracked", 0))

if status.get("status") not in ("ok", None):
    st.warning(f"Status: {status.get('status')}")

st.divider()

tab1, tab2 = st.tabs(["🧪 Clinical Trials", "📄 Research Papers"])

with tab1:
    if trials:
        df = pd.DataFrame(trials).sort_values("last_update_posted", ascending=False)
        status_filter = st.multiselect(
            "Filter by trial status",
            options=sorted(df["status"].dropna().unique()),
            default=None,
        )
        if status_filter:
            df = df[df["status"].isin(status_filter)]
        st.dataframe(
            df[["title", "status", "phase", "sponsor", "last_update_posted", "url"]],
            use_container_width=True,
        )
    else:
        st.write("No trials tracked yet — check back after the first run.")

with tab2:
    if papers:
        df = pd.DataFrame(papers).sort_values("date_found", ascending=False)
        st.dataframe(
            df[["title", "journal", "authors", "pub_date", "url"]],
            use_container_width=True,
        )
    else:
        st.write("No papers tracked yet — check back after the first run.")
