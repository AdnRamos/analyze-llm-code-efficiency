"""
Single entry point of the replication package. Runs the scripts of pipeline/, validation/ and analysis/ in the
right order, so you do not need to know which file to call.

    python run.py paper          # A. reproduce the paper's numbers from the published data (no credentials)
    python run.py check          # integrity checks of the data (validation/)
    python run.py audit          # audit of the 2025 pipeline (validation/, published data only)

    python run.py collect        # B1. collect the LeetCode catalogue                   (network; hours)
    python run.py select         # B2. draw the 336-problem sample                     (seconds)
    python run.py generate       # B3. generate the solutions with the LLMs            (LLM API key; hours/days)
    python run.py extract        # B4. extract the code to submit                      (minutes)
    python run.py submit         # B5. submit to LeetCode's judge                      (LeetCode session; weeks)
    python run.py results        # B6. build data/results.csv                          (seconds)
    python run.py analysis       # B7. statistics (+ GLMM if R is installed)           (minutes)
    python run.py scratch        # B2..B4, B6, B7 and check in sequence (B1 and B5 must be run on their own)

    python run.py dashboard      # open the dashboard

For a run from scratch set STUDY_DATA_DIR and STUDY_RESULTS_DIR first (see REPRODUCING.md), so that the published
data are never overwritten.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

STEPS = {
    "collect":  [[PY, "pipeline/1_collect/collect_problems.py"]],
    "select":   [[PY, "pipeline/2_select/select_sample.py"]],
    "generate": [[PY, "pipeline/3_generate/generate_solutions.py"],
                 [PY, "pipeline/3_generate/validate_responses.py"]],
    "extract":  [[PY, "pipeline/4_extract/extract_code.py"]],
    "submit":   [[PY, "pipeline/5_submit/submit_solutions.py"],
                 [PY, "pipeline/5_submit/check_submissions.py"]],
    "results":  [[PY, "pipeline/5_submit/build_results.py"]],
    "check":    [[PY, "validation/build_cache.py"],
                 [PY, "validation/check_consistency.py"]],
    "audit":    [[PY, "validation/build_cache.py"],
                 [PY, "validation/triage.py"],
                 [PY, "validation/check_extraction.py"],
                 [PY, "validation/select_control.py"],
                 [PY, "validation/blind_validation/score.py"],
                 [PY, "validation/check_consistency.py"]],
    "analysis": [[PY, "analysis/statistics.py"],
                 ["Rscript", "analysis/glmm.R"]],
}
STEPS["paper"] = STEPS["check"] + STEPS["results"] + STEPS["analysis"]
STEPS["scratch"] = STEPS["select"] + STEPS["generate"] + STEPS["extract"] + STEPS["results"] + STEPS["check"] + STEPS["analysis"]


def run(cmd):
    if cmd[0] == "Rscript" and not shutil.which("Rscript"):
        print("\n[skip] %s (R is not installed; the GLMM needs R and the glmmTMB package)" % " ".join(cmd))
        return
    print("\n$ " + " ".join(cmd[1:] if cmd[0] == PY else cmd), flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        sys.exit("\n[stop] '%s' ended with code %d. Fix the problem above and run again." % (" ".join(cmd), r.returncode))


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in list(STEPS) + ["dashboard"]:
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "dashboard":
        sys.exit(subprocess.run([PY, "-m", "streamlit", "run", "dashboard/app.py"], cwd=ROOT).returncode)
    data = os.getenv("STUDY_DATA_DIR") or os.path.join(ROOT, "data")
    print("data:    %s\nresults: %s" % (data, os.getenv("STUDY_RESULTS_DIR") or os.path.join(ROOT, "results")))
    for cmd in STEPS[sys.argv[1]]:
        run(cmd)
    print("\n[done] %s" % sys.argv[1])


if __name__ == "__main__":
    main()
