"""
Step 5 (final): builds data/results.csv, the dataset analysed in the paper (one row per judged submission).

  input   data/submissions/<model>__<language>.ndjson   judge records written by the submission scripts
                                                        (the last record of each (model, language, problem) counts)
          data/rejudging_2026/rejudged.ndjson           OPTIONAL: verdicts of the submissions re-judged after the
                                                        October 2026 pipeline fix; they replace the earlier verdict.
                                                        A run made from scratch with the corrected pipeline has none.
  output  data/results.csv                              sorted by model, language and problem id

Columns: modelo, linguagem, slug, id_questao, categoria_declarada, categoria_calculada, categoria_ok, status, aceito,
tempo_ms, memoria_mb (accepted only), submission_id, data_julgamento (date of the verdict), fonte
('2025' or '2026' in the published data; 'judge' in a run without re-judging).
Ground-truth rows (community solutions, if any) are left out. Inputs are never modified.

Usage: python pipeline/5_submit/build_results.py
"""
import csv
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.paths import REJUDGED, RESULTS_CSV, SUBMISSIONS  # noqa: E402

COLS = ["modelo", "linguagem", "slug", "id_questao", "categoria_declarada", "categoria_calculada", "categoria_ok",
        "status", "aceito", "tempo_ms", "memoria_mb", "submission_id", "data_julgamento", "fonte"]


def fmt(v):
    return "" if v is None else str(v)


def categoria_calculada(r):
    """Same rule as the submission scripts (without local tests)."""
    if r.get("erro_compilacao") or (r.get("compilou") is False and r.get("status") == "Compile Error"):
        return "invalid"
    return "actual_correct" if r.get("aceito") else "semantic_incorrect"


def load_judged():
    """Last judge record of each (model, language, slug) in data/submissions/."""
    last = {}
    for p in sorted(SUBMISSIONS.glob("*.ndjson")):
        for line in p.open(encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                if r.get("ground_truth") or r.get("modelo") == "ground_truth":
                    continue
                k = (r["modelo"], r["linguagem"], r["slug"])
                if k not in last or r.get("ts_epoch", 0) >= last[k].get("ts_epoch", 0):
                    last[k] = r
    return last


def load_2026():
    res = {}
    if not REJUDGED.exists():
        return res
    for line in REJUDGED.open(encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            if r.get("status") not in (None, "Timeout"):
                res[(r["modelo"], r["linguagem"], int(r["id"]))] = r
    return res


def main():
    judged = load_judged()
    rej = load_2026()
    out, used = [], set()
    for r in judged.values():
        k = (r["modelo"], r["linguagem"], int(r["id_questao"]))
        ok = bool(r.get("aceito"))
        ts = r.get("ts_epoch")
        row = {"modelo": r["modelo"], "linguagem": r["linguagem"], "slug": r["slug"], "id_questao": k[2],
               "categoria_declarada": fmt(r.get("categoria_declarada")),
               "categoria_calculada": fmt(r.get("categoria_calculada")), "categoria_ok": fmt(r.get("categoria_ok")),
               "status": r["status"], "aceito": str(ok),
               "tempo_ms": fmt(r.get("tempo_ms")) if ok else "", "memoria_mb": fmt(r.get("memoria_mb")) if ok else "",
               "submission_id": fmt(r.get("submission_id")),
               "data_julgamento": datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date().isoformat() if ts else "",
               "fonte": "2025" if rej else "judge"}
        s = rej.get(k)
        if s:
            used.add(k)
            ok = bool(s.get("aceito"))
            row.update({"status": s["status"], "aceito": str(ok),
                        "tempo_ms": fmt(s.get("tempo_ms")) if ok else "", "memoria_mb": fmt(s.get("memoria_mb")) if ok else "",
                        "submission_id": fmt(s.get("submission_id")), "categoria_calculada": categoria_calculada(s),
                        "data_julgamento": str(s.get("data_utc", ""))[:10], "fonte": "2026"})
            row["categoria_ok"] = str(row["categoria_declarada"] == row["categoria_calculada"])
        out.append(row)
    out.sort(key=lambda x: (x["modelo"], x["linguagem"], x["id_questao"]))
    with RESULTS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)
    acc = sum(o["status"] == "Accepted" for o in out)
    print("rows %d | re-judged %d | not matched %d | acceptance %.1f%%"
          % (len(out), len(used), len(set(rej) - used), 100 * acc / max(1, len(out))))


if __name__ == "__main__":
    main()
