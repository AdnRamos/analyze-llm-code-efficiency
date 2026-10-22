"""Consolidates data/generations and data/submissions into data/.cache/validation/ (read-only on the sources).
Honours STUDY_DATA_DIR.
Usage: python validation/build_cache.py            (or in parts: build_cache.py <model> ... ; build_cache.py --merge)"""
import glob
import json
import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pipeline"))
from lib.paths import CACHE, GENERATIONS, SUBMISSIONS  # noqa: E402

# code extracted by the 2025 pipeline (and the August 2025 re-extraction), used only by the audit scripts
AUDIT_2025 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_2025", "code_2025.jsonl")

GEN, SUB, OUT = str(GENERATIONS), str(SUBMISSIONS), str(CACHE / "validation")


def load_old():
    old = {}
    if os.path.exists(AUDIT_2025) and os.path.abspath(GEN) == os.path.abspath(os.path.join(os.path.dirname(AUDIT_2025), "..", "..", "data", "generations")):
        for line in open(AUDIT_2025, encoding="utf-8"):
            r = json.loads(line)
            old[(r.pop("modelo").replace("/", "_"), r.pop("linguagem"), int(r.pop("id")))] = r
    return old


def build_model(model, old):
    """One file per model, so the cache can also be built in parts (python validation/build_cache.py <model> ...)."""
    with open(os.path.join(OUT, "gen_%s.jsonl" % model), "w", encoding="utf-8") as o:
        for f in sorted(glob.glob(os.path.join(GEN, model, "*", "*.json"))):
            s = open(f, encoding="utf-8-sig").read()
            try:
                j = json.loads(s)
                j["_strict"] = True
            except Exception:
                j = json.loads(s, strict=False)
                j["_strict"] = False
            j["_file"] = os.path.relpath(f, GEN)
            j.update(old.get((j["modelo"].replace("/", "_"), j["linguagem"], int(j["id"])), {}))
            o.write(json.dumps(j, ensure_ascii=False) + "\n")


def merge():
    models = sorted(d for d in os.listdir(GEN) if os.path.isdir(os.path.join(GEN, d)))
    with open(os.path.join(OUT, "gen_all.jsonl"), "w", encoding="utf-8") as o:
        for m in models:
            with open(os.path.join(OUT, "gen_%s.jsonl" % m), encoding="utf-8") as f:
                o.write(f.read())
    with open(os.path.join(OUT, "sub_all.jsonl"), "w", encoding="utf-8") as o:
        for f in sorted(glob.glob(os.path.join(SUB, "*.ndjson"))):
            o.write(open(f, encoding="utf-8").read())


def main():
    """No arguments: whole cache. With model folders as arguments: only those parts; `--merge` joins the parts."""
    os.makedirs(OUT, exist_ok=True)
    args = sys.argv[1:]
    if args == ["--merge"]:
        merge()
    else:
        old = load_old()
        models = args or sorted(d for d in os.listdir(GEN) if os.path.isdir(os.path.join(GEN, d)))
        for m in models:
            build_model(m, old)
        if not args:
            merge()
    print("cache ->", OUT)


if __name__ == "__main__":
    main()
