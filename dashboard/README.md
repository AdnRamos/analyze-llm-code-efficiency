# Dashboard

*Resumo em português no fim da página.*

Interactive Streamlit app to explore the dataset (English and Portuguese).

```bash
streamlit run dashboard/app.py
# another run:  STUDY_DATA_DIR=runs/my-run/data STUDY_RESULTS_DIR=runs/my-run/results streamlit run dashboard/app.py
```

- **Data:** the final dataset `data/results.csv` (corrected pipeline), with filters by model, language and
  difficulty in the sidebar.
- **Tabs:** Overview; RQ1 acceptance; RQ2 execution time; RQ3 memory; **Statistical Analysis** — first the analyses
  of the paper, read from `results/statistics/` and `results/glmm/` (full dataset, ignore the filters): acceptance
  with Wilson CIs, decision rule and omnibus tests, post hoc (Holm), GLMM and GEE, attrition, acceptance × memory
  with composition controls, contamination proxies and judge drift; then exploratory views that follow the filters
  (Cohen's d, correlation plots, composite score, recommendations); Code Explorer (raw response, code sent to
  LeetCode, judge errors, whether the verdict is from 2025 or from the 2026 re-judging); Export.
- Reads `data/` and `results/` only; run `analysis/statistics.py` first if `results/` is empty.

---

## Resumo em português

Dashboard Streamlit, em inglês e português, sobre a base final (pipeline corrigido), com filtros por modelo, linguagem
e dificuldade, as abas das três RQs, a aba Statistical Analysis (primeiro as análises do artigo, lidas de `results/`,
depois visões exploratórias que seguem os filtros) e um explorador do código gerado e dos erros do juiz.
