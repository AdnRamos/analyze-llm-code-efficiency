# Validation

*Resumo em português no fim da página. Step-by-step guide: [REPRODUCING.md](../REPRODUCING.md) /
[REPRODUZINDO.md](../REPRODUZINDO.md).*

Scripts that check the integrity of the data. They never modify `data/` and never contact LeetCode. They follow
`STUDY_DATA_DIR`, so they also validate a run made from scratch.

- `python run.py check` — integrity checks of **any** run (`build_cache.py` + `check_consistency.py`).
- `python run.py audit` — the audit of the **2025 pipeline** (published data): found the defects, built the
  re-judging plan and measured the agreement of the triage rules.

## Files

Legend: ▶ script · 📚 library · 📄 input data · 📊 generated report.

| File | | `run.py` | What it does | Reads | Writes |
|---|---|---|---|---|---|
| `build_cache.py` | ▶ | check, audit | consolidates generations and judge records | `generations/`, `submissions/` | `<data>/.cache/validation/{gen_all,sub_all}.jsonl` |
| `check_consistency.py` | ▶ | check, audit | end-to-end checks (list below); exit code 1 on failure | cache, `results.csv`, `rejudging_2026/`, `reports/rejudge_plan.jsonl` | `reports/consistency.md` |
| `triage.py` | ▶ | audit | rebuilds the code judged in 2025 and classifies each failure as A/B/C | cache, `problems/sample.csv` | `reports/triage/` |
| `check_extraction.py` | ▶ | audit | corrected extractor vs. code judged in 2025: what must be re-judged | cache, `reports/triage/triagem_submissoes.csv` | `reports/extraction/`, `reports/rejudge_plan.jsonl` |
| `select_control.py` | ▶ | audit | draws 100 unchanged submissions as a drift control (seed 20261016) | `reports/extraction/plano_ressubmissao.csv` | `reports/rejudge_control.jsonl` |
| `audit_2025/code_2025.jsonl` | 📄 | — | code extracted by the 2025 pipeline (and the August 2025 re-extraction) for every generation; merged into the cache by `build_cache.py`; only the audit uses it | — | — |
| `CRITERIA.md` | 📄 | — | the A/B/C rules and flags used by `triage.py` | — | — |
| `blind_validation/score.py` | ▶ | audit | agreement between the rules and a blind classification of 100 cases (kappa, Wilson CIs) | `validacao_regras_llm.xlsx`, `validacao_mapa_cego.csv` | `reports/blind_validation/validacao.md` |
| `blind_validation/prepare.py` | ▶ | — | built the blind spreadsheet (already done; kept for transparency) | `reports/extraction/`, `reports/triage/` | `validacao_regras.xlsx`, `validacao_mapa_cego.csv` |
| `blind_validation/sheets.py`, `kappa.py` | 📚 | — | spreadsheet helpers; Cohen's kappa and confusion tables | — | — |
| `blind_validation/validacao_regras_llm.xlsx` | 📄 | — | the 100 blind cases classified by an LLM without access to rules, flags or suggestions | — | — |
| `blind_validation/validacao_mapa_cego.csv` | 📄 | — | blind id → submission and rule suggestion | — | — |
| `blind_validation/validacao_classificacao_llm.csv` | 📄 | — | the blind classification with justifications | — | — |

### Reports (`reports/`, generated)

| File | Content |
|---|---|
| `consistency.md` | result of every check |
| `triage/triagem_submissoes.csv` | one row per judged submission: flags, rebuilt code adherence, A/B/C suggestion and rule |
| `triage/resumo_por_{flag,modelo,questao}.csv`, `resumo_reconstrucao.csv` | summaries |
| `triage/RELATORIO.md` | triage report (counts per language and verdict) |
| `triage/amostra_fase3.csv` | sample drawn for the blind validation |
| `extraction/plano_ressubmissao.csv` | every submission: old vs. corrected extraction, reasons to re-judge |
| `extraction/RELATORIO.md` | what changes with the corrected pipeline |
| `rejudge_plan.jsonl` | the 2,560 submissions to re-judge with their corrected code (input of `pipeline/5_submit/rejudge.py`) |
| `rejudge_control.jsonl` | the 100 control submissions |
| `blind_validation/validacao.md` | agreement report (kappa 0.636) |

### What `check_consistency.py` verifies

Any run: one generation per (model, language, problem); raw response present; `code` = corrected extractor output;
keys never judged = generations
classified `invalid`; slug = problem id; verdicts given in the requested language; `results.csv` = output of
`build_results.py`. Published data, in addition: every 2025 submission judged in another language/problem or whose
code changes is in the re-judging plan; re-judged code = corrected extractor output; controls kept their verdicts;
pending re-judgings.

---

## Resumo em português

`python run.py check` valida qualquer execução (inclusive do zero): contagens, chaves, código extraído, linguagem e
questão julgadas e a montagem de `results.csv`. `python run.py audit` refaz a auditoria do pipeline de 2025: classifica
as falhas (A/B/C, regras em `CRITERIA.md`), lista o que precisava ser rejulgado, sorteia o grupo de controle e mede a
concordância das regras com uma classificação cega (kappa 0,636). As tabelas acima descrevem cada arquivo e cada
relatório gerado.
