# Reproduction guide

*Versão em português: [REPRODUZINDO.md](REPRODUZINDO.md).*

There are two ways to reproduce this study. Both start with the same setup.

| | What you get | Time | Needs |
|---|---|---|---|
| **A. From the published data** | every number and table of the paper, recomputed from the judge records in `data/` | ~10 min | Python (R optional) |
| **B. From scratch** | the whole study run again: new catalogue (optional), new generations, new verdicts | days to weeks | LLM API key, LeetCode account |

You only call **`run.py`**; it runs the scripts of the other folders in the right order and stops at the first
error. The per-folder READMEs describe every file, if you want to run or inspect a single step.

## 0. Setup

```bash
git clone <this repository> && cd analyze-llm-code-efficiency
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Optional: R ≥ 4.1 with `install.packages("glmmTMB")` for the mixed model (`run.py` skips it if R is missing).

---

## A. Reproduce the paper from the published data

```bash
python run.py paper
```

It runs, in order:

| # | Script | What it does | You should see |
|---|---|---|---|
| A1 | `validation/build_cache.py` | reads the 11,088 generations and the 10,666 judge records into a local cache | `cache -> .../data/.cache/validation` (≈2 min) |
| A2 | `validation/check_consistency.py` | integrity checks of `data/` | every line starts with `[ok]` (one pending re-judging is reported, not a failure) |
| A3 | `pipeline/5_submit/build_results.py` | rebuilds `data/results.csv` from the judge records | `rows 10666 \| re-judged 2559 \| not matched 0 \| acceptance 51.5%` |
| A4 | `analysis/statistics.py` | all numbers and tables → `results/statistics/` | `results/statistics/ESTATISTICA.md` starts with `Submissões: 10666; aceitação 51.5% [50.6, 52.5]` |
| A5 | `analysis/glmm.R` | mixed-effects model → `results/glmm/` | `glmm_resumo.txt`: `n=10666 questoes=336 aceitas=5495`, `convergence=0` |

Compare with the paper: `results/statistics/tabelas.tex` has every table between `%%BEGIN <label>` and
`%%END <label>`; `results/statistics/numeros.json` every number cited in the text. Open the dashboard with
`python run.py dashboard`.

To also re-run the audit that found the 2025 defects (triage A/B/C, extraction check, control sample, blind
validation): `python run.py audit` (see `validation/README.md`).

---

## B. Run the study from scratch

### B0. Choose a folder for the new run and configure it

```bash
export STUDY_DATA_DIR=runs/my-run/data STUDY_RESULTS_DIR=runs/my-run/results   # Windows: set VAR=value
cp config.example.json config.json
```

Edit `config.json`:

| Key | Meaning |
|---|---|
| `provider` | `groq` (as in the paper) or `openai_compatible` (vLLM, Ollama, any OpenAI-compatible cloud; `pip install openai`) |
| `base_url` | server URL, only for `openai_compatible` (e.g. `http://localhost:8000/v1`) |
| `api_key` | API key of the provider |
| `models` | models to evaluate (default: the 11 models of the paper; most are no longer served by Groq) |
| `temperature` | 0 in the paper |
| `leetcode_user`, `leetcode_pass` | only for the fallback submitter `submit_missing.py` |

All outputs go to `runs/my-run/`; `data/` and `results/` are never touched. Every step can be interrupted and run
again: it continues where it stopped.

### B1. Collect the catalogue — `python run.py collect`

Downloads every public LeetCode algorithm problem (statement, difficulty, topics, statistics, starter code).
Output: `runs/my-run/data/problems/`. No login needed; takes several hours.

**Want the same sample as the paper?** Skip B1 and copy the published catalogue instead:
`mkdir -p runs/my-run/data && cp -r data/problems runs/my-run/data/` (B2 then rebuilds exactly the same 336 problems).

### B2. Select the sample — `python run.py select`

Draws 336 problems stratified by difficulty and topic (seed 2025). Output: `problems/sample.csv`.
You should see `Total esperado: 336`, `Diferença: 0`, `Todos os temas estão representados na amostra.`

### B3. Generate the solutions — `python run.py generate`

One request per (problem, model, language), zero-shot, temperature 0. Output: `generations/<model>/<language>/<id>.json`
and figures in `results/figures/generation_validation/`. Number of requests = 336 × 3 × number of models (11,088 for
the 11 models). Rate limits are handled automatically (the model is paused and retried).

### B4. Extract the code — `python run.py extract`

Writes the code to submit in the `code` field of each generation. You should see `files N | updated N` the first time.

### B5. Submit to LeetCode — `python run.py submit`

**Run it on your own computer** (LeetCode blocks cloud IP addresses). Log in to leetcode.com in a browser, copy the
cookies `LEETCODE_SESSION` and `csrftoken`, and export them:

```bash
export LEETCODE_SESSION=... LEETCODE_CSRFTOKEN=...
python run.py submit
```

It submits every generation with code (those classified `invalid` are skipped), stores each verdict in
`submissions/`, and finally lists what is still missing
(`check_submissions.py`: only the `invalid` generations should remain). LeetCode accepts about 450–500
submissions per account per day, so the 10,000+ submissions take several weeks; just run the command again each day.
If LeetCode starts refusing the API, use `python pipeline/5_submit/submit_missing.py` (login and browser fallbacks).

### B6–B7. Build the dataset, check it and analyse it

```bash
python run.py results      # results.csv
python run.py check        # integrity checks: every line must be [ok]
python run.py analysis     # runs/my-run/results/statistics/ and glmm/
STUDY_DATA_DIR=runs/my-run/data STUDY_RESULTS_DIR=runs/my-run/results python run.py dashboard
```

(`python run.py scratch` runs B2, B3, B4, B6, B7 and the checks in one go, for when B1 and B5 are already done or
not needed.)

### What will differ from the paper, and why

- **Catalogue:** LeetCode keeps adding problems; a new B1 gives a newer catalogue and another sample. Reuse
  `data/problems/` to keep the paper's sample (B2 is deterministic).
- **Models:** Groq retired most of the 11 models after the study. They are open-weight, so they can be served
  elsewhere (`openai_compatible`), but outputs are not guaranteed to be identical even at temperature 0.
- **Judge:** LeetCode may change tests and language versions. Our 100 control submissions kept their verdicts between
  2025 and 2026; memory readings were slightly higher (median ratio 1.03).

## Troubleshooting

| Problem | Fix |
|---|---|
| `[stop] ... ended with code 1` after `check` | read the `[FAIL]` lines; the report is in `validation/reports/consistency.md` (or `<data>/.cache/consistency.md` for another run) |
| `Erro na inicialização da API` in B3 | check `api_key`, `provider` and `base_url` in `config.json`; `pip install groq` or `pip install openai` |
| B5 prints `[FAIL] Não encontrou question_id` or HTTP 403/429 | cookies expired or daily limit reached: refresh the cookies and run again later |
| B5 prints `julgada como <language>. Não gravado.` | LeetCode judged it in another language; it was not saved and will be retried on the next run |
| `[skip] Rscript analysis/glmm.R` | install R and the `glmmTMB` package to get the mixed model |
