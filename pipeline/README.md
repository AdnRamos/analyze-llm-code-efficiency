# Pipeline

*Resumo em português no fim da página. Step-by-step guide: [REPRODUCING.md](../REPRODUCING.md) /
[REPRODUZINDO.md](../REPRODUZINDO.md).*

The study as code. Five steps, each reading the output of the previous one. You normally do not call these files
directly: `python run.py <step>` (repository root) runs them in order. This page explains every file.

```
1_collect ──> 2_select ──> 3_generate ──> 4_extract ──> 5_submit ──> build_results
catalogue     sample.csv   generations    `code` field   verdicts      results.csv
```

All paths come from `lib/paths.py`: by default `data/` and `results/`; with `STUDY_DATA_DIR` / `STUDY_RESULTS_DIR`
another folder (runs from scratch).

## Files

Legend: ▶ script you can run · 📚 library imported by other scripts.

| File | | `run.py` step | What it does | Reads | Writes |
|---|---|---|---|---|---|
| `lib/paths.py` | 📚 | — | every input/output path of the study | env `STUDY_DATA_DIR`, `STUDY_RESULTS_DIR` | — |
| `lib/config.py` | 📚 | — | provider, API key, models, temperature, LeetCode login; defaults = setup of the paper | `config.json`, env `LLM_*`, `LC_LOGIN_*` | — |
| `lib/extraction.py` | 📚 | — | raw LLM response → code sent to LeetCode (corrected extractor, rules E1–E5, W1) | — | — |
| `1_collect/collect_problems.py` | ▶ | `collect` | downloads the public LeetCode catalogue | LeetCode API (no login) | `problems/questions/*.json`, `problems/{easy,medium,hard}.json`, `problems/public_problems*.json`, `problems/report.json` |
| `2_select/select_sample.py` | ▶ | `select` | stratified sample of 336 problems, seed 2025 | `problems/public_problems_without_images.json` | `problems/sample.csv` |
| `3_generate/generate_solutions.py` | ▶ | `generate` | one zero-shot request per (problem, model, language) | `problems/sample.csv`, `config.json` | `generations/<model>/<language>/<id>.json`, `.cache/generation_progress.json` |
| `3_generate/validate_responses.py` | ▶ | `generate` | summary and figures of the generation categories | `generations/` | `results/figures/generation_validation/*.png` |
| `4_extract/extract_code.py` | ▶ | `extract` | applies `lib/extraction.py`; `--check` only counts | `generations/`, `problems/sample.csv` | field `code` of `generations/` |
| `5_submit/submit_solutions.py` | ▶ | `submit` | submits every generation with code and records the verdict | `generations/`, cookies `LEETCODE_SESSION`/`LEETCODE_CSRFTOKEN` | `submissions/*.ndjson` |
| `5_submit/submit_missing.py` | ▶ | — | same as above with login and browser fallbacks, when LeetCode blocks the API | same + `leetcode_user`/`leetcode_pass` | same |
| `5_submit/check_submissions.py` | ▶ | `submit` | lists generations still without a verdict | `generations/`, `submissions/` | `.cache/missing_submissions.{csv,txt}` |
| `5_submit/rejudge.py` | ▶ | — | **published data only**: re-judging of October 2026; `--export` publishes it | `validation/reports/rejudge_*.jsonl` | `.cache/rejudge_log.ndjson`, `rejudging_2026/*.ndjson` |
| `5_submit/build_results.py` | ▶ | `results` | final dataset: last judge record of each submission, replaced by the re-judged verdict when there is one | `submissions/`, `rejudging_2026/rejudged.ndjson` (optional) | `results.csv` |

(`problems/`, `generations/`, … are folders of `data/`, or of `STUDY_DATA_DIR`.)

## How each step works

**1 — Collect.** Lists all algorithm problems from `leetcode.com/api/problems/algorithms/` and, for every public
one, queries the GraphQL API for statement, difficulty, topics, global statistics (`totalSubmissionRaw`, `acRate`),
starter code in C++/Java/Python3, hints, test cases and top community solutions. Problems with images in the
statement are set apart (the models receive text only). Incremental: files already downloaded are skipped.

**2 — Select.** Splits 336 problems across Easy/Medium/Hard in proportion to the catalogue (92/169/75), guarantees
at least one problem of every main topic, fills the remaining slots cyclically across topics and completes any gap
at random. Seed 2025: on the published catalogue it reproduces the published sample exactly.

**3 — Generate.** System prompt: act as an algorithms specialist and answer only in the format `solution:` /
`efficiency:` / `time complexity:` / `space complexity:` / `energy implications:` / `explanation:`. User prompt:
problem statement and starter code of the language, asking to complete the starter code. Temperature 0, one
attempt. Each response gets a category from the 2025 heuristic: `invalid` = no code could be found; those are
**not submitted** (the 422 "incomplete generations" of the paper).

**4 — Extract.** The code sent to LeetCode is extracted from the raw response by `lib/extraction.py`: removes
`<think>` blocks; finds the `solution:` label only at the start of a line; takes the code block of that section;
keeps imports and indentation; for Python3, wraps `self` methods in the class expected by the starter code when the
model forgot it. Deterministic.

**5 — Submit.** For each problem, model and language: submits `code`, polls the verdict, and stores status,
runtime, memory, tests passed, judged language and error messages. A verdict judged in another language than
requested is not saved (it will be retried). A slug that starts with digits is resolved as a slug (problem 650
`2-keys-keyboard` was judged as problem 2 in 2025). Resumable; LeetCode accepts ~450–500 submissions per account
per day.

**Build results.** `results.csv` has one row per judged submission: the last verdict in `submissions/`, replaced by
the 2026 verdict for the re-judged ones (column `fonte` = `2025` or `2026`; `judge` in a run without re-judging).

---

## Resumo em português

O pipeline é o estudo em código, em cinco etapas: (1) coleta do catálogo público do LeetCode; (2) seleção
estratificada de 336 questões (semente 2025; reproduz exatamente a amostra publicada); (3) geração das soluções,
zero-shot, temperatura 0, uma tentativa, via Groq ou servidor compatível com a API da OpenAI (`config.json`);
respostas sem código (`invalid`) não são submetidas; (4) extração do código com o extrator corrigido; (5) submissão ao
juiz do LeetCode e montagem de `results.csv`. A tabela "Files" acima diz, para cada arquivo, o que faz, o que lê e o
que grava. Normalmente basta `python run.py <etapa>` na raiz; o passo a passo está em
[REPRODUZINDO.md](../REPRODUZINDO.md).
