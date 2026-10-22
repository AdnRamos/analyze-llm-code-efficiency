"""
Repository paths shared by the pipeline, validation, analysis and dashboard.

By default everything reads and writes the published data in `data/` and `results/`. To run the study again
from scratch WITHOUT touching the published data, point these environment variables to another folder:

    STUDY_DATA_DIR     replaces data/      (e.g. runs/my-run/data)
    STUDY_RESULTS_DIR  replaces results/   (e.g. runs/my-run/results)
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA = Path(os.getenv("STUDY_DATA_DIR") or ROOT / "data").resolve()
PROBLEMS = DATA / "problems"                 # step 1: LeetCode catalogue; step 2: sample.csv
SAMPLE_CSV = PROBLEMS / "sample.csv"
GENERATIONS = DATA / "generations"           # step 3: raw LLM responses <model>/<language>/<id>.json
SUBMISSIONS = DATA / "submissions"           # step 5: judge records <model>__<language>.ndjson
REJUDGING = DATA / "rejudging_2026"          # step 5b (only after the 2026 pipeline fix)
REJUDGED = REJUDGING / "rejudged.ndjson"
CONTROL = REJUDGING / "control.ndjson"
RESULTS_CSV = DATA / "results.csv"           # final dataset, one row per judged submission (build_results.py)
CACHE = DATA / ".cache"                      # local caches, logs and progress files (not versioned)
PROBLEMS_INDEX_CACHE = CACHE / "problems_index.json"

RESULTS = Path(os.getenv("STUDY_RESULTS_DIR") or ROOT / "results").resolve()
VALIDATION_REPORTS = ROOT / "validation" / "reports"

LANGUAGES = ["C++", "Java", "Python3"]
LEETCODE_LANG = {"C++": "cpp", "Java": "java", "Python3": "python3"}
