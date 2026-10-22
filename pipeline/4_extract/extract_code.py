"""
Step 4: extracts the code to be submitted from every raw LLM response (corrected extractor, lib/extraction.py).

For each data/generations/<model>/<language>/<id>.json:
  - `resposta` (the raw model output) is never modified;
  - `code` receives the code produced by the corrected extractor and Python wrapper, i.e. exactly what is
    sent to LeetCode by pipeline/5_submit;

Usage:
  python pipeline/4_extract/extract_code.py           # update the files
  python pipeline/4_extract/extract_code.py --check   # only report how many files would change
  python pipeline/4_extract/extract_code.py <model> ...  # restrict to some model folders
"""
import ast
import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.extraction import prepare_submission  # noqa: E402
from lib.paths import GENERATIONS, SAMPLE_CSV  # noqa: E402

csv.field_size_limit(10 ** 9)


def load_starters():
    with SAMPLE_CSV.open(encoding="utf-8", newline="") as f:
        return {int(r["id"]): ast.literal_eval(r["starter_code"]) for r in csv.DictReader(f)}


def main(check=False, models=None):
    starters = load_starters()
    total = changed = 0
    for path in sorted(GENERATIONS.glob("*/*/*.json")):
        if models and path.parts[-3] not in models:
            continue
        raw = path.read_text(encoding="utf-8-sig")
        try:
            g = json.loads(raw)
        except json.JSONDecodeError:
            try:
                g = json.loads(raw, strict=False)
            except json.JSONDecodeError as e:
                print("skip (invalid JSON): %s (%s)" % (path, e))
                continue
        total += 1
        code, _ = prepare_submission(g.get("resposta"), g["linguagem"], starters[int(g["id"])])
        if g.get("code") == code:
            continue
        changed += 1
        if check:
            continue
        g["code"] = code
        tmp = path.with_suffix(".json.tmp")   # atomic write: an interrupted run never leaves a truncated file
        tmp.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    print("files %d | %s %d" % (total, "would change" if check else "updated", changed))


if __name__ == "__main__":
    main(check="--check" in sys.argv, models=[a for a in sys.argv[1:] if not a.startswith("--")])
