# Analysis

*Resumo em português no fim da página.*

Scripts that produce every number, table and figure coordinate of the paper from `data/results.csv`. They only
read `data/` (or `STUDY_DATA_DIR`) and write `results/` (or `STUDY_RESULTS_DIR`).

Run both with `python run.py analysis` (repository root). Step-by-step guide: [REPRODUCING.md](../REPRODUCING.md).

| File | Language | Reads | Writes |
|---|---|---|---|
| `statistics.py` | Python (pandas, scipy, statsmodels) | `results.csv`, `problems/sample.csv`, `rejudging_2026/control.ndjson` and `submissions/` (judge drift, when present) | `results/statistics/` (`numeros.json`, `tabelas.tex`, `posthoc.csv`, `ESTATISTICA.md`) |
| `glmm.R` | R ≥ 4.1 (glmmTMB) | `results.csv`, `problems/sample.csv` | `results/glmm/` |

## `statistics.py` (Python: pandas, scipy, statsmodels)

```bash
python analysis/statistics.py                    # final dataset      -> results/statistics/
```

What it computes:

- **RQ1 – acceptance:** overall and by model, language and difficulty, and their cross-tabulations, with 95% Wilson
  confidence intervals; outcome distribution by verdict; attrition by difficulty with lower/upper bounds (incomplete
  generations counted as failures or as accepted).
- **RQ2/RQ3 – execution time and memory** of accepted solutions: means, medians, distributions, by every factor.
- **Statistical tests:** Shapiro–Wilk; one-way ANOVA (reported for comparability) and Kruskal–Wallis. Decision
  rule: time and memory are not normal, so conclusions follow Kruskal–Wallis (effect ε²); for acceptance
  (binary) the chi-square test, with η² of the 0/1 indicator. Post hoc after each significant omnibus test:
  two-proportion z-tests (acceptance) and Dunn's test (time, memory), Holm correction.
- **Effect sizes:** Cohen's d and h for language and difficulty pairs.
- **Correlations** among model-level metrics (Pearson and Spearman) and the composition controls of the
  acceptance × memory correlation (memory relative to the same problem and language; problems solved by all models).
- **GEE** logistic model clustered by problem (robustness check of the GLMM).
- **Contamination proxies:** question id and global submission count vs. per-problem acceptance (Spearman, GEE).
- **Judge drift** (published data only): verdicts, time and memory of the 100 control submissions.

Outputs: `numeros.json` (every number), `tabelas.tex` (LaTeX tables and figure coordinates between
`%%BEGIN <label>` / `%%END <label>` markers), `posthoc.csv` (every pairwise comparison), `ESTATISTICA.md` (summary).

## `glmm.R` (R ≥ 4.1, package glmmTMB)

```bash
Rscript analysis/glmm.R            # or: Rscript analysis/glmm.R <results.csv> <sample.csv> <output dir>
```

Logistic generalised linear mixed model of acceptance with a random intercept per problem and model, language and
difficulty as crossed fixed effects (Laplace approximation). Likelihood-ratio tests for each factor and for each
two-way interaction added to the model. Outputs in `results/glmm/`: `glmm_or.csv` (odds ratios, Wald 95% CI),
`glmm_lrt_fatores.csv`, `glmm_lrt_interacoes.csv`, `glmm_resumo.txt` (random-effect SD, ICC, convergence) and
`tab_glmm.tex`.

---

## Resumo em português

`statistics.py` calcula todos os números e tabelas do artigo a partir de `data/results.csv` (aceitação com ICs de
Wilson, tempo, memória, testes de hipótese com a regra Kruskal–Wallis, post hoc com Holm, tamanhos de efeito,
correlações com controle de composição, GEE, contaminação e deriva do juiz). `glmm.R` ajusta o modelo misto
logístico (glmmTMB) com a questão como efeito aleatório e testa as interações. As saídas vão para `results/`.
