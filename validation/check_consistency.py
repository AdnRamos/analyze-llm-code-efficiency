"""
Integrity checks of a dataset (no network, nothing is modified). Works on the published data (data/) and on a run
made from scratch (STUDY_DATA_DIR=...).

General checks (any run):
  1. generations   one file per (configured model, language, sampled problem); raw response present; `code` is
                   exactly what the corrected extractor produces from it (step 4 applied).
  2. submissions   the judged keys are exactly the generations with code: the keys never judged are the
                   generations classified as `invalid` (incomplete);
                   slug and problem id agree with the sample; every verdict was given in the requested language.
  3. results.csv   equals what pipeline/5_submit/build_results.py produces from its inputs.

Checks of the 2026 pipeline fix (only when data/rejudging_2026/ exists; need validation/triage.py and
validation/check_extraction.py first):
  4. every 2025 submission judged in another language or problem, or whose code changes with the corrected
     extractor, is in the re-judging plan; re-judged code = corrected extractor output; controls; pending ones.

Usage: python validation/build_cache.py && python validation/check_consistency.py
Report: validation/reports/consistency.md (or <STUDY_DATA_DIR>/.cache/consistency.md for another run).
Exit code 1 if a check fails.
"""
import ast
import csv
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pipeline"))
sys.path.insert(0, str(HERE.parent / "pipeline" / "5_submit"))
from lib.extraction import prepare_submission  # noqa: E402
from lib.config import load_config  # noqa: E402
from lib.paths import (CACHE, CONTROL, DATA, LANGUAGES, REJUDGED, RESULTS_CSV,  # noqa: E402
                       ROOT, SAMPLE_CSV, SUBMISSIONS)
import build_results as B  # noqa: E402

csv.field_size_limit(10 ** 9)
REPORTS = HERE / "reports"
PUBLISHED = DATA == (ROOT / "data").resolve()
checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    print("[%s] %s %s" % ("ok" if ok else "FAIL", name, detail))


def norm(c):
    return "\n".join(l.rstrip() for l in (c or "").strip("\n").split("\n"))


def key_row(r):
    return (r["modelo"], r["linguagem"], int(float(r["id_questao"])))


def main():
    with SAMPLE_CSV.open(encoding="utf-8", newline="") as f:
        sample = {int(r["id"]): r for r in csv.DictReader(f)}
    starters = {k: ast.literal_eval(v["starter_code"]) for k, v in sample.items()}
    models = [m.replace("/", "_") for m in load_config()["models"]]
    check("sample", len(sample) > 0, "(%d problems)" % len(sample))

    # 1. generations
    gen = {}
    with (CACHE / "validation" / "gen_all.jsonl").open(encoding="utf-8") as f:
        for line in f:
            g = json.loads(line)
            gen[(g["modelo"].replace("/", "_"), g["linguagem"], int(g["id"]))] = g
    expected = {(m, l, q) for m in models for l in LANGUAGES for q in sample}
    check("generations: one per (model, language, problem)", set(gen) == expected,
          "(%d files; expected %d = %d models x 3 x %d)" % (len(gen), len(expected), len(models), len(sample)))
    check("generations: raw response present", all("resposta" in g for g in gen.values()))
    bad = [k for k, g in gen.items() if k[2] in starters
           and g.get("code") != prepare_submission(g.get("resposta"), k[1], starters[k[2]])[0]]
    check("generations: `code` = corrected extractor output (step 4)", not bad, "(%d differ)" % len(bad))

    # 2. submissions (first round)
    last, n_rec = {}, 0
    for p in sorted(SUBMISSIONS.glob("*.ndjson")):
        for line in p.open(encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                if r.get("ground_truth") or r.get("modelo") == "ground_truth":
                    continue
                n_rec += 1
                k = (r["modelo"], r["linguagem"], r["slug"])
                if k not in last or r.get("ts_epoch", 0) >= last[k].get("ts_epoch", 0):
                    last[k] = r
    rows1 = list(last.values())
    check("submissions: judged keys", len(rows1) > 0, "(%d keys, %d records)" % (len(last), n_rec))
    judged = {key_row(r) for r in rows1}
    never = set(gen) - judged
    invalid = {k for k, g in gen.items() if g.get("categoria") == "invalid"}
    check("never judged = generations classified `invalid` (incomplete)", never == invalid and judged <= set(gen),
          "(%d never judged, %d invalid)" % (len(never), len(invalid)))
    check("slug = problem id in every row", all(sample[key_row(r)[2]]["slug"] == r["slug"] for r in rows1))
    wrong_lang = {key_row(r) for r in rows1
                  if last[(r["modelo"], r["linguagem"], r["slug"])].get("lang_pretty") not in (None, r["linguagem"])}

    # 4. pipeline fix (published data only)
    rej = B.load_2026()
    plan, pending = {}, []
    if rej:
        check("2025: submissions judged in another language (pipeline bug, re-judged below)", True, "(%d)" % len(wrong_lang))
        with (REPORTS / "rejudge_plan.jsonl").open(encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                plan[(r["modelo"], r["linguagem"], int(r["id"]))] = r
        check("2025: every submission judged in another language is in the plan", wrong_lang <= set(plan))
        q650 = {k for k in judged if sample[k[2]]["slug"][:1].isdigit()}
        check("2025: problems with a slug starting with digits (650) are in the plan", q650 <= set(plan), "(%d)" % len(q650))
        with open(REPORTS / "extraction" / "plano_ressubmissao.csv", encoding="utf-8-sig", newline="") as f:
            changed = {(r["modelo"], r["linguagem"], int(r["id"])) for r in csv.DictReader(f) if "codigo_mudou" in r["motivos"]}
        check("2025: every submission whose code changes is in the plan", changed <= set(plan), "(%d)" % len(changed))
        lang26 = [k for k, r in rej.items() if r.get("lang_pretty") not in (None, r["linguagem"])]
        check("2026: re-judged in the requested language", not lang26, "(%d wrong)" % len(lang26))
        code26 = [k for k in rej if k in plan and norm(plan[k]["codigo"]) != norm(gen[k]["code"])]
        check("2026: code re-judged = corrected extractor output", not code26, "(%d differ)" % len(code26))
        pending = sorted(set(plan) - set(rej))
        check("2026: re-judging coverage", True, "(%d of %d done; pending: %s)" % (
            len(set(plan) & set(rej)), len(plan), ", ".join("%s/%s/%d" % k for k in pending) or "none"))
        by_key = {key_row(r): r for r in rows1}
        ctrl = [json.loads(l) for l in CONTROL.open(encoding="utf-8") if l.strip()]
        same = sum(1 for r in ctrl if by_key[(r["modelo"], r["linguagem"], int(r["id"]))]["status"] == r["status"])
        check("2026: control submissions keep the 2025 verdict", same == len(ctrl), "(%d/%d)" % (same, len(ctrl)))
    else:
        check("every verdict given in the requested language", not wrong_lang, "(%d wrong)" % len(wrong_lang))

    # 3. final dataset
    with RESULTS_CSV.open(encoding="utf-8", newline="") as f:
        final = list(csv.DictReader(f))
    by1 = {key_row(r): r for r in rows1}
    ok = len(final) == len(rows1) and all(
        key_row(r) in by1 and r["status"] == (rej[key_row(r)]["status"] if key_row(r) in rej else by1[key_row(r)]["status"])
        for r in final)
    check("results.csv = judge records with re-judged verdicts (build_results.py)", ok)
    if rej:
        stale = [key_row(r) for r in final if r["fonte"] != "2026" and key_row(r) in plan]
        check("results.csv: verdicts from the corrected pipeline", len(stale) == len(pending),
              "(%d still from 2025 code that changed = pending re-judgings)" % len(stale))
    acc = sum(r["status"] == "Accepted" for r in final)
    st = Counter(r["status"] for r in final)

    L = ["# Data consistency report", "", "Generated by `validation/check_consistency.py` on `%s`." % DATA, "",
         "| Check | Result | Detail |", "|---|---|---|"]
    L += ["| %s | %s | %s |" % (n, "ok" if o else "**FAIL**", d) for n, o, d in checks]
    L += ["", "## Final dataset (results.csv)", "",
          "- Judged submissions: %d; accepted: %d (%.1f%%)" % (len(final), acc, 100 * acc / max(1, len(final))),
          "- Re-judged: %d" % sum(r.get("fonte") == "2026" for r in final),
          "- Verdicts: " + ", ".join("%s %d" % kv for kv in st.most_common()), ""]
    out = REPORTS if PUBLISHED else CACHE
    out.mkdir(parents=True, exist_ok=True)
    (out / "consistency.md").write_text("\n".join(L), encoding="utf-8")
    sys.exit(0 if all(o for _, o, _ in checks) else 1)


if __name__ == "__main__":
    main()
