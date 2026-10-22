# -*- coding: utf-8 -*-
"""
LeetCode LLM Performance Dashboard - Comprehensive Research Companion
=====================================================================
Aligned with the paper's three research questions:
  RQ1: Acceptance Rate   (OAR, ARM, ARD, ARL + cross-tabs)
  RQ2: Execution Time    (OAET, ETM, ETD, ETL + cross-tabs)
  RQ3: Memory Usage      (OAMU, MUM, MUD, MUL + cross-tabs)
Plus: Statistical Analysis (ANOVA, Kruskal-Wallis, Cohen's d, Pearson/Spearman)
"""
from __future__ import annotations

import json, re, textwrap, warnings
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

try:
    from scipy import stats as sp_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

warnings.filterwarnings("ignore", category=FutureWarning)

# ==================================================================
# CONFIG
# ==================================================================
st.set_page_config(
    page_title="LLM Code Efficiency - Research Dashboard",
    page_icon="\U0001F4CA",
    layout="wide",
    initial_sidebar_state="expanded",
)
px.defaults.template = "plotly_white"
COLORS_MODEL = px.colors.qualitative.Set3
COLORS_LANG = {"C++": "#636EFA", "Java": "#EF553B", "Python3": "#00CC96"}
COLORS_DIFF = {"Easy": "#2ecc71", "Medium": "#f39c12", "Hard": "#e74c3c"}
COLORS_STATUS = {"Accepted": "#2ecc71", "Compilation Error": "#e74c3c", "Wrong Answer": "#f39c12"}

# All paths are resolved relative to the repository root, so the app runs from any cwd
# (recommended: `streamlit run dashboard/app.py` from the repo root).
ROOT = Path(__file__).resolve().parents[1]
# STUDY_DATA_DIR / STUDY_RESULTS_DIR point the dashboard to a run made from scratch (see pipeline/README.md)
DATA_DIR = Path(os.getenv("STUDY_DATA_DIR") or ROOT / "data").resolve()
RESULTS_DIR = Path(os.getenv("STUDY_RESULTS_DIR") or ROOT / "results").resolve()
RESULTS_CSV_FINAL = DATA_DIR / "results.csv"                    # corrected final dataset (paper)
LLM_DATA = DATA_DIR / "generations"                             # <model>/<language>/<id>.json
DATASETS = DATA_DIR / "problems"                                # easy.json, medium.json, hard.json, sample.csv
SUBMISSIONS_2025 = DATA_DIR / "submissions"                     # <model>__<language>.ndjson (2025 judge records)
REJUDGED_2026 = DATA_DIR / "rejudging_2026" / "rejudged.ndjson" # 2026 judge records
STATS_DIR = RESULTS_DIR / "statistics"                     # precomputed by analysis/statistics.py
GLMM_DIR = RESULTS_DIR / "glmm"                            # precomputed by analysis/glmm.R

EXPECTED_PER_MODEL = 1_008  # 336 problems x 3 languages
NUM_MODELS = 11
TOTAL_EXPECTED = EXPECTED_PER_MODEL * NUM_MODELS  # 11,088

MODEL_SHORT = {
    "allam-2-7b": "allam-2-7b",
    "deepseek-r1-distill-llama-70b": "deepseek-r1-70b",
    "gemma2-9b-it": "gemma2-9b-it",
    "llama-3.1-8b-instant": "llama-3.1-8b",
    "llama-3.3-70b-versatile": "llama-3.3-70b",
    "llama3-70b-8192": "llama3-70b",
    "llama3-8b-8192": "llama3-8b",
    "meta-llama_llama-4-maverick-17b-128e-instruct": "llama-4-maverick",
    "meta-llama_llama-4-scout-17b-16e-instruct": "llama-4-scout",
    "moonshotai_kimi-k2-instruct": "kimi-k2",
    "qwen_qwen3-32b": "qwen3-32b",
}

DIFF_PT_EN = {"Fácil": "Easy", "Média": "Medium", "Difícil": "Hard"}
DIFF_ORDER = ["Easy", "Medium", "Hard"]
LANG_ORDER = ["C++", "Java", "Python3"]


# ==================================================================
# i18n - BILINGUAL SUPPORT (EN / PT-BR)
# ==================================================================
UI: Dict[str, Dict[str, str]] = {
    "en": {
        "sidebar.title": "\U0001F4CA Global Filters",
        "sidebar.caption": "These filters affect all tabs",
        "sidebar.language": "Output language",
        "sidebar.models": "Models",
        "sidebar.langs": "Languages",
        "sidebar.difficulty": "Difficulty",
        "sidebar.cache": "Cache",
        "sidebar.clear_cache": "\U0001F5D1\uFE0F Clear cache",
        "main.title": "\U0001F4CA LLM Code Efficiency - Research Dashboard",
        "main.caption": "Interactive dashboard for consulting the research data on LLM-generated code efficiency",
        "main.nodata": "No data found. Check that `data/results.csv` and `data/problems/` exist (run from the repository root: `streamlit run dashboard/app.py`).",
        "tab.overview": "\U0001F4CA Overview",
        "tab.rq1": "\u2705 RQ1: Acceptance",
        "tab.rq2": "\u23F1\uFE0F RQ2: Execution Time",
        "tab.rq3": "\U0001F4BE RQ3: Memory Usage",
        "tab.stats": "\U0001F4C8 Statistical Analysis",
        "tab.explorer": "\U0001F50D Code Explorer",
        "tab.export": "\U0001F4CB Export Data",
        "ov.header": "Study Overview",
        "ov.desc": "This dashboard presents the results of a large-scale evaluation of **11 LLMs** available on the Groq Cloud platform, evaluated on **336 LeetCode problems** in **3 programming languages** (C++, Java, Python3). Acceptance is single-attempt, zero-shot (each problem is submitted once per model and language, with no retries or feedback); it is 51.5% in the corrected final dataset used in the paper.",
        "ov.total_subs": "Total Submissions",
        "ov.oar": "Acceptance Rate (OAR, single-attempt zero-shot)",
        "ov.avg_time": "Avg Time (Accepted)",
        "ov.avg_mem": "Avg Memory (Accepted)",
        "ov.incomplete_header": "Incomplete Generations",
        "ov.incomplete_desc": "Some LLMs produced truncated or incomplete outputs that were not submitted to LeetCode.",
        "ov.total_expected": "Total Expected",
        "ov.total_sub_missing": "Total Submitted / Missing",
        "ov.dist_header": "Overall Outcome Distribution (OAR)",
        "ov.pie_title": "Distribution of 3 Statuses (Paper)",
        "ov.table_3cat": "**Results Table (3 categories - paper)**",
        "ov.table_granular": "**Granular breakdown (original LeetCode status)**",
        "ov.sample_header": "Sample Composition",
        "ov.by_diff": "**By Difficulty**",
        "ov.models_eval": "**Models Evaluated**",
        "ov.by_lang": "**Languages**",
        "ov.topic_header": "Distribution by Topic (tema_principal)",
        "ov.topic_chart": "Number of problems per topic in the sample",
        "col.model": "Model",
        "col.expected": "Expected",
        "col.submitted": "Submitted",
        "col.missing": "Missing",
        "col.result": "Result",
        "col.count": "Count",
        "col.status": "Status",
        "col.problems": "Problems",
        "col.submissions": "Submissions",
        "col.topic": "Topic",
        "rq1.header": "RQ1: Acceptance Rates",
        "rq1.desc": "*How do the acceptance rates of different LLMs vary by difficulty and language?*",
        "rq1.nodata": "No data available for the selected filters.",
        "rq1.ard_header": "ARD - Acceptance Rate by Difficulty",
        "rq1.ard_chart": "Acceptance Rate by Difficulty (ARD)",
        "rq1.arm_header": "ARM - Acceptance Rate by Model",
        "rq1.arm_chart": "Acceptance Rate by Model (ARM)",
        "rq1.arl_header": "ARL - Acceptance Rate by Language",
        "rq1.arl_chart": "Acceptance Rate by Language (ARL)",
        "rq1.crosstabs": "Cross-Tabulations",
        "rq1.ct_md": "Model x Difficulty",
        "rq1.ct_ml": "Model x Language",
        "rq1.ct_ld": "Language x Difficulty",
        "rq1.ct_md_title": "**Acceptance Rate (%) by Model and Difficulty**",
        "rq1.ct_ml_title": "**Acceptance Rate (%) by Model and Language**",
        "rq1.ct_ld_title": "**Acceptance Rate (%) by Language and Difficulty**",
        "rq1.hm_md": "Heatmap: Acceptance (%) - Model x Difficulty",
        "rq1.hm_ml": "Heatmap: Acceptance (%) - Model x Language",
        "rq1.fail_header": "Failure Distribution by Model",
        "rq1.fail_stacked": "Status by Model (stacked)",
        "rq1.fail_granular": "Granular status breakdown (7 original categories)",
        "rq1.byq_header": "Acceptance Rate by Problem",
        "rq1.byq_chart": "Acceptance by Problem",
        "rq2.header": "RQ2: Execution Time",
        "rq2.desc": "*How does the average execution time of accepted solutions vary by model, difficulty and language?*\n\n**Note:** Metrics computed only on accepted submissions.",
        "rq2.nodata": "No accepted submissions for the selected filters.",
        "rq2.oaet_header": "OAET - Overall Execution Time Statistics",
        "rq2.mean": "Mean",
        "rq2.median": "Median",
        "rq2.std": "Std Dev",
        "rq2.p99": "P99",
        "rq2.max": "Maximum",
        "rq2.based_on": "Based on {n:,} accepted submissions",
        "rq2.hist_header": "Execution Time Distribution",
        "rq2.hist_title": "Execution Time Distribution (Accepted)",
        "rq2.etd_header": "ETD - Execution Time by Difficulty",
        "rq2.etd_chart": "Mean Time by Difficulty (ETD)",
        "rq2.etm_header": "ETM - Execution Time by Model",
        "rq2.etm_chart": "Mean Time by Model (ETM) - sorted",
        "rq2.etl_header": "ETL - Execution Time by Language",
        "rq2.etl_chart": "Mean Time by Language (ETL)",
        "rq2.ct_header": "Cross-Tabulations - Execution Time",
        "rq2.ct_md_title": "**Mean Time (ms) by Model and Difficulty**",
        "rq2.ct_ml_title": "**Mean Time (ms) by Model and Language**",
        "rq2.ct_ld_title": "**Mean Time (ms) by Language and Difficulty**",
        "rq2.hm_md": "Heatmap: Mean Time (ms) - Model x Difficulty",
        "rq2.hm_ml": "Heatmap: Mean Time (ms) - Model x Language",
        "rq2.box_header": "Distributions (Box Plots)",
        "rq2.box_model": "By Model",
        "rq2.box_lang": "By Language",
        "rq2.box_diff": "By Difficulty",
        "rq2.box_model_title": "Time Distribution by Model",
        "rq2.box_lang_title": "Time Distribution by Language",
        "rq2.box_diff_title": "Time Distribution by Difficulty",
        "rq3.header": "RQ3: Memory Usage",
        "rq3.desc": "*How does the average memory usage of accepted solutions vary by model, difficulty and language?*\n\n**Note:** Metrics computed only on accepted submissions.",
        "rq3.nodata": "No accepted submissions for the selected filters.",
        "rq3.oamu_header": "OAMU - Overall Memory Usage Statistics",
        "rq3.hist_header": "Memory Usage Distribution",
        "rq3.hist_title": "Memory Usage Distribution (Accepted)",
        "rq3.mud_header": "MUD - Memory Usage by Difficulty",
        "rq3.mud_chart": "Mean Memory by Difficulty (MUD)",
        "rq3.mum_header": "MUM - Memory Usage by Model",
        "rq3.mum_chart": "Mean Memory by Model (MUM) - sorted",
        "rq3.mul_header": "MUL - Memory Usage by Language",
        "rq3.mul_chart": "Mean Memory by Language (MUL)",
        "rq3.ct_header": "Cross-Tabulations - Memory Usage",
        "rq3.ct_md_title": "**Mean Memory (MB) by Model and Difficulty**",
        "rq3.ct_ml_title": "**Mean Memory (MB) by Model and Language**",
        "rq3.ct_ld_title": "**Mean Memory (MB) by Language and Difficulty**",
        "rq3.hm_md": "Heatmap: Mean Memory (MB) - Model x Difficulty",
        "rq3.hm_ml": "Heatmap: Mean Memory (MB) - Model x Language",
        "rq3.box_header": "Distributions (Box Plots)",
        "rq3.box_model_title": "Memory Distribution by Model",
        "rq3.box_lang_title": "Memory Distribution by Language",
        "rq3.box_diff_title": "Memory Distribution by Difficulty",
        "rq3.tradeoff_header": "Speed x Memory Trade-off",
        "rq3.tradeoff_chart": "Trade-off: Mean Time x Mean Memory by Language",
        "st.header": "Statistical Analysis",
        "st.desc": "Analyses inspired by Guimaraes et al. (2025): Wilson confidence intervals, omnibus tests (ANOVA / Kruskal-Wallis with the decision rule), post hoc with Holm, GLMM and GEE, attrition, acceptance x memory composition controls, contamination proxies and judge drift, followed by Cohen's d, correlation plots and a composite score on the sidebar filters. Time and memory are not normal (Shapiro-Wilk), so conclusions follow Kruskal-Wallis; ANOVA is shown for comparability.",
        "st.no_scipy": "\u26A0\uFE0F `scipy` library not found. Install with `pip install scipy` to enable statistical tests.",
        "st.nodata": "No data available.",
        "st.anova_desc": "eta squared thresholds: **small** (< 0.06), **medium** (0.06-0.14), **large** (> 0.14)",
        "st.cohens_lang_header": "Cohen's d - Language Comparisons",
        "st.cohens_desc": "Thresholds: **negligible** (|d| < 0.2), **small** (0.2-0.5), **medium** (0.5-0.8), **large** (> 0.8)",
        "st.cohens_diff_header": "Cohen's d - Difficulty Comparisons (Acceptance)",
        "st.corr_viz_header": "Correlation Visualizations",
        "st.corr_acc_mem": "Acceptance vs Mean Memory (per model)",
        "st.corr_acc_time": "Acceptance vs Mean Time (per model)",
        "st.corr_need": "scipy required for correlation calculations.",
        "st.corr_insuf": "Insufficient data.",
        "st.composite_header": "Composite Score (Trade-off)",
        "st.composite_desc": "Normalized ranking combining acceptance (up), execution time (down) and memory (down), with equal weights. Higher values = better overall balance.",
        "st.composite_chart": "Composite Score by Model (higher = better)",
        "st.rec_header": "Practical Recommendations",
        "st.rec_body": """Based on the combined analysis of the three RQs (corrected final data; single-attempt, zero-shot). Per-model time and memory rankings are descriptive only: the model effect on execution time is small (Kruskal-Wallis significant) and no model pair differs after Holm correction.

| Priority | Recommendation |
|---|---|
| **Maximize acceptance** | `kimi-k2-instruct` (85.9%), `qwen3-32b` (79.7%), `deepseek-r1-70b` (71.5%). The three languages reach similar acceptance (C++ 50.3%, Java 51.9%, Python3 52.4%); the language effect is not significant in ANOVA and only a small effect appears in the joint GLMM. |
| **Minimize time** | Descriptive: Java (25.4ms) ~ C++ (28.3ms) << Python3 (151.2ms). Model means (e.g. `qwen3-32b` 40.6ms, `llama3-70b` 45.7ms) are not statistically distinguishable pairwise. |
| **Minimize memory** | Python3 (22.4MB) < C++ (29.1MB) < Java (48.0MB). Differences between models are negligible (1 of 55 pairs significant after Holm). |
| **Best balance** | See the composite score table above (descriptive, equal weights). |

**No model or language simultaneously dominates across all three metrics.**""",
        "stcol.factor": "Factor",
        "stcol.metric": "Metric",
        "stcol.acceptance": "Acceptance",
        "stcol.time": "Time (ms)",
        "stcol.memory": "Memory (MB)",
        "stcol.effect": "Effect",
        "stcol.pair": "Pair",
        "stcol.magnitude": "Magnitude",
        "stcol.trend": "Trend",
        "ax.acceptance_pct": "Acceptance (%)",
        "ax.model": "Model",
        "ax.language": "Language",
        "ax.difficulty": "Difficulty",
        "ax.time_ms": "Time (ms)",
        "ax.memory_mb": "Memory (MB)",
        "ax.count": "Count",
        "ax.frequency": "Frequency",
        "ax.mean_time_ms": "Mean Time (ms)",
        "ax.mean_memory_mb": "Mean Memory (MB)",
        "tc.difficulty": "Difficulty",
        "tc.accepted": "Accepted",
        "tc.total": "Total",
        "tc.rate_pct": "Rate%",
        "tc.language": "Language",
        "tc.mean_ms": "Mean (ms)",
        "tc.median_ms": "Median (ms)",
        "tc.std_ms": "SD (ms)",
        "tc.mean_mb": "Mean (MB)",
        "tc.median_mb": "Median (MB)",
        "tc.std_mb": "SD (MB)",
        "tc.n": "N",
        "ex.header": "Code Explorer",
        "ex.desc": "View the code generated by LLMs and the LeetCode submission results.",
        "ex.nodata": "No LLM responses found in `data/generations/`.",
        "ex.model": "Model",
        "ex.language": "Language",
        "ex.problem": "Problem (ID)",
        "ex.code_title": "**Generated Code**",
        "ex.meta_title": "**LLM Metadata**",
        "ex.category": "Category",
        "ex.reason": "Reason",
        "ex.result_title": "**LeetCode Result**",
        "ex.status": "Status",
        "ex.time": "Time",
        "ex.memory": "Memory",
        "ex.problem_info": "**Problem Info**",
        "ex.title_field": "Title",
        "ex.diff_field": "Difficulty",
        "ex.topic_field": "Topic",
        "ex.no_result": "No submission result found for this combination.",
        "ex.empty_code": "(empty)",
        "ex.compare_header": "Side-by-Side Comparison",
        "ex.model_a": "**Model A**",
        "ex.model_b": "**Model B**",
        "ex.compare_problem": "Problem to compare",
        "ex.no_common": "No common problems between the selections.",
        "exp.header": "Export Data",
        "exp.desc": "Download filtered data in various formats for external analyses.",
        "exp.nodata": "No data available.",
        "exp.sub_header": "Submission Data (Filtered)",
        "exp.record_count": "{n:,} records with current filters",
        "exp.showing_500": "Showing first 500 rows. Download to see all data.",
        "exp.dl_csv_all": "\U0001F4E5 Download CSV (All submissions)",
        "exp.dl_json_all": "\U0001F4E5 Download JSON (All submissions)",
        "exp.dl_csv_acc": "\U0001F4E5 Download CSV (Accepted only)",
        "exp.tables_header": "Summary Tables for the Paper",
        "exp.tables_desc": "Ready-to-use tables for copy/paste into the paper.",
        "exp.table_oar": "Table: Overall Distribution (OAR)",
        "exp.table_arm_diff": "Table: ARM x Difficulty",
        "exp.table_arm_lang": "Table: ARM x Language",
        "exp.table_etm_diff": "Table: ETM x Difficulty",
        "exp.table_etm_lang": "Table: ETM x Language",
        "exp.table_mum_diff": "Table: MUM x Difficulty",
        "exp.table_mum_lang": "Table: MUM x Language",
        "exp.meta_header": "Problem Metadata",
        "exp.meta_count": "{n} problems in metadata",
        "exp.dl_meta": "\U0001F4E5 Download CSV (Metadata)",
        "ex.code_sent": "**Code sent to LeetCode (corrected pipeline)**",
        "ex.source": "Verdict source",
        "ex.src_2025": "Judged in 2025",
        "ex.src_2026": "Judged in 2026",
        "st.filtered_header": "Exploratory views on the sidebar filters",
        "st.filtered_desc": "The sections below are recomputed on the current sidebar filters (descriptive; the tests above use the full dataset).",
        "ex.err_compile": "Judge compile error message",
        "ex.err_runtime": "Judge runtime error message",
        "pp.caption": "The paper analyses below read only the precomputed files in `results/statistics/` and `results/glmm/` (produced by `analysis/statistics.py` and `analysis/glmm.R`). They always represent the full corrected dataset (10,666 judged submissions) and ignore the sidebar filters.",
        "pp.missing": "Precomputed files not found in `results/statistics/` (`numeros.json`). Run `analysis/statistics.py` first.",
        "pp.missing_part": "Not available in the precomputed files.",
        "pp.oar_note": "Overall acceptance is single-attempt, zero-shot: each problem is submitted once per model and language, with no retries or feedback.",
        "pp.oar_metric": "Overall acceptance (95% Wilson CI)",
        "pp.oar_n": "Judged submissions",
        "pp.a.header": "a. Acceptance with 95% Wilson confidence intervals",
        "pp.a.desc": "Wilson score intervals (z = 1.959964) for every cell. Each cell shows `% [lower, upper] (k/n)`. Cells with fewer judged submissions than planned reflect attrition (see section e).",
        "pp.a.marg": "Marginals (difficulty, language, model)",
        "pp.a.note_lang": "The three languages reach similar acceptance (C++ 50.3%, Java 51.9%, Python3 52.4%): the intervals overlap, the ANOVA is not significant, and only a small effect appears in the joint GLMM (section d).",
        "pp.b.header": "b. Decision rule and omnibus tests",
        "pp.b.desc": "Time and memory are strongly non-normal (Shapiro-Wilk, below), so conclusions about them follow Kruskal-Wallis (effect size epsilon squared); the one-way ANOVA is shown only for comparability. Acceptance (binary) is tested with a chi-square test of proportions, with the eta squared of the 0/1 indicator as effect size. Where ANOVA and Kruskal-Wallis disagree (e.g. model effect on time), the Kruskal-Wallis result is used.",
        "pp.b.shapiro": "Shapiro-Wilk normality tests (accepted submissions)",
        "pp.b.note_time": "Model effect on execution time: Kruskal-Wallis is significant but small, and no model pair is significant after Holm correction, so per-model time and memory rankings are descriptive.",
        "pp.c.header": "c. Post hoc comparisons (Holm correction)",
        "pp.c.desc": "Pairwise comparisons: Dunn's test for time and memory, tests of proportions for acceptance, all with Holm adjustment. Counts of significant pairs (adjusted p < 0.05):",
        "pp.c.table": "Pairwise results (`posthoc.csv`)",
        "pp.c.only_sig": "Only significant pairs (Holm p < 0.05)",
        "pp.d.header": "d. Joint model (GLMM, glmmTMB) and robustness (GEE)",
        "pp.d.desc": "Binomial GLMM of acceptance with fixed effects for model, language and difficulty and a random intercept per problem (336 problems), fitted with glmmTMB. Odds ratios (OR) with 95% CI.",
        "pp.d.ref": "Reference levels: model `{m}`, language C++, difficulty Easy.",
        "pp.d.or": "Odds ratios (GLMM)",
        "pp.d.lrt_f": "Likelihood-ratio tests: main effects",
        "pp.d.lrt_i": "Likelihood-ratio tests: interactions",
        "pp.d.summary": "Model summary (`glmm_resumo.txt`)",
        "pp.d.gee": "Robustness: GEE odds ratios (clustered by problem, `numeros.json`)",
        "pp.d.lang_note": "In the joint model the language effect is small but significant (Java and Python3 slightly above C++), although the one-way ANOVA on language is not significant.",
        "pp.e.header": "e. Attrition by difficulty (bounds)",
        "pp.e.desc": "Some planned generations were not judged (truncated or incomplete outputs). The rate among judged submissions is bracketed by a lower bound (every missing submission would have failed) and an upper bound (every missing one would have been accepted).",
        "pp.f.header": "f. Acceptance x memory correlation with composition controls",
        "pp.f.desc": "Model-level correlations (N = 11 models; N = 10 when allam-2-7b is dropped) between acceptance and memory/time, with three controls: raw means, memory/time relative to the per-problem level, and only the problem-language pairs accepted by every model.",
        "pp.f.note": "Interpretation: the raw positive association between acceptance and memory is compositional, not causal. Models that solve more problems also have accepted solutions on harder problems, which use more memory; once composition is controlled (relative memory, or only the problems solved by all models) it is no longer significant (and it is negative on the common problems). It must not be read as 'correct models write more memory-intensive code'.",
        "pp.g.header": "g. Contamination proxies",
        "pp.g.desc": "Per-problem acceptance (pooled over models and languages) against question ID (older problems have lower IDs), the global number of LeetCode submissions of the problem (popularity) and LeetCode's human acceptance rate. GEE odds ratios adjust for model, language and difficulty (z-scored predictors).",
        "pp.g.note": "Caveat: these proxies cannot separate memorization of training data from popularity (popular problems also have more public solutions, editorials and discussion). They are consistent with, but do not prove, contamination.",
        "pp.h.header": "h. Judge drift control",
        "pp.h.desc": "To check that the LeetCode judge did not change between 2025 and the 2026 re-judging, {n} unchanged submissions were judged again as controls.",
        "pp.h.note": "All verdicts are identical. Execution time is unchanged (Wilcoxon not significant), but memory readings are slightly higher in 2026 (mean ratio {r:.2f}, median ratio {mr:.2f}), so memory of re-judged submissions is interpreted with that in mind.",
        "pp.col.cell": "Cell",
        "pp.col.k": "Accepted (k)",
        "pp.col.n": "Judged (n)",
        "pp.col.pct": "Acceptance (%)",
        "pp.col.lo": "Lower 95%",
        "pp.col.hi": "Upper 95%",
        "pp.col.test": "Test",
        "pp.col.stat": "chi2 / H",
        "pp.col.df": "df",
        "pp.col.p": "p",
        "pp.col.p_holm": "p (Holm)",
        "pp.col.effect": "Effect",
        "pp.col.effect_val": "Effect size",
        "pp.col.pairs": "Significant pairs",
        "pp.col.total": "Pairs",
        "pp.col.sig": "Significant",
        "pp.col.term": "Term",
        "pp.col.or": "OR",
        "pp.col.ci": "95% CI",
        "pp.col.chisq": "chi2",
        "pp.col.planned": "Planned",
        "pp.col.missing": "Missing",
        "pp.col.rate": "Rate among judged (%)",
        "pp.col.lower": "Lower bound (%)",
        "pp.col.upper": "Upper bound (%)",
        "pp.col.control": "Control",
        "pp.col.pair": "Pair",
        "pp.col.proxy": "Proxy",
        "pp.col.rho": "Spearman rho",
        "pp.col.value": "Value",
        "pp.col.metric": "Metric",
        "pp.col.estat": "Statistic",
        "pp.col.a": "A",
        "pp.col.b": "B",
        "pp.ctl.raw": "None (model means)",
        "pp.ctl.rel": "Relative to the problem level",
        "pp.ctl.all": "Problems solved by all 11 models",
        "pp.ctl.noallam": "Problems solved by all models except allam-2-7b",
        "pp.pair.acc_mem": "Acceptance x memory",
        "pp.pair.acc_time": "Acceptance x time",
        "pp.pair.time_mem": "Time x memory",
        "pp.proxy.id": "Question ID",
        "pp.proxy.n_subm": "Global submissions (popularity)",
        "pp.proxy.humana": "Human acceptance rate (LeetCode)",
        "pp.h.same": "Same verdict",
        "pp.h.accepted": "Accepted controls",
        "pp.h.time_med": "Median time difference (ms)",
        "pp.h.time_p": "Time: Wilcoxon p",
        "pp.h.mem_mean": "Memory: mean ratio (2026/2025)",
        "pp.h.mem_med": "Memory: median ratio",
        "pp.h.mem_p": "Memory: Wilcoxon p",
    },
    "pt": {
        "sidebar.title": "\U0001F4CA Filtros Globais",
        "sidebar.caption": "Estes filtros afetam todas as abas",
        "sidebar.language": "Idioma de saida",
        "sidebar.models": "Modelos",
        "sidebar.langs": "Linguagens",
        "sidebar.difficulty": "Dificuldade",
        "sidebar.cache": "Cache",
        "sidebar.clear_cache": "\U0001F5D1\uFE0F Limpar cache",
        "main.title": "\U0001F4CA LLM Code Efficiency - Research Dashboard",
        "main.caption": "Dashboard interativo para consulta dos dados da pesquisa sobre eficiencia de codigo gerado por LLMs",
        "main.nodata": "Nenhum dado encontrado. Verifique se `data/results.csv` e `data/problems/` existem (execute a partir da raiz do repositorio: `streamlit run dashboard/app.py`).",
        "tab.overview": "\U0001F4CA Visao Geral",
        "tab.rq1": "\u2705 RQ1: Aceitacao",
        "tab.rq2": "\u23F1\uFE0F RQ2: Tempo de Execucao",
        "tab.rq3": "\U0001F4BE RQ3: Uso de Memoria",
        "tab.stats": "\U0001F4C8 Analise Estatistica",
        "tab.explorer": "\U0001F50D Explorador de Codigo",
        "tab.export": "\U0001F4CB Exportar Dados",
        "ov.header": "Visao Geral do Estudo",
        "ov.desc": "Este dashboard apresenta os resultados de uma avaliacao em larga escala de **11 LLMs** disponiveis na plataforma Groq Cloud, avaliados em **336 problemas do LeetCode** em **3 linguagens de programacao** (C++, Java, Python3). A aceita\u00e7\u00e3o \u00e9 de tentativa \u00fanica e zero-shot (cada problema \u00e9 submetido uma vez por modelo e linguagem, sem novas tentativas ou feedback); \u00e9 51,5% na base final corrigida usada no artigo.",
        "ov.total_subs": "Total de Submissoes",
        "ov.oar": "Taxa de Aceitacao (OAR, tentativa unica zero-shot)",
        "ov.avg_time": "Tempo Medio (Aceitos)",
        "ov.avg_mem": "Memoria Media (Aceitos)",
        "ov.incomplete_header": "Geracoes Incompletas",
        "ov.incomplete_desc": "Algumas LLMs produziram saidas truncadas ou incompletas que nao foram submetidas ao LeetCode.",
        "ov.total_expected": "Total Esperado",
        "ov.total_sub_missing": "Total Submetido / Faltante",
        "ov.dist_header": "Distribuicao Geral dos Resultados (OAR)",
        "ov.pie_title": "Distribuicao dos 3 Status (Paper)",
        "ov.table_3cat": "**Tabela de Resultados (3 categorias - artigo)**",
        "ov.table_granular": "**Detalhamento granular (status original do LeetCode)**",
        "ov.sample_header": "Composicao da Amostra",
        "ov.by_diff": "**Por Dificuldade**",
        "ov.models_eval": "**Modelos Avaliados**",
        "ov.by_lang": "**Linguagens**",
        "ov.topic_header": "Distribuicao por Topico (tema_principal)",
        "ov.topic_chart": "Numero de problemas por topico na amostra",
        "col.model": "Modelo",
        "col.expected": "Esperado",
        "col.submitted": "Submetido",
        "col.missing": "Faltante",
        "col.result": "Resultado",
        "col.count": "Contagem",
        "col.status": "Status",
        "col.problems": "Problemas",
        "col.submissions": "Submissoes",
        "col.topic": "Topico",
        "rq1.header": "RQ1: Taxas de Aceitacao",
        "rq1.desc": "*Como as taxas de aceitacao dos diferentes LLMs comparados variam por dificuldade e linguagem?*",
        "rq1.nodata": "Nenhum dado disponivel para os filtros selecionados.",
        "rq1.ard_header": "ARD - Taxa de Aceitacao por Dificuldade",
        "rq1.ard_chart": "Taxa de Aceitacao por Dificuldade (ARD)",
        "rq1.arm_header": "ARM - Taxa de Aceitacao por Modelo",
        "rq1.arm_chart": "Taxa de Aceitacao por Modelo (ARM)",
        "rq1.arl_header": "ARL - Taxa de Aceitacao por Linguagem",
        "rq1.arl_chart": "Taxa de Aceitacao por Linguagem (ARL)",
        "rq1.crosstabs": "Tabulacoes Cruzadas",
        "rq1.ct_md": "Modelo x Dificuldade",
        "rq1.ct_ml": "Modelo x Linguagem",
        "rq1.ct_ld": "Linguagem x Dificuldade",
        "rq1.ct_md_title": "**Taxa de Aceitacao (%) por Modelo e Dificuldade**",
        "rq1.ct_ml_title": "**Taxa de Aceitacao (%) por Modelo e Linguagem**",
        "rq1.ct_ld_title": "**Taxa de Aceitacao (%) por Linguagem e Dificuldade**",
        "rq1.hm_md": "Heatmap: Aceitacao (%) - Modelo x Dificuldade",
        "rq1.hm_ml": "Heatmap: Aceitacao (%) - Modelo x Linguagem",
        "rq1.fail_header": "Distribuicao de Falhas por Modelo",
        "rq1.fail_stacked": "Status por Modelo (empilhado)",
        "rq1.fail_granular": "Detalhamento granular dos status (7 categorias originais)",
        "rq1.byq_header": "Taxa de Aceitacao por Problema",
        "rq1.byq_chart": "Aceitacao por Problema",
        "rq2.header": "RQ2: Tempo de Execucao",
        "rq2.desc": "*Como o tempo medio de execucao das solucoes aceitas varia por modelo, dificuldade e linguagem?*\n\n**Nota:** Metricas calculadas apenas sobre submissoes aceitas (Accepted).",
        "rq2.nodata": "Nenhuma submissao aceita para os filtros selecionados.",
        "rq2.oaet_header": "OAET - Estatisticas Gerais do Tempo de Execucao",
        "rq2.mean": "Media",
        "rq2.median": "Mediana",
        "rq2.std": "Desvio Padrao",
        "rq2.p99": "P99",
        "rq2.max": "Maximo",
        "rq2.based_on": "Baseado em {n:,} submissoes aceitas",
        "rq2.hist_header": "Distribuicao do Tempo de Execucao",
        "rq2.hist_title": "Distribuicao do Tempo de Execucao (Aceitos)",
        "rq2.etd_header": "ETD - Tempo de Execucao por Dificuldade",
        "rq2.etd_chart": "Tempo Medio por Dificuldade (ETD)",
        "rq2.etm_header": "ETM - Tempo de Execucao por Modelo",
        "rq2.etm_chart": "Tempo Medio por Modelo (ETM) - ordenado",
        "rq2.etl_header": "ETL - Tempo de Execucao por Linguagem",
        "rq2.etl_chart": "Tempo Medio por Linguagem (ETL)",
        "rq2.ct_header": "Tabulacoes Cruzadas - Tempo de Execucao",
        "rq2.ct_md_title": "**Tempo Medio (ms) por Modelo e Dificuldade**",
        "rq2.ct_ml_title": "**Tempo Medio (ms) por Modelo e Linguagem**",
        "rq2.ct_ld_title": "**Tempo Medio (ms) por Linguagem e Dificuldade**",
        "rq2.hm_md": "Heatmap: Tempo Medio (ms) - Modelo x Dificuldade",
        "rq2.hm_ml": "Heatmap: Tempo Medio (ms) - Modelo x Linguagem",
        "rq2.box_header": "Distribuicoes (Box Plots)",
        "rq2.box_model": "Por Modelo",
        "rq2.box_lang": "Por Linguagem",
        "rq2.box_diff": "Por Dificuldade",
        "rq2.box_model_title": "Distribuicao do Tempo por Modelo",
        "rq2.box_lang_title": "Distribuicao do Tempo por Linguagem",
        "rq2.box_diff_title": "Distribuicao do Tempo por Dificuldade",
        "rq3.header": "RQ3: Uso de Memoria",
        "rq3.desc": "*Como o uso medio de memoria das solucoes aceitas varia por modelo, dificuldade e linguagem?*\n\n**Nota:** Metricas calculadas apenas sobre submissoes aceitas (Accepted).",
        "rq3.nodata": "Nenhuma submissao aceita para os filtros selecionados.",
        "rq3.oamu_header": "OAMU - Estatisticas Gerais do Uso de Memoria",
        "rq3.hist_header": "Distribuicao do Uso de Memoria",
        "rq3.hist_title": "Distribuicao do Uso de Memoria (Aceitos)",
        "rq3.mud_header": "MUD - Uso de Memoria por Dificuldade",
        "rq3.mud_chart": "Memoria Media por Dificuldade (MUD)",
        "rq3.mum_header": "MUM - Uso de Memoria por Modelo",
        "rq3.mum_chart": "Memoria Media por Modelo (MUM) - ordenado",
        "rq3.mul_header": "MUL - Uso de Memoria por Linguagem",
        "rq3.mul_chart": "Memoria Media por Linguagem (MUL)",
        "rq3.ct_header": "Tabulacoes Cruzadas - Uso de Memoria",
        "rq3.ct_md_title": "**Memoria Media (MB) por Modelo e Dificuldade**",
        "rq3.ct_ml_title": "**Memoria Media (MB) por Modelo e Linguagem**",
        "rq3.ct_ld_title": "**Memoria Media (MB) por Linguagem e Dificuldade**",
        "rq3.hm_md": "Heatmap: Memoria Media (MB) - Modelo x Dificuldade",
        "rq3.hm_ml": "Heatmap: Memoria Media (MB) - Modelo x Linguagem",
        "rq3.box_header": "Distribuicoes (Box Plots)",
        "rq3.box_model_title": "Distribuicao da Memoria por Modelo",
        "rq3.box_lang_title": "Distribuicao da Memoria por Linguagem",
        "rq3.box_diff_title": "Distribuicao da Memoria por Dificuldade",
        "rq3.tradeoff_header": "Trade-off Velocidade x Memoria",
        "rq3.tradeoff_chart": "Trade-off: Tempo Medio x Memoria Media por Linguagem",
        "st.header": "Analise Estatistica",
        "st.desc": "An\u00e1lises inspiradas em Guimaraes et al. (2025): intervalos de Wilson, testes omnibus (ANOVA / Kruskal-Wallis com a regra de decis\u00e3o), post hoc com Holm, GLMM e GEE, atrito, controles de composi\u00e7\u00e3o aceita\u00e7\u00e3o x mem\u00f3ria, proxies de contamina\u00e7\u00e3o e deriva do juiz, seguidos de d de Cohen, gr\u00e1ficos de correla\u00e7\u00e3o e escore composto com os filtros da barra lateral. Tempo e mem\u00f3ria n\u00e3o s\u00e3o normais (Shapiro-Wilk); as conclus\u00f5es seguem o Kruskal-Wallis e a ANOVA \u00e9 mostrada para comparabilidade.",
        "st.no_scipy": "\u26A0\uFE0F Biblioteca `scipy` nao encontrada. Instale com `pip install scipy` para habilitar os testes estatisticos.",
        "st.nodata": "Nenhum dado disponivel.",
        "st.anova_desc": "Limiares de eta squared: **small** (< 0.06), **medium** (0.06-0.14), **large** (> 0.14)",
        "st.cohens_lang_header": "Cohen's d - Comparacoes entre Linguagens",
        "st.cohens_desc": "Limiares: **negligible** (|d| < 0.2), **small** (0.2-0.5), **medium** (0.5-0.8), **large** (> 0.8)",
        "st.cohens_diff_header": "Cohen's d - Comparacoes entre Dificuldades (Aceitacao)",
        "st.corr_viz_header": "Visualizacoes de Correlacao",
        "st.corr_acc_mem": "Aceitacao vs Memoria Media (por modelo)",
        "st.corr_acc_time": "Aceitacao vs Tempo Medio (por modelo)",
        "st.corr_need": "scipy necessario para calculos de correlacao.",
        "st.corr_insuf": "Dados insuficientes.",
        "st.composite_header": "Escore Composto (Trade-off)",
        "st.composite_desc": "Ranking normalizado combinando aceitacao (cima), tempo de execucao (baixo) e memoria (baixo), com pesos iguais. Valores maiores = melhor equilibrio geral.",
        "st.composite_chart": "Escore Composto por Modelo (maior = melhor)",
        "st.rec_header": "Recomendacoes Praticas",
        "st.rec_body": """Com base na an\u00e1lise combinada das tr\u00eas RQs (base final corrigida; tentativa \u00fanica, zero-shot). Os rankings de tempo e mem\u00f3ria por modelo s\u00e3o apenas descritivos: o efeito do modelo sobre o tempo de execu\u00e7\u00e3o \u00e9 pequeno (Kruskal-Wallis significativo) e nenhum par de modelos difere ap\u00f3s a corre\u00e7\u00e3o de Holm.

| Prioridade | Recomenda\u00e7\u00e3o |
|---|---|
| **Maximizar aceita\u00e7\u00e3o** | `kimi-k2-instruct` (85,9%), `qwen3-32b` (79,7%), `deepseek-r1-70b` (71,5%). As tr\u00eas linguagens atingem aceita\u00e7\u00e3o semelhante (C++ 50,3%, Java 51,9%, Python3 52,4%); o efeito da linguagem n\u00e3o \u00e9 significativo na ANOVA e s\u00f3 aparece um efeito pequeno no GLMM conjunto. |
| **Minimizar tempo** | Descritivo: Java (25,4ms) ~ C++ (28,3ms) << Python3 (151,2ms). As m\u00e9dias por modelo (ex.: `qwen3-32b` 40,6ms, `llama3-70b` 45,7ms) n\u00e3o s\u00e3o estatisticamente distingu\u00edveis par a par. |
| **Minimizar mem\u00f3ria** | Python3 (22,4MB) < C++ (29,1MB) < Java (48,0MB). As diferen\u00e7as entre modelos s\u00e3o desprez\u00edveis (1 de 55 pares significativo ap\u00f3s Holm). |
| **Melhor equil\u00edbrio** | Ver a tabela de escore composto acima (descritivo, pesos iguais). |

**Nenhum modelo ou linguagem domina simultaneamente em todas as tr\u00eas m\u00e9tricas.**""",
        "stcol.factor": "Fator",
        "stcol.metric": "Metrica",
        "stcol.acceptance": "Aceitacao",
        "stcol.time": "Tempo (ms)",
        "stcol.memory": "Memoria (MB)",
        "stcol.effect": "Efeito",
        "stcol.pair": "Par",
        "stcol.magnitude": "Magnitude",
        "stcol.trend": "Tendencia",
        "ax.acceptance_pct": "Aceitacao (%)",
        "ax.model": "Modelo",
        "ax.language": "Linguagem",
        "ax.difficulty": "Dificuldade",
        "ax.time_ms": "Tempo (ms)",
        "ax.memory_mb": "Memoria (MB)",
        "ax.count": "Contagem",
        "ax.frequency": "Frequencia",
        "ax.mean_time_ms": "Tempo Medio (ms)",
        "ax.mean_memory_mb": "Memoria Media (MB)",
        "tc.difficulty": "Dificuldade",
        "tc.accepted": "Aceitos",
        "tc.total": "Total",
        "tc.rate_pct": "Taxa%",
        "tc.language": "Linguagem",
        "tc.mean_ms": "Media (ms)",
        "tc.median_ms": "Mediana (ms)",
        "tc.std_ms": "DP (ms)",
        "tc.mean_mb": "Media (MB)",
        "tc.median_mb": "Mediana (MB)",
        "tc.std_mb": "DP (MB)",
        "tc.n": "N",
        "ex.header": "Explorador de Codigo",
        "ex.desc": "Visualize o codigo gerado pelas LLMs e os resultados de submissao no LeetCode.",
        "ex.nodata": "Nenhuma resposta de LLM encontrada em `data/generations/`.",
        "ex.model": "Modelo",
        "ex.language": "Linguagem",
        "ex.problem": "Problema (ID)",
        "ex.code_title": "**Codigo Gerado**",
        "ex.meta_title": "**Metadados da LLM**",
        "ex.category": "Categoria",
        "ex.reason": "Motivo",
        "ex.result_title": "**Resultado no LeetCode**",
        "ex.status": "Status",
        "ex.time": "Tempo",
        "ex.memory": "Memoria",
        "ex.problem_info": "**Info do Problema**",
        "ex.title_field": "Titulo",
        "ex.diff_field": "Dificuldade",
        "ex.topic_field": "Topico",
        "ex.no_result": "Nenhum resultado de submissao encontrado para esta combinacao.",
        "ex.empty_code": "(vazio)",
        "ex.compare_header": "Comparacao Lado a Lado",
        "ex.model_a": "**Modelo A**",
        "ex.model_b": "**Modelo B**",
        "ex.compare_problem": "Problema para comparar",
        "ex.no_common": "Nenhum problema em comum entre as selecoes.",
        "exp.header": "Exportar Dados",
        "exp.desc": "Baixe os dados filtrados em diversos formatos para analises externas.",
        "exp.nodata": "Nenhum dado disponivel.",
        "exp.sub_header": "Dados de Submissao (Filtrados)",
        "exp.record_count": "{n:,} registros com os filtros atuais",
        "exp.showing_500": "Exibindo 500 primeiras linhas. Faca o download para ver todos os dados.",
        "exp.dl_csv_all": "\U0001F4E5 Download CSV (Todas submissoes)",
        "exp.dl_json_all": "\U0001F4E5 Download JSON (Todas submissoes)",
        "exp.dl_csv_acc": "\U0001F4E5 Download CSV (Apenas Aceitos)",
        "exp.tables_header": "Tabelas Resumo para o Artigo",
        "exp.tables_desc": "Tabelas prontas para copiar/colar no paper.",
        "exp.table_oar": "Tabela: Distribuicao geral (OAR)",
        "exp.table_arm_diff": "Tabela: ARM x Dificuldade",
        "exp.table_arm_lang": "Tabela: ARM x Linguagem",
        "exp.table_etm_diff": "Tabela: ETM x Dificuldade",
        "exp.table_etm_lang": "Tabela: ETM x Linguagem",
        "exp.table_mum_diff": "Tabela: MUM x Dificuldade",
        "exp.table_mum_lang": "Tabela: MUM x Linguagem",
        "exp.meta_header": "Metadados dos Problemas",
        "exp.meta_count": "{n} problemas na base de metadados",
        "exp.dl_meta": "\U0001F4E5 Download CSV (Metadados)",
        "ex.code_sent": "**Código enviado ao LeetCode (pipeline corrigido)**",
        "ex.source": "Origem do veredito",
        "ex.src_2025": "Julgado em 2025",
        "ex.src_2026": "Julgado em 2026",
        "st.filtered_header": "Vis\u00f5es explorat\u00f3rias com os filtros da barra lateral",
        "st.filtered_desc": "As se\u00e7\u00f5es abaixo s\u00e3o recalculadas com os filtros atuais da barra lateral (descritivas; os testes acima usam a base completa).",
        "ex.err_compile": "Mensagem de erro de compilação do juiz",
        "ex.err_runtime": "Mensagem de erro de execução do juiz",
        "pp.caption": "As an\u00e1lises do artigo abaixo leem apenas os arquivos pr\u00e9-calculados em `results/statistics/` e `results/glmm/` (gerados por `analysis/statistics.py` e `analysis/glmm.R`). Elas sempre representam a base completa corrigida (10.666 submiss\u00f5es julgadas) e ignoram os filtros da barra lateral.",
        "pp.missing": "Arquivos pré-calculados não encontrados em `results/statistics/` (`numeros.json`). Execute `analysis/statistics.py` antes.",
        "pp.missing_part": "Não disponível nos arquivos pré-calculados.",
        "pp.oar_note": "A aceitação geral é de tentativa única e zero-shot: cada problema é submetido uma vez por modelo e linguagem, sem novas tentativas nem feedback.",
        "pp.oar_metric": "Aceitação geral (IC de Wilson 95%)",
        "pp.oar_n": "Submissões julgadas",
        "pp.a.header": "a. Aceitação com intervalos de confiança de Wilson de 95%",
        "pp.a.desc": "Intervalos de Wilson (z = 1,959964) para cada célula. Cada célula mostra `% [inferior, superior] (k/n)`. Células com menos submissões julgadas que o planejado refletem perdas (ver seção e).",
        "pp.a.marg": "Marginais (dificuldade, linguagem, modelo)",
        "pp.a.note_lang": "As três linguagens atingem aceitação semelhante (C++ 50,3%, Java 51,9%, Python3 52,4%): os intervalos se sobrepõem, a ANOVA não é significativa e só aparece um efeito pequeno no GLMM conjunto (seção d).",
        "pp.b.header": "b. Regra de decisão e testes omnibus",
        "pp.b.desc": "Tempo e memória são fortemente não normais (Shapiro-Wilk, abaixo); portanto as conclusões sobre eles seguem o Kruskal-Wallis (tamanho de efeito epsilon ao quadrado) e a ANOVA de um fator é mostrada apenas para comparabilidade. A aceitação (binária) é testada com qui-quadrado de proporções, com o eta ao quadrado do indicador 0/1 como tamanho de efeito. Quando ANOVA e Kruskal-Wallis divergem (ex.: efeito do modelo sobre o tempo), vale o Kruskal-Wallis.",
        "pp.b.shapiro": "Testes de normalidade de Shapiro-Wilk (submissões aceitas)",
        "pp.b.note_time": "Efeito do modelo sobre o tempo de execução: Kruskal-Wallis significativo, porém pequeno, e nenhum par de modelos é significativo após Holm; os rankings de tempo e memória por modelo são, portanto, descritivos.",
        "pp.c.header": "c. Comparações post hoc (correção de Holm)",
        "pp.c.desc": "Comparações par a par: teste de Dunn para tempo e memória, testes de proporções para aceitação, todos com ajuste de Holm. Contagem de pares significativos (p ajustado < 0,05):",
        "pp.c.table": "Resultados par a par (`posthoc.csv`)",
        "pp.c.only_sig": "Somente pares significativos (p Holm < 0,05)",
        "pp.d.header": "d. Modelo conjunto (GLMM, glmmTMB) e robustez (GEE)",
        "pp.d.desc": "GLMM binomial da aceitação com efeitos fixos de modelo, linguagem e dificuldade e intercepto aleatório por problema (336 problemas), ajustado com glmmTMB. Razões de chances (OR) com IC de 95%.",
        "pp.d.ref": "Níveis de referência: modelo `{m}`, linguagem C++, dificuldade Easy.",
        "pp.d.or": "Razões de chances (GLMM)",
        "pp.d.lrt_f": "Testes de razão de verossimilhança: efeitos principais",
        "pp.d.lrt_i": "Testes de razão de verossimilhança: interações",
        "pp.d.summary": "Resumo do modelo (`glmm_resumo.txt`)",
        "pp.d.gee": "Robustez: OR do GEE (agrupado por problema, `numeros.json`)",
        "pp.d.lang_note": "No modelo conjunto o efeito da linguagem é pequeno porém significativo (Java e Python3 ligeiramente acima de C++), embora a ANOVA de um fator para linguagem não seja significativa.",
        "pp.e.header": "e. Perdas por dificuldade (limites)",
        "pp.e.desc": "Algumas gerações planejadas não foram julgadas (saídas truncadas ou incompletas). A taxa entre as submissões julgadas fica entre um limite inferior (toda submissão ausente teria falhado) e um limite superior (toda ausente teria sido aceita).",
        "pp.f.header": "f. Correlação aceitação x memória com controles de composição",
        "pp.f.desc": "Correlações no nível de modelo (N = 11 modelos; N = 10 sem o allam-2-7b) entre aceitação e memória/tempo, com três controles: médias brutas, memória/tempo relativos ao nível do problema e apenas os pares problema-linguagem aceitos por todos os modelos.",
        "pp.f.note": "Interpretação: a associação positiva bruta entre aceitação e memória é composicional, não causal. Modelos que resolvem mais problemas têm soluções aceitas também em problemas mais difíceis, que usam mais memória; ao controlar a composição (memória relativa, ou apenas problemas resolvidos por todos) ela deixa de ser significativa (e fica negativa nos problemas comuns). Não deve ser lida como 'modelos corretos escrevem código mais intensivo em memória'.",
        "pp.g.header": "g. Proxies de contaminação",
        "pp.g.desc": "Aceitação por problema (agregada em modelos e linguagens) contra o ID da questão (problemas antigos têm IDs menores), o número global de submissões do problema no LeetCode (popularidade) e a taxa de aceitação humana do LeetCode. As OR do GEE ajustam por modelo, linguagem e dificuldade (preditores padronizados).",
        "pp.g.note": "Ressalva: esses proxies não separam memorização dos dados de treino de popularidade (problemas populares também têm mais soluções públicas, comentários e discussões). São consistentes com contaminação, mas não a comprovam.",
        "pp.h.header": "h. Controle de deriva do juiz",
        "pp.h.desc": "Para verificar que o juiz do LeetCode não mudou entre 2025 e o rejulgamento de 2026, {n} submissões inalteradas foram julgadas novamente como controles.",
        "pp.h.note": "Todos os vereditos são idênticos. O tempo de execução não mudou (Wilcoxon não significativo), mas as leituras de memória são ligeiramente maiores em 2026 (razão média {r:.2f}, razão mediana {mr:.2f}); a memória das rejulgadas deve ser interpretada com essa ressalva.",
        "pp.col.cell": "Célula",
        "pp.col.k": "Aceitas (k)",
        "pp.col.n": "Julgadas (n)",
        "pp.col.pct": "Aceitação (%)",
        "pp.col.lo": "Inferior 95%",
        "pp.col.hi": "Superior 95%",
        "pp.col.test": "Teste",
        "pp.col.stat": "qui2 / H",
        "pp.col.df": "gl",
        "pp.col.p": "p",
        "pp.col.p_holm": "p (Holm)",
        "pp.col.effect": "Efeito",
        "pp.col.effect_val": "Tamanho do efeito",
        "pp.col.pairs": "Pares significativos",
        "pp.col.total": "Pares",
        "pp.col.sig": "Significativos",
        "pp.col.term": "Termo",
        "pp.col.or": "OR",
        "pp.col.ci": "IC 95%",
        "pp.col.chisq": "qui2",
        "pp.col.planned": "Planejadas",
        "pp.col.missing": "Ausentes",
        "pp.col.rate": "Taxa entre julgadas (%)",
        "pp.col.lower": "Limite inferior (%)",
        "pp.col.upper": "Limite superior (%)",
        "pp.col.control": "Controle",
        "pp.col.pair": "Par",
        "pp.col.proxy": "Proxy",
        "pp.col.rho": "rho de Spearman",
        "pp.col.value": "Valor",
        "pp.col.metric": "Métrica",
        "pp.col.estat": "Estatística",
        "pp.col.a": "A",
        "pp.col.b": "B",
        "pp.ctl.raw": "Nenhum (médias por modelo)",
        "pp.ctl.rel": "Relativo ao nível do problema",
        "pp.ctl.all": "Problemas resolvidos pelos 11 modelos",
        "pp.ctl.noallam": "Problemas resolvidos por todos exceto allam-2-7b",
        "pp.pair.acc_mem": "Aceitação x memória",
        "pp.pair.acc_time": "Aceitação x tempo",
        "pp.pair.time_mem": "Tempo x memória",
        "pp.proxy.id": "ID da questão",
        "pp.proxy.n_subm": "Submissões globais (popularidade)",
        "pp.proxy.humana": "Taxa de aceitação humana (LeetCode)",
        "pp.h.same": "Mesmo veredito",
        "pp.h.accepted": "Controles aceitos",
        "pp.h.time_med": "Diferença mediana de tempo (ms)",
        "pp.h.time_p": "Tempo: p de Wilcoxon",
        "pp.h.mem_mean": "Memória: razão média (2026/2025)",
        "pp.h.mem_med": "Memória: razão mediana",
        "pp.h.mem_p": "Memória: p de Wilcoxon",
    },
}


def t(key: str) -> str:
    """Get translated string for the current language."""
    lang = st.session_state.get("ui_lang", "en")
    return UI[lang].get(key, key)


# ==================================================================
# DATA LOADING
# ==================================================================
@st.cache_data(show_spinner="Loading / Carregando...")
def load_results(csv_path: str = str(RESULTS_CSV_FINAL)) -> pd.DataFrame:
    """Load submission results from csv_path (default data/results.csv)."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path, encoding="utf-8", low_memory=False)

    if df.empty:
        return df

    # Normalize columns
    df["tempo_ms"] = pd.to_numeric(df.get("tempo_ms"), errors="coerce")
    df["memoria_mb"] = pd.to_numeric(df.get("memoria_mb"), errors="coerce")
    if "aceito" in df.columns:
        df["aceito"] = df["aceito"].map(
            lambda v: True if str(v).strip().lower() in ("true", "1", "yes") else False
        )
    if "id_questao" in df.columns:
        df["id_questao"] = pd.to_numeric(df["id_questao"], errors="coerce")

    # Short model name
    df["model_short"] = df["modelo"].map(lambda m: MODEL_SHORT.get(str(m).strip(), str(m).strip()))

    # Paper 3-category status
    def paper_status(row):
        s = str(row.get("status", "")).strip()
        if s == "Accepted":
            return "Accepted"
        if "Compile" in s or "Compilation" in s:
            return "Compilation Error"
        return "Wrong Answer"

    df["status_paper"] = df.apply(paper_status, axis=1)
    df["status_detail"] = df["status"].astype(str).str.strip()

    return df


@st.cache_data(show_spinner="Loading / Carregando...")
def load_problem_metadata() -> pd.DataFrame:
    """Load problem metadata from data/problems/{easy,medium,hard}.json."""
    rows = []
    for fname in ["easy.json", "medium.json", "hard.json"]:
        fpath = DATASETS / fname
        if not fpath.exists():
            continue
        try:
            problems = json.load(open(fpath, "r", encoding="utf-8"))
            for p in problems:
                diff_pt = str(p.get("dificuldade", ""))
                diff_en = DIFF_PT_EN.get(diff_pt, diff_pt)
                rows.append({
                    "problem_id": p.get("id"),
                    "slug": p.get("slug", ""),
                    "titulo": p.get("titulo", ""),
                    "difficulty": diff_en,
                    "tema_principal": p.get("tema_principal", ""),
                    "temas": p.get("temas", []),
                    "has_image": p.get("has_image", False),
                })
        except Exception:
            continue
    return pd.DataFrame(rows)


@st.cache_data(show_spinner="Loading / Carregando...")
def load_llm_answers() -> pd.DataFrame:
    """Load LLM-generated code from data/generations/<model>/<language>/<id>.json."""
    rows = []
    if not LLM_DATA.exists():
        return pd.DataFrame()
    for model_dir in sorted(LLM_DATA.iterdir()):
        if not model_dir.is_dir():
            continue
        for lang_dir in model_dir.iterdir():
            if not lang_dir.is_dir():
                continue
            for jf in lang_dir.glob("*.json"):
                try:
                    obj = json.load(open(jf, "r", encoding="utf-8"))
                    rows.append({
                        "modelo": model_dir.name,
                        "linguagem": lang_dir.name,
                        "problem_id": obj.get("id"),
                        "code": obj.get("code", ""),
                        "resposta": obj.get("resposta", ""),
                        "categoria": obj.get("categoria", ""),
                        "motivo": obj.get("motivo", ""),
                        "timestamp": obj.get("timestamp", ""),
                    })
                except Exception:
                    continue
    df_out = pd.DataFrame(rows)
    if not df_out.empty:
        df_out["problem_id"] = pd.to_numeric(df_out["problem_id"], errors="coerce")
    return df_out


@st.cache_data(show_spinner=False)
def load_judge_errors(fonte: str, modelo: str, linguagem: str) -> Dict[int, Dict[str, str]]:
    """Judge error messages (compile/runtime) keyed by problem id.
    fonte == "2026" -> data/rejudging_2026/rejudged.ndjson; otherwise the 2025 records
    in data/submissions/<model>__<language>.ndjson."""
    out: Dict[int, Dict[str, str]] = {}
    norm = lambda m: str(m).replace("/", "_").strip()
    if fonte == "2026":
        path, id_key = REJUDGED_2026, "id"
    else:
        path, id_key = SUBMISSIONS_2025 / f"{norm(modelo)}__{linguagem}.ndjson", "id_questao"
    if not path.exists():
        return out
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if fonte == "2026" and (norm(rec.get("modelo")) != norm(modelo) or rec.get("linguagem") != linguagem):
                continue
            try:
                pid = int(rec.get(id_key))
            except (TypeError, ValueError):
                continue
            out[pid] = {"erro_compilacao": rec.get("erro_compilacao") or "",
                        "erro_runtime": rec.get("erro_runtime") or ""}
    return out


def merge_difficulty(df_results: pd.DataFrame, df_meta: pd.DataFrame) -> pd.DataFrame:
    """Merge difficulty info into results."""
    if df_meta.empty or df_results.empty:
        return df_results

    slug_diff = df_meta.set_index("slug")["difficulty"].to_dict()
    id_diff = df_meta.set_index("problem_id")["difficulty"].to_dict()
    slug_tema = df_meta.set_index("slug")["tema_principal"].to_dict()
    id_tema = df_meta.set_index("problem_id")["tema_principal"].to_dict()
    slug_titulo = df_meta.set_index("slug")["titulo"].to_dict()

    df = df_results.copy()
    df["difficulty"] = df["slug"].map(slug_diff)
    mask = df["difficulty"].isna()
    if mask.any() and "id_questao" in df.columns:
        df.loc[mask, "difficulty"] = df.loc[mask, "id_questao"].map(id_diff)

    df["tema_principal"] = df["slug"].map(slug_tema)
    mask2 = df["tema_principal"].isna()
    if mask2.any() and "id_questao" in df.columns:
        df.loc[mask2, "tema_principal"] = df.loc[mask2, "id_questao"].map(id_tema)

    df["titulo"] = df["slug"].map(slug_titulo)
    df["difficulty"] = pd.Categorical(df["difficulty"], categories=DIFF_ORDER, ordered=True)

    return df


# ==================================================================
# STATISTICAL HELPERS
# ==================================================================
def compute_eta_squared(f_stat, df_between, df_within):
    return (f_stat * df_between) / (f_stat * df_between + df_within)


def compute_cohens_d(group1, group2):
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return np.nan
    m1, m2 = np.mean(group1), np.mean(group2)
    s1, s2 = np.std(group1, ddof=1), np.std(group2, ddof=1)
    pooled = np.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
    return (m1 - m2) / pooled if pooled > 0 else np.nan


def run_anova(df, group_col, value_col):
    groups = [g[value_col].dropna().values for _, g in df.groupby(group_col) if len(g[value_col].dropna()) > 0]
    if len(groups) < 2:
        return np.nan, np.nan, np.nan
    if HAS_SCIPY:
        f_stat, p_val = sp_stats.f_oneway(*groups)
        k = len(groups)
        n = sum(len(g) for g in groups)
        eta2 = compute_eta_squared(f_stat, k - 1, n - k)
        return f_stat, p_val, eta2
    return np.nan, np.nan, np.nan


def run_kruskal(df, group_col, value_col):
    groups = [g[value_col].dropna().values for _, g in df.groupby(group_col) if len(g[value_col].dropna()) > 0]
    if len(groups) < 2 or not HAS_SCIPY:
        return np.nan, np.nan
    h_stat, p_val = sp_stats.kruskal(*groups)
    return h_stat, p_val


def effect_label(eta2):
    if pd.isna(eta2):
        return "n.s."
    if eta2 < 0.06:
        return "small"
    if eta2 < 0.14:
        return "medium"
    return "large"


# ==================================================================
# PAPER ANALYSES HELPERS (precomputed files only)
# ==================================================================
def wilson_ci(k, n, z: float = 1.959964):
    """Wilson score interval in percent (same formula as analysis/statistics.py)."""
    if not n:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (100 * (centre - half), 100 * (centre + half))


def _msh(name) -> str:
    """Short model name; accepts 'org/model' and 'org_model' spellings."""
    name = str(name)
    return MODEL_SHORT.get(name.replace("/", "_"), MODEL_SHORT.get(name, name))


def fmt_p(p) -> str:
    try:
        p = float(p)
    except (TypeError, ValueError):
        return "-"
    if np.isnan(p):
        return "-"
    if p == 0:
        return "<1e-300"
    return f"{p:.3f}" if p >= 0.001 else f"{p:.1e}"


@st.cache_data(show_spinner=False)
def load_paper_files() -> Dict[str, Any]:
    """Read ONLY the precomputed analysis files (results/statistics, results/glmm)."""
    out: Dict[str, Any] = {"num": {}, "posthoc": pd.DataFrame(), "glmm_or": pd.DataFrame(),
                           "lrt_f": pd.DataFrame(), "lrt_i": pd.DataFrame(), "resumo": ""}
    try:
        with open(STATS_DIR / "numeros.json", "r", encoding="utf-8") as fh:
            out["num"] = json.load(fh)
    except Exception:
        pass
    for key, path in (("posthoc", STATS_DIR / "posthoc.csv"), ("glmm_or", GLMM_DIR / "glmm_or.csv"),
                      ("lrt_f", GLMM_DIR / "glmm_lrt_fatores.csv"), ("lrt_i", GLMM_DIR / "glmm_lrt_interacoes.csv")):
        try:
            out[key] = pd.read_csv(path, encoding="utf-8")
        except Exception:
            pass
    try:
        out["resumo"] = (GLMM_DIR / "glmm_resumo.txt").read_text(encoding="utf-8")
    except Exception:
        pass
    return out


def ci_table(d, two_level: bool, row_name: str, col_name: str) -> pd.DataFrame:
    """Flatten numeros.json acceptance dicts to rows with Wilson CIs (computed here if not stored)."""
    rows = []
    for r, v in (d or {}).items():
        sub = list(v.items()) if two_level else [("", v)]
        for c, cell in sub:
            k, n = cell.get("k"), cell.get("n")
            pct = cell.get("pct", (100 * k / n) if n else np.nan)
            lo, hi = cell.get("lo"), cell.get("hi")
            if (lo is None or hi is None) and n:
                lo, hi = wilson_ci(k, n)
            rows.append({row_name: _msh(r), col_name: c, "k": k, "n": n, "pct": pct, "lo": lo, "hi": hi})
    return pd.DataFrame(rows)


def ci_wide(d: pd.DataFrame, row_name: str, col_name: str, col_order: List[str]) -> pd.DataFrame:
    d = d.copy()
    d["txt"] = d.apply(lambda r: f"{r['pct']:.1f}% [{r['lo']:.1f}, {r['hi']:.1f}] ({int(r['k'])}/{int(r['n'])})", axis=1)
    wide = d.pivot(index=row_name, columns=col_name, values="txt")
    wide = wide[[c for c in col_order if c in wide.columns]]
    order = d.drop_duplicates(row_name)[row_name].tolist()
    return wide.loc[[r for r in order if r in wide.index]].reset_index()


def clean_term(term: str) -> str:
    """Readable names for GLMM / GEE coefficient labels."""
    term = str(term)
    m = re.match(r"C\((\w+)\)\[T\.(.*)\]$", term)
    if m:
        var, lvl = m.group(1), m.group(2)
        pref = {"modelo_tex": "modelo", "linguagem": "linguagem", "dif": "dif"}.get(var, var)
        term = pref + lvl
    if term.startswith("modelo"):
        return f"Model: {_msh(term[len('modelo'):])}"
    if term.startswith("linguagem"):
        return f"Language: {term[len('linguagem'):]}"
    if term.startswith("dif"):
        return f"Difficulty: {term[len('dif'):]}"
    return {"(Intercept)": "Intercept", "Intercept": "Intercept"}.get(term, term)


def or_table(df_or: pd.DataFrame, term_col: str, or_col: str = "OR", lo: str = "lo", hi: str = "hi", p: str = "p") -> pd.DataFrame:
    return pd.DataFrame({
        t("pp.col.term"): df_or[term_col].map(clean_term),
        t("pp.col.or"): df_or[or_col].map(lambda v: f"{v:.3g}"),
        t("pp.col.ci"): df_or.apply(lambda r: f"[{r[lo]:.3g}, {r[hi]:.3g}]", axis=1),
        t("pp.col.p"): df_or[p].map(fmt_p),
    })


def ref_model(model_terms: List[str], all_models: List[str]) -> str:
    present = {_msh(x) for x in model_terms}
    ref = [m for m in all_models if _msh(m) not in present]
    return _msh(ref[0]) if ref else "-"


# ==================================================================
# LOAD DATA
# ==================================================================
with st.sidebar:
    # Language selector first, so every label below is translated in the same run
    lang_choice = st.selectbox(
        "\U0001F310 Language / Idioma",
        ["English", "Portugues (Brasil)"],
        index=0,
        key="lang_select",
    )
    st.session_state["ui_lang"] = "pt" if lang_choice.startswith("Portugu") else "en"

df_raw = load_results(str(RESULTS_CSV_FINAL))
df_meta = load_problem_metadata()
df_llm = load_llm_answers()

if not df_raw.empty and not df_meta.empty:
    df_all = merge_difficulty(df_raw, df_meta)
else:
    df_all = df_raw.copy() if not df_raw.empty else pd.DataFrame()

if not df_all.empty:
    df_accepted = df_all[df_all["status_paper"] == "Accepted"].copy()
else:
    df_accepted = pd.DataFrame()


# ==================================================================
# SIDEBAR - Language Selector + Global Filters
# ==================================================================
with st.sidebar:
    st.title(t("sidebar.title"))
    st.caption(t("sidebar.caption"))

    if not df_all.empty:
        all_models = sorted(df_all["model_short"].dropna().unique().tolist())
        sel_models = st.multiselect(t("sidebar.models"), all_models, default=all_models)

        sel_langs = st.multiselect(t("sidebar.langs"), LANG_ORDER,
                                   default=[l for l in LANG_ORDER if l in df_all["linguagem"].unique()])

        available_diffs = [d for d in DIFF_ORDER if d in df_all["difficulty"].dropna().unique()]
        sel_diffs = st.multiselect(t("sidebar.difficulty"), available_diffs, default=available_diffs)

        st.markdown("---")
        st.caption(t("sidebar.cache"))
        if st.button(t("sidebar.clear_cache")):
            st.cache_data.clear()
            st.rerun()
    else:
        sel_models, sel_langs, sel_diffs = [], [], []

# Apply filters
if not df_all.empty:
    mask = (
        df_all["model_short"].isin(sel_models) &
        df_all["linguagem"].isin(sel_langs) &
        (df_all["difficulty"].isin(sel_diffs) | df_all["difficulty"].isna())
    )
    df = df_all[mask].copy()
    df_acc = df[df["status_paper"] == "Accepted"].copy()
else:
    df = pd.DataFrame()
    df_acc = pd.DataFrame()


# ==================================================================
# MAIN UI
# ==================================================================
st.title(t("main.title"))
st.caption(t("main.caption"))

if df_all.empty:
    st.error(t("main.nodata"))
    st.stop()

tab_overview, tab_rq1, tab_rq2, tab_rq3, tab_stats, tab_explorer, tab_export = st.tabs([
    t("tab.overview"), t("tab.rq1"), t("tab.rq2"), t("tab.rq3"),
    t("tab.stats"), t("tab.explorer"), t("tab.export"),
])

# ==================================================================
# TAB 1: OVERVIEW
# ==================================================================
with tab_overview:
    st.header(t("ov.header"))
    st.markdown(t("ov.desc"))

    total_judged = len(df)
    total_accepted = len(df_acc)
    oar = (total_accepted / total_judged * 100) if total_judged > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("ov.total_subs"), f"{total_judged:,}")
    col2.metric(t("ov.oar"), f"{oar:.1f}%")
    col3.metric(t("ov.avg_time"), f"{df_acc['tempo_ms'].mean():.1f} ms" if not df_acc.empty else "-")
    col4.metric(t("ov.avg_mem"), f"{df_acc['memoria_mb'].mean():.1f} MB" if not df_acc.empty else "-")

    # Incomplete generations
    st.subheader(t("ov.incomplete_header"))
    st.markdown(t("ov.incomplete_desc"))

    incomplete_data = []
    for model_full, model_short in MODEL_SHORT.items():
        count = len(df_all[df_all["modelo"] == model_full])
        missing = EXPECTED_PER_MODEL - count
        incomplete_data.append({
            t("col.model"): model_short,
            t("col.expected"): EXPECTED_PER_MODEL,
            t("col.submitted"): count,
            t("col.missing"): max(0, missing),
        })
    df_incomplete = pd.DataFrame(incomplete_data).sort_values(t("col.missing"), ascending=False)
    total_submitted = df_incomplete[t("col.submitted")].sum()
    total_missing = TOTAL_EXPECTED - total_submitted

    c1, c2 = st.columns(2)
    c1.metric(t("ov.total_expected"), f"{TOTAL_EXPECTED:,}")
    c2.metric(t("ov.total_sub_missing"), f"{total_submitted:,} / {max(0, total_missing):,}")

    st.dataframe(df_incomplete, use_container_width=True, hide_index=True)

    # Overall outcome distribution
    st.subheader(t("ov.dist_header"))
    c1, c2 = st.columns([1, 1])
    with c1:
        status_counts = df["status_paper"].value_counts()
        fig = px.pie(
            names=status_counts.index,
            values=status_counts.values,
            hole=0.42,
            color=status_counts.index,
            color_discrete_map=COLORS_STATUS,
            title=t("ov.pie_title"),
        )
        fig.update_traces(textposition="inside", textinfo="percent+label+value")
        fig.update_layout(height=400, margin=dict(t=60, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown(t("ov.table_3cat"))
        summary_3cat = pd.DataFrame({
            t("col.result"): ["Accepted", "Compilation Error", "Wrong Answer"],
            t("col.count"): [
                len(df[df["status_paper"] == "Accepted"]),
                len(df[df["status_paper"] == "Compilation Error"]),
                len(df[df["status_paper"] == "Wrong Answer"]),
            ],
        })
        summary_3cat["%"] = (summary_3cat[t("col.count")] / summary_3cat[t("col.count")].sum() * 100).round(1)
        st.dataframe(summary_3cat, use_container_width=True, hide_index=True)

        st.markdown(t("ov.table_granular"))
        detail_counts = df["status_detail"].value_counts().reset_index()
        detail_counts.columns = [t("col.status"), t("col.count")]
        detail_counts["%"] = (detail_counts[t("col.count")] / detail_counts[t("col.count")].sum() * 100).round(1)
        st.dataframe(detail_counts, use_container_width=True, hide_index=True)

    # Sample composition
    st.subheader(t("ov.sample_header"))
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(t("ov.by_diff"))
        diff_comp = df_all.drop_duplicates("slug").groupby("difficulty", observed=True).size().reset_index(name=t("col.problems"))
        st.dataframe(diff_comp, use_container_width=True, hide_index=True)
    with c2:
        st.markdown(t("ov.models_eval"))
        st.dataframe(
            pd.DataFrame({t("col.model"): sorted(MODEL_SHORT.values())}),
            use_container_width=True, hide_index=True,
        )
    with c3:
        st.markdown(t("ov.by_lang"))
        lang_comp = df_all.groupby("linguagem").size().reset_index(name=t("col.submissions"))
        st.dataframe(lang_comp, use_container_width=True, hide_index=True)

    # Topic distribution
    if "tema_principal" in df_all.columns and df_all["tema_principal"].notna().any():
        st.subheader(t("ov.topic_header"))
        topic_dist = (
            df_all.drop_duplicates("slug")
            .groupby("tema_principal").size()
            .sort_values(ascending=False)
            .reset_index(name=t("col.problems"))
        )
        topic_dist.columns = [t("col.topic"), t("col.problems")]
        fig = px.bar(topic_dist, x=t("col.topic"), y=t("col.problems"),
                     title=t("ov.topic_chart"), height=400)
        fig.update_xaxes(tickangle=-40)
        fig.update_layout(margin=dict(t=60, b=120))
        st.plotly_chart(fig, use_container_width=True)


# ==================================================================
# TAB 2: RQ1 - ACCEPTANCE RATES
# ==================================================================
with tab_rq1:
    st.header(t("rq1.header"))
    st.markdown(t("rq1.desc"))

    if df.empty:
        st.warning(t("rq1.nodata"))
    else:
        df["is_accepted"] = (df["status_paper"] == "Accepted").astype(int)

        # ARD
        st.subheader(t("rq1.ard_header"))
        ard = df.groupby("difficulty", observed=True)["is_accepted"].agg(["mean", "sum", "count"]).reset_index()
        ard.columns = [t("tc.difficulty"), "Taxa", t("tc.accepted"), t("tc.total")]
        ard[t("tc.rate_pct")] = (ard["Taxa"] * 100).round(1)

        c1, c2 = st.columns([2, 1])
        with c1:
            fig = px.bar(ard, x=t("tc.difficulty"), y=t("tc.rate_pct"), text=t("tc.rate_pct"),
                         color=t("tc.difficulty"), color_discrete_map=COLORS_DIFF,
                         title=t("rq1.ard_chart"),
                         labels={t("tc.rate_pct"): t("ax.acceptance_pct")}, height=400)
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False)
            fig.update_layout(showlegend=False, yaxis_range=[0, max(ard[t("tc.rate_pct")]) * 1.15])
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.dataframe(ard[[t("tc.difficulty"), t("tc.accepted"), t("tc.total"), t("tc.rate_pct")]],
                         use_container_width=True, hide_index=True)

        # ARM
        st.subheader(t("rq1.arm_header"))
        arm = df.groupby("model_short")["is_accepted"].agg(["mean", "sum", "count"]).reset_index()
        arm.columns = [t("col.model"), "Taxa", t("tc.accepted"), t("tc.total")]
        arm[t("tc.rate_pct")] = (arm["Taxa"] * 100).round(1)
        arm = arm.sort_values(t("tc.rate_pct"), ascending=False)

        fig = px.bar(arm, x=t("col.model"), y=t("tc.rate_pct"), text=t("tc.rate_pct"),
                     title=t("rq1.arm_chart"),
                     labels={t("tc.rate_pct"): t("ax.acceptance_pct"), t("col.model"): t("ax.model")},
                     height=480, color_discrete_sequence=["#636EFA"])
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False)
        fig.update_xaxes(tickangle=-35)
        fig.update_layout(yaxis_range=[0, max(arm[t("tc.rate_pct")]) * 1.12])
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(arm[[t("col.model"), t("tc.accepted"), t("tc.total"), t("tc.rate_pct")]],
                     use_container_width=True, hide_index=True)

        # ARL
        st.subheader(t("rq1.arl_header"))
        arl = df.groupby("linguagem")["is_accepted"].agg(["mean", "sum", "count"]).reset_index()
        arl.columns = [t("tc.language"), "Taxa", t("tc.accepted"), t("tc.total")]
        arl[t("tc.rate_pct")] = (arl["Taxa"] * 100).round(1)

        c1, c2 = st.columns([2, 1])
        with c1:
            fig = px.bar(arl, x=t("tc.language"), y=t("tc.rate_pct"), text=t("tc.rate_pct"),
                         color=t("tc.language"), color_discrete_map=COLORS_LANG,
                         title=t("rq1.arl_chart"),
                         labels={t("tc.rate_pct"): t("ax.acceptance_pct")}, height=400)
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False)
            fig.update_layout(showlegend=False, yaxis_range=[0, max(arl[t("tc.rate_pct")]) * 1.15])
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.dataframe(arl[[t("tc.language"), t("tc.accepted"), t("tc.total"), t("tc.rate_pct")]],
                         use_container_width=True, hide_index=True)

        # Cross-tabs
        st.subheader(t("rq1.crosstabs"))
        ct1, ct2, ct3 = st.tabs([t("rq1.ct_md"), t("rq1.ct_ml"), t("rq1.ct_ld")])

        with ct1:
            st.markdown(t("rq1.ct_md_title"))
            ct_md = df.pivot_table(index="model_short", columns="difficulty",
                                   values="is_accepted", aggfunc="mean").multiply(100)
            ct_md = ct_md.reindex(columns=[d for d in DIFF_ORDER if d in ct_md.columns])
            st.dataframe(ct_md.round(1).style.format("{:.1f}"), use_container_width=True)

            fig = px.imshow(ct_md.values, x=ct_md.columns.tolist(), y=ct_md.index.tolist(),
                            text_auto=".1f", aspect="auto",
                            color_continuous_scale="YlGn",
                            title=t("rq1.hm_md"),
                            labels=dict(x=t("ax.difficulty"), y=t("ax.model"), color=t("ax.acceptance_pct")))
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

        with ct2:
            st.markdown(t("rq1.ct_ml_title"))
            ct_ml = df.pivot_table(index="model_short", columns="linguagem",
                                   values="is_accepted", aggfunc="mean").multiply(100)
            ct_ml = ct_ml.reindex(columns=[l for l in LANG_ORDER if l in ct_ml.columns])
            st.dataframe(ct_ml.round(1).style.format("{:.1f}"), use_container_width=True)

            fig = px.imshow(ct_ml.values, x=ct_ml.columns.tolist(), y=ct_ml.index.tolist(),
                            text_auto=".1f", aspect="auto",
                            color_continuous_scale="YlGn",
                            title=t("rq1.hm_ml"),
                            labels=dict(x=t("ax.language"), y=t("ax.model"), color=t("ax.acceptance_pct")))
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

        with ct3:
            st.markdown(t("rq1.ct_ld_title"))
            ct_ld = df.pivot_table(index="linguagem", columns="difficulty",
                                   values="is_accepted", aggfunc="mean").multiply(100)
            ct_ld = ct_ld.reindex(columns=[d for d in DIFF_ORDER if d in ct_ld.columns])
            ct_ld = ct_ld.reindex([l for l in LANG_ORDER if l in ct_ld.index])
            st.dataframe(ct_ld.round(1).style.format("{:.1f}"), use_container_width=True)

        # Failure-mode distribution
        st.subheader(t("rq1.fail_header"))
        fail_dist = df.groupby(["model_short", "status_paper"]).size().reset_index(name="count")
        fail_piv = fail_dist.pivot_table(index="model_short", columns="status_paper", values="count", fill_value=0)
        fail_piv["Total"] = fail_piv.sum(axis=1)
        for col in ["Accepted", "Compilation Error", "Wrong Answer"]:
            if col in fail_piv.columns:
                fail_piv[f"{col} (%)"] = (fail_piv[col] / fail_piv["Total"] * 100).round(1)
        st.dataframe(fail_piv, use_container_width=True)

        fig = px.bar(fail_dist, x="model_short", y="count", color="status_paper",
                     color_discrete_map=COLORS_STATUS,
                     title=t("rq1.fail_stacked"),
                     labels={"count": t("ax.count"), "model_short": t("ax.model"), "status_paper": t("col.status")},
                     height=480)
        fig.update_xaxes(tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander(t("rq1.fail_granular")):
            detail_dist = df.groupby(["model_short", "status_detail"]).size().reset_index(name="count")
            detail_piv = detail_dist.pivot_table(index="model_short", columns="status_detail", values="count", fill_value=0)
            st.dataframe(detail_piv, use_container_width=True)

        with st.expander(t("rq1.byq_header")):
            qperf = df.groupby(["slug", "titulo"])["is_accepted"].mean().multiply(100).reset_index()
            qperf.columns = ["slug", "titulo", t("tc.rate_pct")]
            qperf = qperf.sort_values(t("tc.rate_pct"), ascending=True)
            fig = px.bar(qperf, y="titulo", x=t("tc.rate_pct"), orientation="h",
                         title=t("rq1.byq_chart"),
                         labels={t("tc.rate_pct"): t("ax.acceptance_pct"), "titulo": ""},
                         height=max(400, 22 * len(qperf) + 80))
            fig.update_traces(texttemplate="%{x:.1f}%", textposition="outside", cliponaxis=False)
            fig.update_layout(margin=dict(l=250))
            st.plotly_chart(fig, use_container_width=True)


# ==================================================================
# TAB 3: RQ2 - EXECUTION TIME
# ==================================================================
with tab_rq2:
    st.header(t("rq2.header"))
    st.markdown(t("rq2.desc"))

    if df_acc.empty:
        st.warning(t("rq2.nodata"))
    else:
        n_acc = len(df_acc)

        # OAET summary
        st.subheader(t("rq2.oaet_header"))
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric(t("rq2.mean"), f"{df_acc['tempo_ms'].mean():.1f} ms")
        c2.metric(t("rq2.median"), f"{df_acc['tempo_ms'].median():.1f} ms")
        c3.metric(t("rq2.std"), f"{df_acc['tempo_ms'].std():.1f} ms")
        c4.metric(t("rq2.p99"), f"{df_acc['tempo_ms'].quantile(0.99):.1f} ms")
        c5.metric(t("rq2.max"), f"{df_acc['tempo_ms'].max():.1f} ms")
        st.caption(t("rq2.based_on").format(n=n_acc))

        with st.expander(t("rq2.hist_header")):
            fig = px.histogram(df_acc, x="tempo_ms", nbins=100,
                               title=t("rq2.hist_title"),
                               labels={"tempo_ms": t("ax.time_ms"), "count": t("ax.frequency")},
                               height=350)
            fig.update_layout(margin=dict(t=50, b=40))
            st.plotly_chart(fig, use_container_width=True)

        # ETD
        st.subheader(t("rq2.etd_header"))
        etd = df_acc.groupby("difficulty", observed=True)["tempo_ms"].agg(["mean", "median", "std", "count"]).reset_index()
        etd.columns = [t("tc.difficulty"), t("tc.mean_ms"), t("tc.median_ms"), t("tc.std_ms"), t("tc.n")]
        etd = etd.sort_values(t("tc.difficulty"))

        c1, c2 = st.columns([2, 1])
        with c1:
            fig = px.bar(etd, x=t("tc.difficulty"), y=t("tc.mean_ms"), text=t("tc.mean_ms"),
                         color=t("tc.difficulty"), color_discrete_map=COLORS_DIFF,
                         title=t("rq2.etd_chart"), height=400)
            fig.update_traces(texttemplate="%{text:.1f}", textposition="outside", cliponaxis=False)
            fig.update_layout(showlegend=False, yaxis_range=[0, max(etd[t("tc.mean_ms")]) * 1.15])
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.dataframe(etd.round(1), use_container_width=True, hide_index=True)

        # ETM
        st.subheader(t("rq2.etm_header"))
        etm = df_acc.groupby("model_short")["tempo_ms"].agg(["mean", "median", "std", "count"]).reset_index()
        etm.columns = [t("col.model"), t("tc.mean_ms"), t("tc.median_ms"), t("tc.std_ms"), t("tc.n")]
        etm = etm.sort_values(t("tc.mean_ms"))

        fig = px.bar(etm, x=t("col.model"), y=t("tc.mean_ms"), text=t("tc.mean_ms"),
                     title=t("rq2.etm_chart"),
                     labels={t("tc.mean_ms"): t("ax.mean_time_ms")}, height=480)
        fig.update_traces(texttemplate="%{text:.1f}", textposition="outside", cliponaxis=False)
        fig.update_xaxes(tickangle=-35)
        fig.update_layout(yaxis_range=[0, max(etm[t("tc.mean_ms")]) * 1.15])
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(etm.round(1), use_container_width=True, hide_index=True)

        # ETL
        st.subheader(t("rq2.etl_header"))
        etl = df_acc.groupby("linguagem")["tempo_ms"].agg(["mean", "median", "std", "count"]).reset_index()
        etl.columns = [t("tc.language"), t("tc.mean_ms"), t("tc.median_ms"), t("tc.std_ms"), t("tc.n")]

        c1, c2 = st.columns([2, 1])
        with c1:
            fig = px.bar(etl, x=t("tc.language"), y=t("tc.mean_ms"), text=t("tc.mean_ms"),
                         color=t("tc.language"), color_discrete_map=COLORS_LANG,
                         title=t("rq2.etl_chart"), height=400)
            fig.update_traces(texttemplate="%{text:.1f}", textposition="outside", cliponaxis=False)
            fig.update_layout(showlegend=False, yaxis_range=[0, max(etl[t("tc.mean_ms")]) * 1.15])
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.dataframe(etl.round(1), use_container_width=True, hide_index=True)

        # Cross-tabs
        st.subheader(t("rq2.ct_header"))
        ct1, ct2, ct3 = st.tabs([t("rq1.ct_md"), t("rq1.ct_ml"), t("rq1.ct_ld")])

        with ct1:
            st.markdown(t("rq2.ct_md_title"))
            ct = df_acc.pivot_table(index="model_short", columns="difficulty", values="tempo_ms", aggfunc="mean")
            ct = ct.reindex(columns=[d for d in DIFF_ORDER if d in ct.columns])
            st.dataframe(ct.round(1).style.format("{:.1f}"), use_container_width=True)
            fig = px.imshow(ct.values, x=ct.columns.tolist(), y=ct.index.tolist(),
                            text_auto=".1f", aspect="auto", color_continuous_scale="YlOrRd",
                            title=t("rq2.hm_md"),
                            labels=dict(x=t("ax.difficulty"), y=t("ax.model"), color=t("ax.time_ms")))
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

        with ct2:
            st.markdown(t("rq2.ct_ml_title"))
            ct = df_acc.pivot_table(index="model_short", columns="linguagem", values="tempo_ms", aggfunc="mean")
            ct = ct.reindex(columns=[l for l in LANG_ORDER if l in ct.columns])
            st.dataframe(ct.round(1).style.format("{:.1f}"), use_container_width=True)
            fig = px.imshow(ct.values, x=ct.columns.tolist(), y=ct.index.tolist(),
                            text_auto=".1f", aspect="auto", color_continuous_scale="YlOrRd",
                            title=t("rq2.hm_ml"),
                            labels=dict(x=t("ax.language"), y=t("ax.model"), color=t("ax.time_ms")))
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

        with ct3:
            st.markdown(t("rq2.ct_ld_title"))
            ct = df_acc.pivot_table(index="linguagem", columns="difficulty", values="tempo_ms", aggfunc="mean")
            ct = ct.reindex(columns=[d for d in DIFF_ORDER if d in ct.columns])
            ct = ct.reindex([l for l in LANG_ORDER if l in ct.index])
            st.dataframe(ct.round(1).style.format("{:.1f}"), use_container_width=True)

        # Box plots
        st.subheader(t("rq2.box_header"))
        bp1, bp2, bp3 = st.tabs([t("rq2.box_model"), t("rq2.box_lang"), t("rq2.box_diff")])

        with bp1:
            fig = px.box(df_acc, x="model_short", y="tempo_ms", points=False,
                         title=t("rq2.box_model_title"),
                         labels={"tempo_ms": t("ax.time_ms"), "model_short": t("ax.model")}, height=450)
            fig.update_xaxes(tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)
        with bp2:
            fig = px.box(df_acc, x="linguagem", y="tempo_ms", color="linguagem",
                         color_discrete_map=COLORS_LANG, points=False,
                         title=t("rq2.box_lang_title"),
                         labels={"tempo_ms": t("ax.time_ms"), "linguagem": t("ax.language")}, height=400)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        with bp3:
            fig = px.box(df_acc, x="difficulty", y="tempo_ms", color="difficulty",
                         color_discrete_map=COLORS_DIFF, points=False,
                         title=t("rq2.box_diff_title"),
                         labels={"tempo_ms": t("ax.time_ms"), "difficulty": t("ax.difficulty")}, height=400)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)


# ==================================================================
# TAB 4: RQ3 - MEMORY USAGE
# ==================================================================
with tab_rq3:
    st.header(t("rq3.header"))
    st.markdown(t("rq3.desc"))

    if df_acc.empty:
        st.warning(t("rq3.nodata"))
    else:
        n_acc = len(df_acc)

        # OAMU summary
        st.subheader(t("rq3.oamu_header"))
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric(t("rq2.mean"), f"{df_acc['memoria_mb'].mean():.1f} MB")
        c2.metric(t("rq2.median"), f"{df_acc['memoria_mb'].median():.1f} MB")
        c3.metric(t("rq2.std"), f"{df_acc['memoria_mb'].std():.1f} MB")
        c4.metric(t("rq2.p99"), f"{df_acc['memoria_mb'].quantile(0.99):.1f} MB")
        c5.metric(t("rq2.max"), f"{df_acc['memoria_mb'].max():.1f} MB")
        st.caption(t("rq2.based_on").format(n=n_acc))

        with st.expander(t("rq3.hist_header")):
            fig = px.histogram(df_acc, x="memoria_mb", nbins=100,
                               title=t("rq3.hist_title"),
                               labels={"memoria_mb": t("ax.memory_mb"), "count": t("ax.frequency")},
                               height=350)
            fig.update_layout(margin=dict(t=50, b=40))
            st.plotly_chart(fig, use_container_width=True)

        # MUD
        st.subheader(t("rq3.mud_header"))
        mud = df_acc.groupby("difficulty", observed=True)["memoria_mb"].agg(["mean", "median", "std", "count"]).reset_index()
        mud.columns = [t("tc.difficulty"), t("tc.mean_mb"), t("tc.median_mb"), t("tc.std_mb"), t("tc.n")]

        c1, c2 = st.columns([2, 1])
        with c1:
            fig = px.bar(mud, x=t("tc.difficulty"), y=t("tc.mean_mb"), text=t("tc.mean_mb"),
                         color=t("tc.difficulty"), color_discrete_map=COLORS_DIFF,
                         title=t("rq3.mud_chart"), height=400)
            fig.update_traces(texttemplate="%{text:.1f}", textposition="outside", cliponaxis=False)
            fig.update_layout(showlegend=False, yaxis_range=[0, max(mud[t("tc.mean_mb")]) * 1.15])
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.dataframe(mud.round(1), use_container_width=True, hide_index=True)

        # MUM
        st.subheader(t("rq3.mum_header"))
        mum = df_acc.groupby("model_short")["memoria_mb"].agg(["mean", "median", "std", "count"]).reset_index()
        mum.columns = [t("col.model"), t("tc.mean_mb"), t("tc.median_mb"), t("tc.std_mb"), t("tc.n")]
        mum = mum.sort_values(t("tc.mean_mb"))

        fig = px.bar(mum, x=t("col.model"), y=t("tc.mean_mb"), text=t("tc.mean_mb"),
                     title=t("rq3.mum_chart"),
                     labels={t("tc.mean_mb"): t("ax.mean_memory_mb")}, height=480)
        fig.update_traces(texttemplate="%{text:.1f}", textposition="outside", cliponaxis=False)
        fig.update_xaxes(tickangle=-35)
        fig.update_layout(yaxis_range=[0, max(mum[t("tc.mean_mb")]) * 1.15])
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(mum.round(1), use_container_width=True, hide_index=True)

        # MUL
        st.subheader(t("rq3.mul_header"))
        mul_df = df_acc.groupby("linguagem")["memoria_mb"].agg(["mean", "median", "std", "count"]).reset_index()
        mul_df.columns = [t("tc.language"), t("tc.mean_mb"), t("tc.median_mb"), t("tc.std_mb"), t("tc.n")]

        c1, c2 = st.columns([2, 1])
        with c1:
            fig = px.bar(mul_df, x=t("tc.language"), y=t("tc.mean_mb"), text=t("tc.mean_mb"),
                         color=t("tc.language"), color_discrete_map=COLORS_LANG,
                         title=t("rq3.mul_chart"), height=400)
            fig.update_traces(texttemplate="%{text:.1f}", textposition="outside", cliponaxis=False)
            fig.update_layout(showlegend=False, yaxis_range=[0, max(mul_df[t("tc.mean_mb")]) * 1.15])
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.dataframe(mul_df.round(1), use_container_width=True, hide_index=True)

        # Cross-tabs
        st.subheader(t("rq3.ct_header"))
        ct1, ct2, ct3 = st.tabs([t("rq1.ct_md"), t("rq1.ct_ml"), t("rq1.ct_ld")])

        with ct1:
            st.markdown(t("rq3.ct_md_title"))
            ct = df_acc.pivot_table(index="model_short", columns="difficulty", values="memoria_mb", aggfunc="mean")
            ct = ct.reindex(columns=[d for d in DIFF_ORDER if d in ct.columns])
            st.dataframe(ct.round(1).style.format("{:.1f}"), use_container_width=True)
            fig = px.imshow(ct.values, x=ct.columns.tolist(), y=ct.index.tolist(),
                            text_auto=".1f", aspect="auto", color_continuous_scale="Blues",
                            title=t("rq3.hm_md"),
                            labels=dict(x=t("ax.difficulty"), y=t("ax.model"), color=t("ax.memory_mb")))
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

        with ct2:
            st.markdown(t("rq3.ct_ml_title"))
            ct = df_acc.pivot_table(index="model_short", columns="linguagem", values="memoria_mb", aggfunc="mean")
            ct = ct.reindex(columns=[l for l in LANG_ORDER if l in ct.columns])
            st.dataframe(ct.round(1).style.format("{:.1f}"), use_container_width=True)
            fig = px.imshow(ct.values, x=ct.columns.tolist(), y=ct.index.tolist(),
                            text_auto=".1f", aspect="auto", color_continuous_scale="Blues",
                            title=t("rq3.hm_ml"),
                            labels=dict(x=t("ax.language"), y=t("ax.model"), color=t("ax.memory_mb")))
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

        with ct3:
            st.markdown(t("rq3.ct_ld_title"))
            ct = df_acc.pivot_table(index="linguagem", columns="difficulty", values="memoria_mb", aggfunc="mean")
            ct = ct.reindex(columns=[d for d in DIFF_ORDER if d in ct.columns])
            ct = ct.reindex([l for l in LANG_ORDER if l in ct.index])
            st.dataframe(ct.round(1).style.format("{:.1f}"), use_container_width=True)

        # Box plots
        st.subheader(t("rq3.box_header"))
        bp1, bp2, bp3 = st.tabs([t("rq2.box_model"), t("rq2.box_lang"), t("rq2.box_diff")])

        with bp1:
            fig = px.box(df_acc, x="model_short", y="memoria_mb", points=False,
                         title=t("rq3.box_model_title"),
                         labels={"memoria_mb": t("ax.memory_mb"), "model_short": t("ax.model")}, height=450)
            fig.update_xaxes(tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)
        with bp2:
            fig = px.box(df_acc, x="linguagem", y="memoria_mb", color="linguagem",
                         color_discrete_map=COLORS_LANG, points=False,
                         title=t("rq3.box_lang_title"),
                         labels={"memoria_mb": t("ax.memory_mb"), "linguagem": t("ax.language")}, height=400)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        with bp3:
            fig = px.box(df_acc, x="difficulty", y="memoria_mb", color="difficulty",
                         color_discrete_map=COLORS_DIFF, points=False,
                         title=t("rq3.box_diff_title"),
                         labels={"memoria_mb": t("ax.memory_mb"), "difficulty": t("ax.difficulty")}, height=400)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        # Speed-memory trade-off
        st.subheader(t("rq3.tradeoff_header"))
        trade_lang = df_acc.groupby("linguagem").agg(
            tempo_medio=("tempo_ms", "mean"),
            memoria_media=("memoria_mb", "mean"),
            n=("memoria_mb", "count"),
        ).reset_index()
        fig = px.scatter(trade_lang, x="tempo_medio", y="memoria_media",
                         color="linguagem", color_discrete_map=COLORS_LANG,
                         size="n", text="linguagem",
                         title=t("rq3.tradeoff_chart"),
                         labels={"tempo_medio": t("ax.mean_time_ms"), "memoria_media": t("ax.mean_memory_mb")},
                         height=450)
        fig.update_traces(textposition="top center")
        st.plotly_chart(fig, use_container_width=True)


# ==================================================================
# TAB 5: STATISTICAL ANALYSIS
# ==================================================================
with tab_stats:
    st.header(t("st.header"))
    st.markdown(t("st.desc"))

    if not HAS_SCIPY:
        st.warning(t("st.no_scipy"))

    # ---- Analyses from the paper (full dataset, precomputed in results/)
    st.caption(t("pp.caption"))
    PAPER = load_paper_files()
    num = PAPER["num"]
    if not num:
        st.warning(t("pp.missing"))
    else:
        all_models_num = list(num.get("arm", {}).keys())

        # ---------------- a. acceptance with Wilson CIs
        st.subheader(t("pp.a.header"))
        st.markdown(t("pp.a.desc"))
        oar_p = num.get("oar", {})
        if oar_p:
            c1, c2 = st.columns(2)
            ci = oar_p.get("ci", [np.nan, np.nan])
            c1.metric(t("pp.oar_metric"), f"{oar_p.get('pct_acc', np.nan):.1f}%  [{ci[0]:.1f}, {ci[1]:.1f}]")
            c2.metric(t("pp.oar_n"), f"{num.get('n', 0):,}")
        st.caption(t("pp.oar_note"))
        st.caption(t("pp.a.note_lang"))

        specs = [
            (t("rq1.ct_md"), "arm_dif", t("ax.model"), t("ax.difficulty"), DIFF_ORDER, COLORS_DIFF),
            (t("rq1.ct_ml"), "arm_lang", t("ax.model"), t("ax.language"), LANG_ORDER, COLORS_LANG),
            (t("rq1.ct_ld"), "arl_dif", t("ax.language"), t("ax.difficulty"), DIFF_ORDER, COLORS_DIFF),
        ]
        sub_tabs = st.tabs([sp[0] for sp in specs])
        for tb, (title, key, rname, cname, corder, cmap) in zip(sub_tabs, specs):
            with tb:
                dct = ci_table(num.get(key), True, rname, cname)
                if dct.empty:
                    st.info(t("pp.missing_part"))
                    continue
                st.dataframe(ci_wide(dct, rname, cname, corder), use_container_width=True, hide_index=True)
                dct["err_plus"] = dct["hi"] - dct["pct"]
                dct["err_minus"] = dct["pct"] - dct["lo"]
                fig = px.bar(dct, x="pct", y=rname, color=cname, orientation="h", barmode="group",
                             error_x="err_plus", error_x_minus="err_minus",
                             color_discrete_map=cmap, category_orders={cname: corder},
                             labels={"pct": t("ax.acceptance_pct")},
                             height=max(320, 26 * len(dct[rname].unique()) * len(corder) // 2 + 120))
                st.plotly_chart(fig, use_container_width=True)

        with st.expander(t("pp.a.marg")):
            marg = []
            for key, lab in (("ard", t("ax.difficulty")), ("arl", t("ax.language")), ("arm", t("ax.model"))):
                tb_ = ci_table(num.get(key), False, "cell", "x")
                for _, r in tb_.iterrows():
                    marg.append({"": lab, t("pp.col.cell"): r["cell"], t("pp.col.k"): r["k"], t("pp.col.n"): r["n"],
                                 t("pp.col.pct"): round(r["pct"], 1), t("pp.col.lo"): round(r["lo"], 1),
                                 t("pp.col.hi"): round(r["hi"], 1)})
            if marg:
                st.dataframe(pd.DataFrame(marg), use_container_width=True, hide_index=True)

        # ---------------- b. decision rule + omnibus
        st.subheader(t("pp.b.header"))
        st.markdown(t("pp.b.desc"))
        st.caption(t("st.anova_desc"))
        glb = pd.DataFrame(num.get("global", []))
        if not glb.empty:
            fac_lab = {"Model": t("ax.model"), "Language": t("ax.language"), "Difficulty": t("ax.difficulty")}
            met_lab = {"Acc.": t("stcol.acceptance"), "Time": t("stcol.time"), "Mem.": t("stcol.memory")}
            test_lab = {"chi2": "chi-square", "KW": "Kruskal-Wallis"}
            gt = pd.DataFrame({
                t("stcol.factor"): glb["fator"].map(fac_lab),
                t("stcol.metric"): glb["metrica"].map(met_lab),
                "F (ANOVA)": glb["F"].map(lambda v: f"{v:.2f}"),
                "p (ANOVA)": glb["pF"].map(fmt_p),
                "eta2": glb["eta2"].map(lambda v: f"{v:.4f}"),
                t("pp.col.test"): glb["teste"].map(test_lab),
                t("pp.col.stat"): glb["H"].map(lambda v: f"{v:.1f}"),
                t("pp.col.df"): glb["dof"],
                t("pp.col.p"): glb["p"].map(fmt_p),
                t("pp.col.effect"): glb["efeito"],
                t("pp.col.effect_val"): glb["efeito_val"].map(lambda v: f"{v:.3f}"),
                t("pp.col.pairs"): glb.apply(lambda r: f"{int(r['pares_sig'])}/{int(r['n_pares'])}", axis=1),
            })
            st.dataframe(gt, use_container_width=True, hide_index=True)
        else:
            st.info(t("pp.missing_part"))
        st.caption(t("pp.b.note_time"))
        shp = num.get("shapiro", {})
        if shp:
            st.markdown("**" + t("pp.b.shapiro") + "**")
            st.dataframe(pd.DataFrame([{
                t("pp.col.metric"): {"time": t("stcol.time"), "mem": t("stcol.memory")}.get(k, k),
                "W": f"{v.get('W', np.nan):.3f}", "p": fmt_p(v.get("p")),
                "W (residuals)": f"{v.get('W_res', np.nan):.3f}", "p (residuals)": fmt_p(v.get("p_res")),
            } for k, v in shp.items()]), use_container_width=True, hide_index=True)

        # ---------------- c. post hoc (Holm)
        st.subheader(t("pp.c.header"))
        st.markdown(t("pp.c.desc"))
        ph = PAPER["posthoc"]
        if ph.empty:
            st.info(t("pp.missing_part"))
        else:
            ph = ph.copy()
            ph["sig"] = ph["p_holm"] < 0.05
            met_ph = {"acceptance": t("stcol.acceptance"), "Time": t("stcol.time"), "Mem.": t("stcol.memory")}
            fac_ph = {"Model": t("ax.model"), "Language": t("ax.language"), "Difficulty": t("ax.difficulty")}
            cnt = ph.groupby(["metrica", "fator"]).agg(total=("sig", "size"), sig=("sig", "sum")).reset_index()
            st.dataframe(pd.DataFrame({
                t("stcol.metric"): cnt["metrica"].map(met_ph),
                t("stcol.factor"): cnt["fator"].map(fac_ph),
                t("pp.col.total"): cnt["total"],
                t("pp.col.sig"): cnt["sig"].astype(int),
            }), use_container_width=True, hide_index=True)

            st.markdown("**" + t("pp.c.table") + "**")
            f1, f2, f3 = st.columns(3)
            sel_met = f1.selectbox(t("stcol.metric"), list(ph["metrica"].unique()), key="pp_ph_metric",
                                   format_func=lambda k: met_ph.get(k, k))
            facs = list(ph[ph["metrica"] == sel_met]["fator"].unique())
            sel_fac = f2.selectbox(t("stcol.factor"), facs, key="pp_ph_factor", format_func=lambda k: fac_ph.get(k, k))
            only_sig = f3.checkbox(t("pp.c.only_sig"), value=False, key="pp_ph_sig")
            v = ph[(ph["metrica"] == sel_met) & (ph["fator"] == sel_fac)]
            if only_sig:
                v = v[v["sig"]]
            st.dataframe(pd.DataFrame({
                t("pp.col.a"): v["a"].map(_msh), t("pp.col.b"): v["b"].map(_msh),
                t("pp.col.estat"): v["estat"].map(lambda x: f"{x:.2f}"),
                t("pp.col.p"): v["p"].map(fmt_p), t("pp.col.p_holm"): v["p_holm"].map(fmt_p),
            }), use_container_width=True, hide_index=True)

        # ---------------- d. GLMM + GEE
        st.subheader(t("pp.d.header"))
        st.markdown(t("pp.d.desc"))
        gor = PAPER["glmm_or"]
        if gor.empty:
            st.info(t("pp.missing_part"))
        else:
            mterms = [x[len("modelo"):] for x in gor["termo"] if str(x).startswith("modelo") and not str(x).startswith("modelo:")]
            st.caption(t("pp.d.ref").format(m=ref_model(mterms, all_models_num)))
            st.markdown("**" + t("pp.d.or") + "**")
            st.dataframe(or_table(gor, "termo", "OR", "lo", "hi", "p"), use_container_width=True, hide_index=True)
            st.caption(t("pp.d.lang_note"))
        for key, lab in (("lrt_f", "pp.d.lrt_f"), ("lrt_i", "pp.d.lrt_i")):
            lrt = PAPER[key]
            if lrt.empty:
                continue
            lrt = lrt.rename(columns={lrt.columns[0]: "term"})
            nice = {"modelo": t("ax.model"), "linguagem": t("ax.language"), "dif": t("ax.difficulty")}
            lrt["term"] = lrt["term"].map(lambda x: ":".join(nice.get(p_, p_) for p_ in str(x).split(":")))
            out_l = pd.DataFrame({t("pp.col.term"): lrt["term"],
                                  t("pp.col.chisq"): lrt["chisq"].map(lambda x: f"{x:.1f}"),
                                  t("pp.col.df"): lrt["df"].astype(int),
                                  t("pp.col.p"): lrt["p"].map(fmt_p)})
            st.markdown("**" + t(lab) + "**")
            st.dataframe(out_l, use_container_width=True, hide_index=True)
        if PAPER["resumo"]:
            with st.expander(t("pp.d.summary")):
                st.code(PAPER["resumo"], language="text")
        gee = num.get("gee", {})
        if gee:
            gdf = pd.DataFrame([{"term": k, **v} for k, v in gee.items()])
            st.markdown("**" + t("pp.d.gee") + "**")
            st.dataframe(or_table(gdf, "term", "OR", "lo", "hi", "p"), use_container_width=True, hide_index=True)

        # ---------------- e. attrition
        st.subheader(t("pp.e.header"))
        st.markdown(t("pp.e.desc"))
        atr = num.get("atrito", {})
        if atr:
            st.dataframe(pd.DataFrame([{
                t("ax.difficulty"): k,
                t("pp.col.planned"): v["planned"], t("pp.col.n"): v["judged"], t("pp.col.missing"): v["missing"],
                t("tc.accepted"): v["acc"], t("pp.col.rate"): round(v["rate_judged"], 1),
                t("pp.col.lower"): round(v["lower"], 1), t("pp.col.upper"): round(v["upper"], 1),
            } for k, v in atr.items()]), use_container_width=True, hide_index=True)
        else:
            st.info(t("pp.missing_part"))

        # ---------------- f. acceptance x memory correlation
        st.subheader(t("pp.f.header"))
        st.markdown(t("pp.f.desc"))
        corr = num.get("corr", {})
        if corr:
            crow = []

            def _add(ctl, pair_key, d_, extra=""):
                if not d_:
                    return
                crow.append({t("pp.col.control"): ctl + extra, t("pp.col.pair"): t("pp.pair." + pair_key),
                             "N": d_.get("N"), "Pearson r": f"{d_['r']:.2f}", "p (Pearson)": fmt_p(d_["p"]),
                             t("pp.col.rho"): f"{d_['rho']:.2f}", "p (Spearman)": fmt_p(d_["p_rho"])})
            _add(t("pp.ctl.raw"), "acc_mem", corr.get("acc_mem"))
            _add(t("pp.ctl.rel"), "acc_mem", corr.get("acc_mem_rel"))
            for ck, cl in (("comum_todos", "pp.ctl.all"), ("comum_sem_allam", "pp.ctl.noallam")):
                blk = corr.get(ck, {})
                ex = f" ({blk.get('pares_comuns', '?')} pairs, {blk.get('submissoes', '?')} submissions)" if blk else ""
                _add(t(cl), "acc_mem", blk.get("acc_mem"), ex)
            _add(t("pp.ctl.raw"), "acc_time", corr.get("acc_time"))
            _add(t("pp.ctl.rel"), "acc_time", corr.get("acc_time_rel"))
            for ck, cl in (("comum_todos", "pp.ctl.all"), ("comum_sem_allam", "pp.ctl.noallam")):
                blk = corr.get(ck, {})
                ex = f" ({blk.get('pares_comuns', '?')} pairs, {blk.get('submissoes', '?')} submissions)" if blk else ""
                _add(t(cl), "acc_time", blk.get("acc_time"), ex)
            _add(t("pp.ctl.raw"), "time_mem", corr.get("time_mem"))
            st.dataframe(pd.DataFrame(crow), use_container_width=True, hide_index=True)
            st.info(t("pp.f.note"))
        else:
            st.info(t("pp.missing_part"))

        # ---------------- g. contamination proxies
        st.subheader(t("pp.g.header"))
        st.markdown(t("pp.g.desc"))
        cont = num.get("contaminacao", {})
        if cont:
            prox = [("id", "id_z"), ("n_subm", "log_subm"), ("humana", "humana_z")]
            lab_gee = {"id_z": "Question ID (z)", "log_subm": "log(global submissions)", "humana_z": "Human acceptance rate (z)"}
            st.dataframe(pd.DataFrame([{
                t("pp.col.proxy"): t("pp.proxy." + k),
                t("pp.col.rho"): f"{cont[k]['rho']:.2f}", t("pp.col.p"): fmt_p(cont[k]["p"]),
            } for k, _ in prox if k in cont]), use_container_width=True, hide_index=True)
            geec = cont.get("gee", {})
            if geec:
                st.markdown("**GEE**")
                st.dataframe(pd.DataFrame([{
                    t("pp.col.proxy"): lab_gee.get(k, k), t("pp.col.or"): f"{v['OR']:.2f}",
                    t("pp.col.ci"): f"[{v['lo']:.2f}, {v['hi']:.2f}]", t("pp.col.p"): fmt_p(v["p"]),
                } for k, v in geec.items()]), use_container_width=True, hide_index=True)
            st.warning(t("pp.g.note"))
        else:
            st.info(t("pp.missing_part"))

        # ---------------- h. judge drift
        st.subheader(t("pp.h.header"))
        dv = num.get("deriva", {})
        if dv:
            st.markdown(t("pp.h.desc").format(n=dv.get("n", "?")))
            c1, c2, c3 = st.columns(3)
            c1.metric(t("pp.h.same"), f"{dv.get('mesmo_veredito', '?')}/{dv.get('n', '?')}")
            c2.metric(t("pp.h.accepted"), f"{dv.get('n_aceitas', '?')}")
            c3.metric(t("pp.h.mem_mean"), f"{dv.get('memoria', {}).get('razao_media', np.nan):.2f}")
            st.dataframe(pd.DataFrame([
                {t("pp.col.metric"): t("pp.h.time_med"), t("pp.col.value"): f"{dv.get('tempo', {}).get('mediana_dif_ms', np.nan):.1f}"},
                {t("pp.col.metric"): t("pp.h.time_p"), t("pp.col.value"): fmt_p(dv.get("tempo", {}).get("p_wilcoxon"))},
                {t("pp.col.metric"): t("pp.h.mem_mean"), t("pp.col.value"): f"{dv.get('memoria', {}).get('razao_media', np.nan):.3f}"},
                {t("pp.col.metric"): t("pp.h.mem_med"), t("pp.col.value"): f"{dv.get('memoria', {}).get('mediana_razao', np.nan):.3f}"},
                {t("pp.col.metric"): t("pp.h.mem_p"), t("pp.col.value"): fmt_p(dv.get("memoria", {}).get("p_wilcoxon"))},
            ]), use_container_width=True, hide_index=True)
            st.caption(t("pp.h.note").format(r=dv.get("memoria", {}).get("razao_media", np.nan),
                                             mr=dv.get("memoria", {}).get("mediana_razao", np.nan)))
        else:
            st.info(t("pp.missing_part"))

    # ---- Exploratory views on the sidebar filters
    st.markdown("---")
    st.subheader(t("st.filtered_header"))
    st.caption(t("st.filtered_desc"))
    if df.empty:
        st.warning(t("st.nodata"))
    else:
        df_stat = df.copy()
        df_stat["is_accepted"] = (df_stat["status_paper"] == "Accepted").astype(int)

        # Cohen's d (languages)
        st.subheader(t("st.cohens_lang_header"))
        st.markdown(t("st.cohens_desc"))

        cohens_rows = []
        metrics_for_cohens = [
            (t("stcol.acceptance"), "is_accepted", df_stat),
            (t("stcol.time"), "tempo_ms", df_acc),
            (t("stcol.memory"), "memoria_mb", df_acc),
        ]
        lang_pairs = [("C++", "Java"), ("C++", "Python3"), ("Java", "Python3")]

        for metric_label, col, data in metrics_for_cohens:
            for l1, l2 in lang_pairs:
                g1 = data[data["linguagem"] == l1][col].dropna().values
                g2 = data[data["linguagem"] == l2][col].dropna().values
                d = compute_cohens_d(g1, g2)
                cohens_rows.append({
                    t("stcol.metric"): metric_label,
                    t("stcol.pair"): f"{l1} vs {l2}",
                    "Cohen's d": f"{d:.2f}" if not np.isnan(d) else "-",
                    t("stcol.magnitude"): (
                        "large" if abs(d) > 0.8 else
                        "medium" if abs(d) > 0.5 else
                        "small" if abs(d) > 0.2 else
                        "negligible"
                    ) if not np.isnan(d) else "-",
                })

        if cohens_rows:
            st.dataframe(pd.DataFrame(cohens_rows), use_container_width=True, hide_index=True)

        # Cohen's d (difficulty)
        st.subheader(t("st.cohens_diff_header"))
        diff_pairs = [("Easy", "Medium"), ("Easy", "Hard"), ("Medium", "Hard")]
        diff_cohens = []
        for d1, d2 in diff_pairs:
            g1 = df_stat[df_stat["difficulty"] == d1]["is_accepted"].dropna().values
            g2 = df_stat[df_stat["difficulty"] == d2]["is_accepted"].dropna().values
            d = compute_cohens_d(g1, g2)
            diff_cohens.append({
                t("stcol.pair"): f"{d1} vs {d2}",
                "Cohen's d": f"{d:.2f}" if not np.isnan(d) else "-",
                t("stcol.magnitude"): (
                    "large" if abs(d) > 0.8 else
                    "medium" if abs(d) > 0.5 else
                    "small" if abs(d) > 0.2 else
                    "negligible"
                ) if not np.isnan(d) else "-",
            })
        st.dataframe(pd.DataFrame(diff_cohens), use_container_width=True, hide_index=True)

        # Correlation plots (the paper's correlation table, with composition controls, is above)
        model_agg = df_stat.groupby("model_short").agg(
            acceptance=("is_accepted", "mean"),
        ).reset_index()

        if not df_acc.empty:
            model_eff = df_acc.groupby("model_short").agg(
                mean_time=("tempo_ms", "mean"),
                mean_memory=("memoria_mb", "mean"),
            ).reset_index()
            model_agg = model_agg.merge(model_eff, on="model_short", how="left")

        if "mean_time" in model_agg.columns and "mean_memory" in model_agg.columns:
            st.subheader(t("st.corr_viz_header"))
            c1, c2 = st.columns(2)
            with c1:
                if "mean_memory" in model_agg.columns:
                    fig = px.scatter(model_agg, x="acceptance", y="mean_memory",
                                     text="model_short",
                                     title=t("st.corr_acc_mem"),
                                     labels={"acceptance": t("ax.acceptance_pct"), "mean_memory": t("ax.mean_memory_mb")},
                                     height=400)
                    fig.update_traces(textposition="top center", marker_size=10)
                    valid_data = model_agg.dropna(subset=["acceptance", "mean_memory"])
                    if len(valid_data) >= 2:
                        z = np.polyfit(valid_data["acceptance"], valid_data["mean_memory"], 1)
                        x_line = np.linspace(valid_data["acceptance"].min(), valid_data["acceptance"].max(), 50)
                        fig.add_trace(go.Scatter(x=x_line, y=np.polyval(z, x_line),
                                                 mode="lines", line=dict(dash="dash", color="red"),
                                                 name=t("stcol.trend")))
                    st.plotly_chart(fig, use_container_width=True)

            with c2:
                if "mean_time" in model_agg.columns:
                    fig = px.scatter(model_agg, x="acceptance", y="mean_time",
                                     text="model_short",
                                     title=t("st.corr_acc_time"),
                                     labels={"acceptance": t("ax.acceptance_pct"), "mean_time": t("ax.mean_time_ms")},
                                     height=400)
                    fig.update_traces(textposition="top center", marker_size=10)
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(t("st.corr_insuf"))

        # Composite score
        st.subheader(t("st.composite_header"))
        st.markdown(t("st.composite_desc"))

        if "mean_time" in model_agg.columns and "mean_memory" in model_agg.columns:
            ma = model_agg.dropna(subset=["acceptance", "mean_time", "mean_memory"]).copy()
            if len(ma) > 1:
                ma["norm_acc"] = (ma["acceptance"] - ma["acceptance"].min()) / (ma["acceptance"].max() - ma["acceptance"].min() + 1e-9)
                ma["norm_time"] = 1 - (ma["mean_time"] - ma["mean_time"].min()) / (ma["mean_time"].max() - ma["mean_time"].min() + 1e-9)
                ma["norm_mem"] = 1 - (ma["mean_memory"] - ma["mean_memory"].min()) / (ma["mean_memory"].max() - ma["mean_memory"].min() + 1e-9)
                ma["composite"] = (ma["norm_acc"] + ma["norm_time"] + ma["norm_mem"]) / 3
                ma = ma.sort_values("composite", ascending=False)

                composite_label = "Composite Score" if st.session_state.get("ui_lang") == "en" else "Escore Composto"
                display_cols = {
                    "model_short": t("col.model"),
                    "acceptance": t("stcol.acceptance"),
                    "mean_time": t("stcol.time"),
                    "mean_memory": t("stcol.memory"),
                    "composite": composite_label,
                }
                st.dataframe(
                    ma[list(display_cols.keys())].rename(columns=display_cols).style.format({
                        t("stcol.acceptance"): "{:.2%}",
                        t("stcol.time"): "{:.1f}",
                        t("stcol.memory"): "{:.1f}",
                        composite_label: "{:.3f}",
                    }),
                    use_container_width=True, hide_index=True,
                )

                fig = px.bar(ma, x="model_short", y="composite", text="composite",
                             title=t("st.composite_chart"),
                             labels={"composite": "Score", "model_short": t("ax.model")},
                             height=420)
                fig.update_traces(texttemplate="%{text:.3f}", textposition="outside", cliponaxis=False)
                fig.update_xaxes(tickangle=-35)
                st.plotly_chart(fig, use_container_width=True)

        # Recommendations
        st.subheader(t("st.rec_header"))
        st.markdown(t("st.rec_body"))


# ==================================================================
# TAB 6: CODE EXPLORER
# ==================================================================
with tab_explorer:
    st.header(t("ex.header"))
    st.markdown(t("ex.desc"))

    if df_llm.empty:
        st.warning(t("ex.nodata"))
    else:
        lang_map = {"C++": "cpp", "Java": "java", "Python3": "python"}
        df_llm_view = df_llm.copy()
        df_llm_view["model_short"] = df_llm_view["modelo"].map(
            lambda m: MODEL_SHORT.get(str(m).strip(), str(m).strip())
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            llm_models = sorted(df_llm_view["model_short"].dropna().unique().tolist())
            sel_llm_model = st.selectbox(t("ex.model"), llm_models, key="explorer_model")
        with c2:
            llm_langs = sorted(
                df_llm_view[df_llm_view["model_short"] == sel_llm_model]["linguagem"].dropna().unique().tolist()
            )
            sel_llm_lang = st.selectbox(t("ex.language"), llm_langs, key="explorer_lang")
        with c3:
            subset = df_llm_view[
                (df_llm_view["model_short"] == sel_llm_model) &
                (df_llm_view["linguagem"] == sel_llm_lang)
            ]
            problem_ids = sorted(subset["problem_id"].dropna().unique().tolist())
            sel_problem = st.selectbox(t("ex.problem"), problem_ids, key="explorer_problem")

        hit = subset[subset["problem_id"] == sel_problem]
        if not hit.empty:
            row = hit.iloc[0]
            code = row.get("code", "")

            result_row = None
            if not df_all.empty:
                result_match = df_all[
                    (df_all["modelo"] == row["modelo"]) &
                    (df_all["linguagem"] == row["linguagem"]) &
                    (df_all["id_questao"] == sel_problem)
                ]
                if not result_match.empty:
                    result_row = result_match.iloc[0]

            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown(f"{t('ex.code_title')} - {sel_llm_model} / {sel_llm_lang} / Problem {sel_problem}")
                st.code(code or t("ex.empty_code"), language=lang_map.get(sel_llm_lang, "text"))

            with c2:
                st.markdown(t("ex.meta_title"))
                meta = {
                    t("ex.category"): row.get("categoria", "-"),
                    t("ex.reason"): row.get("motivo", "-"),
                }
                for k, v in meta.items():
                    st.write(f"**{k}:** {v}")

                if result_row is not None:
                    st.markdown("---")
                    st.markdown(t("ex.result_title"))
                    status = result_row.get("status", "-")
                    is_acc = result_row.get("aceito", False)
                    color = "green" if is_acc else "red"
                    st.markdown(f"**{t('ex.status')}:** :{color}[{status}]")
                    fonte_row = str(result_row.get("fonte", "2025")).strip() if "fonte" in result_row.index else "2025"
                    fonte_row = "2026" if fonte_row.startswith("2026") else "2025"
                    st.caption(t("ex.source") + ": " + t("ex.src_" + fonte_row))
                    if not is_acc:
                        errs = load_judge_errors(fonte_row, str(row["modelo"]), str(row["linguagem"])).get(int(sel_problem), {})
                        for ek, elabel in (("erro_compilacao", "ex.err_compile"), ("erro_runtime", "ex.err_runtime")):
                            if errs.get(ek):
                                with st.expander(t(elabel)):
                                    st.code(str(errs[ek])[:3000], language="text")
                    if is_acc:
                        tempo = result_row.get("tempo_ms", "-")
                        mem = result_row.get("memoria_mb", "-")
                        st.write(f"**{t('ex.time')}:** {tempo} ms")
                        st.write(f"**{t('ex.memory')}:** {mem} MB")

                    if not df_meta.empty:
                        pmeta = df_meta[df_meta["problem_id"] == sel_problem]
                        if not pmeta.empty:
                            pm = pmeta.iloc[0]
                            st.markdown("---")
                            st.markdown(t("ex.problem_info"))
                            st.write(f"**{t('ex.title_field')}:** {pm.get('titulo', '-')}")
                            st.write(f"**{t('ex.diff_field')}:** {pm.get('difficulty', '-')}")
                            st.write(f"**{t('ex.topic_field')}:** {pm.get('tema_principal', '-')}")
                else:
                    st.info(t("ex.no_result"))

        # Side-by-side comparison
        st.markdown("---")
        st.subheader(t("ex.compare_header"))

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(t("ex.model_a"))
            m_a = st.selectbox(t("ex.model") + " A", llm_models, key="cmp_model_a")
            l_a_opts = sorted(df_llm_view[df_llm_view["model_short"] == m_a]["linguagem"].dropna().unique().tolist())
            l_a = st.selectbox(t("ex.language") + " A", l_a_opts, key="cmp_lang_a")
        with c2:
            st.markdown(t("ex.model_b"))
            m_b = st.selectbox(t("ex.model") + " B", llm_models, index=min(1, len(llm_models) - 1), key="cmp_model_b")
            l_b_opts = sorted(df_llm_view[df_llm_view["model_short"] == m_b]["linguagem"].dropna().unique().tolist())
            l_b = st.selectbox(t("ex.language") + " B", l_b_opts, key="cmp_lang_b")

        ids_a = set(df_llm_view[(df_llm_view["model_short"] == m_a) & (df_llm_view["linguagem"] == l_a)]["problem_id"].dropna())
        ids_b = set(df_llm_view[(df_llm_view["model_short"] == m_b) & (df_llm_view["linguagem"] == l_b)]["problem_id"].dropna())
        common = sorted(ids_a & ids_b)

        if common:
            sel_cmp = st.selectbox(t("ex.compare_problem"), common, key="cmp_problem")

            row_a = df_llm_view[
                (df_llm_view["model_short"] == m_a) &
                (df_llm_view["linguagem"] == l_a) &
                (df_llm_view["problem_id"] == sel_cmp)
            ]
            row_b = df_llm_view[
                (df_llm_view["model_short"] == m_b) &
                (df_llm_view["linguagem"] == l_b) &
                (df_llm_view["problem_id"] == sel_cmp)
            ]

            ca, cb = st.columns(2)
            with ca:
                if not row_a.empty:
                    st.markdown(f"**{m_a} / {l_a}**")
                    st.code(row_a.iloc[0].get("code", ""), language=lang_map.get(l_a, "text"))
            with cb:
                if not row_b.empty:
                    st.markdown(f"**{m_b} / {l_b}**")
                    st.code(row_b.iloc[0].get("code", ""), language=lang_map.get(l_b, "text"))
        else:
            st.info(t("ex.no_common"))


# ==================================================================
# TAB 7: DATA EXPORT
# ==================================================================
with tab_export:
    st.header(t("exp.header"))
    st.markdown(t("exp.desc"))

    if df.empty:
        st.warning(t("exp.nodata"))
    else:
        st.subheader(t("exp.sub_header"))
        st.caption(t("exp.record_count").format(n=len(df)))

        show_cols = [c for c in [
            "modelo", "model_short", "linguagem", "slug", "titulo", "id_questao",
            "difficulty", "tema_principal", "status", "status_paper", "aceito",
            "tempo_ms", "memoria_mb", "submission_id",
        ] if c in df.columns]

        st.dataframe(df[show_cols].head(500), use_container_width=True, hide_index=True)
        if len(df) > 500:
            st.caption(t("exp.showing_500"))

        c1, c2, c3 = st.columns(3)
        with c1:
            csv_data = df[show_cols].to_csv(index=False).encode("utf-8")
            st.download_button(t("exp.dl_csv_all"), csv_data,
                               file_name="submissions_filtered.csv", mime="text/csv")
        with c2:
            json_data = df[show_cols].to_json(orient="records", force_ascii=False).encode("utf-8")
            st.download_button(t("exp.dl_json_all"), json_data,
                               file_name="submissions_filtered.json", mime="application/json")
        with c3:
            if not df_acc.empty:
                csv_acc = df_acc[show_cols].to_csv(index=False).encode("utf-8")
                st.download_button(t("exp.dl_csv_acc"), csv_acc,
                                   file_name="accepted_only.csv", mime="text/csv")

        # Summary tables
        st.markdown("---")
        st.subheader(t("exp.tables_header"))
        st.markdown(t("exp.tables_desc"))

        with st.expander(t("exp.table_oar")):
            summary = pd.DataFrame({
                t("col.result"): ["Accepted", "Compilation Error", "Wrong Answer", "Total"],
                t("col.count"): [
                    len(df[df["status_paper"] == "Accepted"]),
                    len(df[df["status_paper"] == "Compilation Error"]),
                    len(df[df["status_paper"] == "Wrong Answer"]),
                    len(df),
                ],
            })
            summary["%"] = (summary[t("col.count")] / len(df) * 100).round(1)
            st.dataframe(summary, use_container_width=True, hide_index=True)
            st.download_button("CSV", summary.to_csv(index=False).encode("utf-8"),
                               "oar_summary.csv", "text/csv", key="dl_oar")

        with st.expander(t("exp.table_arm_diff")):
            df_tmp = df.copy()
            df_tmp["acc"] = (df_tmp["status_paper"] == "Accepted").astype(int)
            ct = df_tmp.pivot_table(index="model_short", columns="difficulty", values="acc", aggfunc="mean").multiply(100)
            ct = ct.reindex(columns=[d for d in DIFF_ORDER if d in ct.columns])
            st.dataframe(ct.round(1), use_container_width=True)
            st.download_button("CSV", ct.round(1).to_csv().encode("utf-8"),
                               "arm_difficulty.csv", "text/csv", key="dl_arm_diff")

        with st.expander(t("exp.table_arm_lang")):
            df_tmp = df.copy()
            df_tmp["acc"] = (df_tmp["status_paper"] == "Accepted").astype(int)
            ct = df_tmp.pivot_table(index="model_short", columns="linguagem", values="acc", aggfunc="mean").multiply(100)
            ct = ct.reindex(columns=[l for l in LANG_ORDER if l in ct.columns])
            st.dataframe(ct.round(1), use_container_width=True)
            st.download_button("CSV", ct.round(1).to_csv().encode("utf-8"),
                               "arm_language.csv", "text/csv", key="dl_arm_lang")

        with st.expander(t("exp.table_etm_diff")):
            if not df_acc.empty:
                ct = df_acc.pivot_table(index="model_short", columns="difficulty", values="tempo_ms", aggfunc="mean")
                ct = ct.reindex(columns=[d for d in DIFF_ORDER if d in ct.columns])
                st.dataframe(ct.round(1), use_container_width=True)
                st.download_button("CSV", ct.round(1).to_csv().encode("utf-8"),
                                   "etm_difficulty.csv", "text/csv", key="dl_etm_diff")

        with st.expander(t("exp.table_etm_lang")):
            if not df_acc.empty:
                ct = df_acc.pivot_table(index="model_short", columns="linguagem", values="tempo_ms", aggfunc="mean")
                ct = ct.reindex(columns=[l for l in LANG_ORDER if l in ct.columns])
                st.dataframe(ct.round(1), use_container_width=True)
                st.download_button("CSV", ct.round(1).to_csv().encode("utf-8"),
                                   "etm_language.csv", "text/csv", key="dl_etm_lang")

        with st.expander(t("exp.table_mum_diff")):
            if not df_acc.empty:
                ct = df_acc.pivot_table(index="model_short", columns="difficulty", values="memoria_mb", aggfunc="mean")
                ct = ct.reindex(columns=[d for d in DIFF_ORDER if d in ct.columns])
                st.dataframe(ct.round(1), use_container_width=True)
                st.download_button("CSV", ct.round(1).to_csv().encode("utf-8"),
                                   "mum_difficulty.csv", "text/csv", key="dl_mum_diff")

        with st.expander(t("exp.table_mum_lang")):
            if not df_acc.empty:
                ct = df_acc.pivot_table(index="model_short", columns="linguagem", values="memoria_mb", aggfunc="mean")
                ct = ct.reindex(columns=[l for l in LANG_ORDER if l in ct.columns])
                st.dataframe(ct.round(1), use_container_width=True)
                st.download_button("CSV", ct.round(1).to_csv().encode("utf-8"),
                                   "mum_language.csv", "text/csv", key="dl_mum_lang")

        # Problem metadata
        if not df_meta.empty:
            st.markdown("---")
            st.subheader(t("exp.meta_header"))
            st.caption(t("exp.meta_count").format(n=len(df_meta)))
            st.dataframe(df_meta[["problem_id", "slug", "titulo", "difficulty", "tema_principal"]].head(336),
                         use_container_width=True, hide_index=True)
            st.download_button(t("exp.dl_meta"),
                               df_meta.to_csv(index=False).encode("utf-8"),
                               "problem_metadata.csv", "text/csv", key="dl_meta")
