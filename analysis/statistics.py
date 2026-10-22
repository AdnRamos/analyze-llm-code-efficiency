"""
All statistics, tables and figure coordinates reported in the paper.

Usage:
    python analysis/statistics.py                      # final dataset (data/results.csv) -> results/statistics/
    Rscript analysis/glmm.R                            # mixed-effects logistic model -> results/glmm/

Inputs (read-only):
    data/results.csv                                   final dataset (10,666 judged submissions)
    data/submissions/*.ndjson                          judge records (2025 verdict of the control submissions)
    data/problems/sample.csv                           difficulty, id and global LeetCode statistics of each problem
    data/rejudging_2026/control.ndjson                 100 control submissions (judge drift 2025 -> 2026)
Outputs in results/statistics/:
    numeros.json      every number cited in the text
    tabelas.tex       tables and figure coordinates, between %%BEGIN <label> / %%END <label> markers
    posthoc.csv       every post hoc pair (Holm)
    ESTATISTICA.md    readable summary
Regra de decisao (Revisor C, item 1): tempo e memoria nao sao normais (Shapiro-Wilk), entao a conclusao
sobre tempo e memoria segue sempre o Kruskal-Wallis (efeito: epsilon^2) e o post hoc de Dunn com Holm.
A ANOVA e reportada so por comparabilidade. Para a aceitacao (binaria), o teste e o qui-quadrado de
independencia, com post hoc de proporcoes (z) com Holm; o tamanho do efeito e o eta^2 da ANOVA sobre o
indicador 0/1 (mesmos limiares da versao anterior), com o V de Cramer gravado em numeros.json.

Dependencias: pandas, numpy, scipy, statsmodels.
"""
import argparse
import ast
import itertools
import json
import math
import os
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportions_ztest

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
import sys  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from lib import paths as P  # noqa: E402  (honours STUDY_DATA_DIR / STUDY_RESULTS_DIR)
LANGS = ["C++", "Java", "Python3"]
DIFS = ["Easy", "Medium", "Hard"]
DIF_MAP = {"Fácil": "Easy", "Média": "Medium", "Médio": "Medium", "Difícil": "Hard"}
NOME = {
    "allam-2-7b": "allam-2-7b",
    "deepseek-r1-distill-llama-70b": "deepseek-r1-distill-llama-70b",
    "gemma2-9b-it": "gemma2-9b-it",
    "llama-3.1-8b-instant": "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile": "llama-3.3-70b-versatile",
    "llama3-70b-8192": "llama3-70b-8192",
    "llama3-8b-8192": "llama3-8b-8192",
    "meta-llama_llama-4-maverick-17b-128e-instruct": "llama-4-maverick-17b-128e-instruct",
    "meta-llama_llama-4-scout-17b-16e-instruct": "llama-4-scout-17b-16e-instruct",
    "moonshotai_kimi-k2-instruct": "moonshotai/kimi-k2-instruct",
    "qwen_qwen3-32b": "qwen/qwen3-32b",
}
ST = ["Accepted", "Compile Error", "Wrong Answer", "Runtime Error", "Time Limit Exceeded",
      "Memory Limit Exceeded", "Timeout"]
ST_TEX = {"Accepted": "Accepted", "Compile Error": "Compilation Error", "Wrong Answer": "Wrong Answer (proper)",
          "Runtime Error": "Runtime Error", "Time Limit Exceeded": "Time Limit Exceeded",
          "Memory Limit Exceeded": "Memory Limit Exceeded", "Timeout": "Timeout"}


# ----------------------------------------------------------------------------- utilidades
def wilson(k, n, z=1.959964):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def f1(x):
    return "---" if x is None or (isinstance(x, float) and math.isnan(x)) else "%.1f" % x


def thou(n):
    return "{:,}".format(int(n)).replace(",", "{,}")


def pfmt(p):
    if p == 0 or p < 1e-300:
        return r"$<10^{-300}$"
    if p < 0.001:
        m, e = ("%.1e" % p).split("e")
        return r"$%s\times10^{%d}$" % (m, int(e))
    return "%.3f" % p


def efeito(v):
    return "small" if v < 0.06 else ("medium" if v < 0.14 else "large")


def cramer_label(v, dfmin):
    # Cohen (1988): limiares de w ajustados pelos graus de liberdade min(r-1,c-1)
    lim = {1: (0.10, 0.30, 0.50), 2: (0.07, 0.21, 0.35)}.get(dfmin, (0.06, 0.17, 0.29))
    return "negligible" if v < lim[0] else "small" if v < lim[1] else "medium" if v < lim[2] else "large"


def holm(ps):
    return multipletests(ps, method="holm")[1] if len(ps) else []


# ----------------------------------------------------------------------------- dados
def carregar(base):
    arq = str(P.RESULTS_CSV)
    d = pd.read_csv(arq)
    s = pd.read_csv(str(P.SAMPLE_CSV))
    s["dif"] = s["dificuldade"].map(DIF_MAP)
    st = s["stats"].apply(ast.literal_eval)
    s["n_subm_global"] = st.apply(lambda x: x["totalSubmissionRaw"])
    s["taxa_humana"] = st.apply(lambda x: float(str(x["acRate"]).rstrip("%")) / 100)
    s = s.rename(columns={"id": "id_questao"})[["id_questao", "dif", "n_subm_global", "taxa_humana"]]
    d["id_questao"] = d["id_questao"].astype(float).astype(int)
    d = d.merge(s, on="id_questao", how="left", validate="many_to_one")
    assert d["dif"].notna().all()
    d["modelo_tex"] = d["modelo"].map(NOME).fillna(d["modelo"])   # modelos fora do artigo mantem o nome da pasta
    d["acc"] = (d["status"] == "Accepted").astype(int)
    for c in ("tempo_ms", "memoria_mb"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    if "fonte" not in d:
        d["fonte"] = "judge"
    return d, s


# ----------------------------------------------------------------------------- testes
def dunn(valores, grupos):
    """Dunn (1964) com correcao de empates; devolve lista (g1, g2, z, p_bruto)."""
    df = pd.DataFrame({"v": valores, "g": grupos})
    df["r"] = stats.rankdata(df["v"])
    N = len(df)
    _, t = np.unique(df["v"], return_counts=True)
    corr = (t ** 3 - t).sum() / (12 * (N - 1))
    R = df.groupby("g")["r"].mean()
    n = df.groupby("g").size()
    out = []
    for a, b in itertools.combinations(sorted(R.index), 2):
        se = math.sqrt((N * (N + 1) / 12 - corr) * (1 / n[a] + 1 / n[b]))
        z = (R[a] - R[b]) / se
        out.append((a, b, z, 2 * stats.norm.sf(abs(z))))
    return out


def posthoc_prop(d, fator):
    out = []
    g = d.groupby(fator)["acc"].agg(["sum", "count"])
    for a, b in itertools.combinations(sorted(g.index), 2):
        z, p = proportions_ztest([g.loc[a, "sum"], g.loc[b, "sum"]], [g.loc[a, "count"], g.loc[b, "count"]])
        out.append((a, b, z, p))
    return out


def global_tests(d, acc_df):
    linhas, ph = [], []
    fatores = [("Model", "modelo_tex"), ("Language", "linguagem"), ("Difficulty", "dif")]
    # aceitacao
    for nome, f in fatores:
        grupos = [g["acc"].values for _, g in d.groupby(f)]
        F, pA = stats.f_oneway(*grupos)
        ss_b = sum(len(g) * (g.mean() - d["acc"].mean()) ** 2 for g in grupos)
        ss_t = ((d["acc"] - d["acc"].mean()) ** 2).sum()
        tab = pd.crosstab(d[f], d["acc"])
        chi2, pc, dof, _ = stats.chi2_contingency(tab, correction=False)
        k = min(tab.shape) - 1
        V = math.sqrt(chi2 / (len(d) * k))
        sig = pc < 0.05
        pares = posthoc_prop(d, f) if sig else []
        padj = holm([p for *_, p in pares])
        for (a, b, z, p), pa in zip(pares, padj):
            ph.append({"metrica": "acceptance", "fator": nome, "a": a, "b": b, "estat": z, "p": p, "p_holm": pa})
        linhas.append({"fator": nome, "metrica": "Acc.", "F": F, "pF": pA, "eta2": ss_b / ss_t,
                       "teste": "chi2", "H": chi2, "dof": dof, "p": pc, "efeito_val": V,
                       "efeito": efeito(ss_b / ss_t) if sig else "n.s.", "efeito_V": cramer_label(V, k),
                       "n_pares": len(pares), "pares_sig": int(sum(np.array(padj) < 0.05)) if len(pares) else 0})
    # tempo e memoria (aceitas)
    for met, col in (("Time", "tempo_ms"), ("Mem.", "memoria_mb")):
        a = acc_df.dropna(subset=[col])
        for nome, f in fatores:
            grupos = [g[col].values for _, g in a.groupby(f)]
            F, pF = stats.f_oneway(*grupos)
            ss_b = sum(len(g) * (g.mean() - a[col].mean()) ** 2 for g in grupos)
            ss_t = ((a[col] - a[col].mean()) ** 2).sum()
            H, pH = stats.kruskal(*grupos)
            eps2 = H / (len(a) - 1)
            sig = pH < 0.05
            pares = dunn(a[col].values, a[f].values) if sig else []
            padj = holm([p for *_, p in pares])
            for (x, y, z, p), pa in zip(pares, padj):
                ph.append({"metrica": met, "fator": nome, "a": x, "b": y, "estat": z, "p": p, "p_holm": pa})
            linhas.append({"fator": nome, "metrica": met, "F": F, "pF": pF, "eta2": ss_b / ss_t,
                           "teste": "KW", "H": H, "dof": len(grupos) - 1, "p": pH, "efeito_val": eps2,
                           "efeito": efeito(eps2) if sig else "n.s.",
                           "n_pares": len(pares), "pares_sig": int(sum(np.array(padj) < 0.05)) if len(pares) else 0})
    return linhas, ph


def cohen_d(x, y):
    nx, ny = len(x), len(y)
    sp = math.sqrt(((nx - 1) * np.var(x, ddof=1) + (ny - 1) * np.var(y, ddof=1)) / (nx + ny - 2))
    return abs(np.mean(x) - np.mean(y)) / sp


def cohen_h(p1, p2):
    return abs(2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2)))


# ----------------------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", choices=["corrigida"], default="corrigida", help=argparse.SUPPRESS)
    ap.add_argument("--sem-misto", action="store_true", help="pula a GEE e a analise de contaminacao (mais rapido)")
    args = ap.parse_args()
    d, s = carregar(args.base)
    OUT = str(P.RESULTS / "statistics")
    os.makedirs(OUT, exist_ok=True)
    J = {"base": args.base, "n": int(len(d))}
    T = {}
    A = d[d["acc"] == 1].copy()

    # ---------------- RQ1: aceitacao
    k, n = int(d["acc"].sum()), len(d)
    ce = int((d["status"] == "Compile Error").sum())
    J["oar"] = {"accepted": k, "ce": ce, "wa_agg": n - k - ce, "pct_acc": 100 * k / n, "pct_ce": 100 * ce / n,
                "pct_wa_agg": 100 * (n - k - ce) / n, "ci": [100 * x for x in wilson(k, n)],
                "verdicts": {x: int((d["status"] == x).sum()) for x in ST}}
    T["tab:oar"] = (r"""\begin{tabular}{lrrr}
\hline\hline
\textbf{Outcome} & \textbf{Count} & \textbf{\%} & \textbf{95\% CI} \\
\hline
""" + "".join("%s & %s & %.1f & [%.1f, %.1f] \\\\\n" % (lab, thou(c), 100 * c / n, *[100 * x for x in wilson(c, n)])
              for lab, c in (("Accepted", k), ("Compilation Error", ce), ("Wrong Answer", n - k - ce)))
                    + r"""\hline
\textbf{Total} & %s & 100.0 & \\
\hline\hline
\end{tabular}""" % thou(n))

    def taxa(g):
        k_, n_ = int(g["acc"].sum()), len(g)
        lo, hi = wilson(k_, n_)
        return {"k": k_, "n": n_, "pct": 100 * k_ / n_, "lo": 100 * lo, "hi": 100 * hi}

    J["ard"] = {x: taxa(d[d["dif"] == x]) for x in DIFS}
    J["arl"] = {x: taxa(d[d["linguagem"] == x]) for x in LANGS}
    J["arm"] = {m: taxa(g) for m, g in d.groupby("modelo_tex")}
    ordem_acc = sorted(J["arm"], key=lambda m: -J["arm"][m]["pct"])
    J["arm_dif"] = {m: {x: taxa(d[(d["modelo_tex"] == m) & (d["dif"] == x)]) for x in DIFS} for m in ordem_acc}
    J["arm_lang"] = {m: {x: taxa(d[(d["modelo_tex"] == m) & (d["linguagem"] == x)]) for x in LANGS} for m in ordem_acc}
    J["arl_dif"] = {l: {x: taxa(d[(d["linguagem"] == l) & (d["dif"] == x)]) for x in DIFS} for l in LANGS}

    def ci_cell(t):
        return "%.1f {\\scriptsize[%.1f, %.1f]}" % (t["pct"], t["lo"], t["hi"])

    def tab_ci(rows, cols, get, first):
        h = "\\begin{tabular}{l%s}\n\\hline\\hline\n\\textbf{%s} & %s \\\\\n\\hline\n" % (
            "r" * len(cols), first, " & ".join("\\textbf{%s}" % c for c in cols))
        for r in rows:
            nome = "\\texttt{%s}" % r if first == "Model" else r
            h += nome + " & " + " & ".join(ci_cell(get(r, c)) for c in cols) + " \\\\\n"
        return h + "\\hline\\hline\n\\end{tabular}"

    T["tab:arm_diff"] = tab_ci(ordem_acc, DIFS, lambda r, c: J["arm_dif"][r][c], "Model")
    T["tab:arm_lang"] = tab_ci(ordem_acc, LANGS, lambda r, c: J["arm_lang"][r][c], "Model")
    T["tab:arl_diff"] = tab_ci(LANGS, DIFS, lambda r, c: J["arl_dif"][r][c], "Language")
    T["fig:ard"] = "\\addplot coordinates {%s};" % " ".join("(%s,%.1f)" % (x, J["ard"][x]["pct"]) for x in DIFS)
    T["fig:arl"] = "\\addplot coordinates {%s};" % " ".join("(%s,%.1f)" % (x, J["arl"][x]["pct"]) for x in LANGS)
    nomes_alfa = sorted(J["arm"])
    T["fig:arm:coords"] = ",\n        ".join(nomes_alfa)
    T["fig:arm"] = "\\addplot coordinates {\n%s\n};" % "\n".join(
        "    (%s,%.1f)" % (m, J["arm"][m]["pct"]) for m in nomes_alfa)

    # desfecho por modelo e por linguagem
    sm = "\\begin{tabular}{lrrrr}\n\\hline\\hline\n\\textbf{Model} & \\textbf{Accepted} & \\textbf{CE} & \\textbf{WA} & \\textbf{Total} \\\\\n\\hline\n"
    J["status_model"] = {}
    for m in ordem_acc:
        g = d[d["modelo_tex"] == m]
        a_, c_ = int(g["acc"].sum()), int((g["status"] == "Compile Error").sum())
        w_ = len(g) - a_ - c_
        J["status_model"][m] = {"acc": a_, "ce": c_, "wa": w_, "n": len(g)}
        sm += "\\texttt{%s} & %s (%.1f\\%%) & %s (%.1f\\%%) & %s (%.1f\\%%) & %s \\\\\n" % (
            m, thou(a_), 100 * a_ / len(g), thou(c_), 100 * c_ / len(g), thou(w_), 100 * w_ / len(g), thou(len(g)))
    sm += "\\hline\n\\textbf{All models} & %s (%.1f\\%%) & %s (%.1f\\%%) & %s (%.1f\\%%) & %s \\\\\n\\hline\\hline\n\\end{tabular}" % (
        thou(k), 100 * k / n, thou(ce), 100 * ce / n, thou(n - k - ce), 100 * (n - k - ce) / n, thou(n))
    T["tab:status_model"] = sm
    sl = "\\begin{tabular}{lrrr}\n\\hline\\hline\n\\textbf{Verdict} & \\textbf{C++} & \\textbf{Java} & \\textbf{Python3} \\\\\n\\hline\n"
    J["status_lang"] = {}
    for x in ST:
        cel = []
        for l in LANGS:
            g = d[d["linguagem"] == l]
            c_ = int((g["status"] == x).sum())
            J["status_lang"].setdefault(l, {})[x] = c_
            cel.append("%s (%.1f\\%%)" % (thou(c_), 100 * c_ / len(g)))
        sl += ST_TEX[x] + " & " + " & ".join(cel) + " \\\\\n"
    sl += "\\hline\n\\textbf{Total} & " + " & ".join(
        "\\textbf{%s}" % thou((d["linguagem"] == l).sum()) for l in LANGS) + " \\\\\n\\hline\\hline\n\\end{tabular}"
    T["tab:status_lang"] = sl
    for l in LANGS:
        g = d[d["linguagem"] == l]
        perf = g["status"].isin(["Time Limit Exceeded", "Memory Limit Exceeded", "Timeout"]).sum()
        J["status_lang"][l]["perf_pct_total"] = 100 * perf / len(g)
        J["status_lang"][l]["perf_pct_falhas"] = 100 * perf / (len(g) - g["acc"].sum())
        J["status_lang"][l]["ce_re_pct"] = 100 * g["status"].isin(["Compile Error", "Runtime Error"]).sum() / len(g)

    # atrito (Revisor C, item 3): 11.088 pedidos, limites da aceitacao
    n_modelos = d["modelo"].nunique()
    planned = {x: int((s["dif"] == x).sum()) * 3 * n_modelos for x in DIFS}
    J["atrito"] = {}
    for x in DIFS + ["All"]:
        pl = sum(planned.values()) if x == "All" else planned[x]
        g = d if x == "All" else d[d["dif"] == x]
        jud, acc_ = len(g), int(g["acc"].sum())
        miss = pl - jud
        J["atrito"][x] = {"planned": pl, "judged": jud, "missing": miss, "acc": acc_,
                          "rate_judged": 100 * acc_ / jud, "lower": 100 * acc_ / pl, "upper": 100 * (acc_ + miss) / pl}
    at = "\\begin{tabular}{lrrrrrr}\n\\hline\\hline\n\\textbf{Difficulty} & \\textbf{Planned} & \\textbf{Judged} & \\textbf{Not submitted} & \\textbf{Acc. (judged)} & \\textbf{Lower} & \\textbf{Upper} \\\\\n\\hline\n"
    for x in DIFS + ["All"]:
        r = J["atrito"][x]
        at += "%s & %s & %s & %s (%.1f\\%%) & %.1f & %.1f & %.1f \\\\\n" % (
            "\\textbf{All}" if x == "All" else x, thou(r["planned"]), thou(r["judged"]), thou(r["missing"]),
            100 * r["missing"] / r["planned"], r["rate_judged"], r["lower"], r["upper"])
        if x == "Hard":
            at += "\\hline\n"
    T["tab:attrition"] = at + "\\hline\\hline\n\\end{tabular}"
    J["missing_by_model"] = {m: 3 * len(s) - int((d["modelo_tex"] == m).sum()) for m in ordem_acc}

    # ---------------- RQ2 / RQ3: tempo e memoria das aceitas
    def desc(v):
        v = pd.Series(v).dropna()
        return {"n": int(len(v)), "mean": v.mean(), "median": v.median(), "std": v.std(), "p99": v.quantile(0.99),
                "max": v.max(), "skew": stats.skew(v), "zeros": int((v == 0).sum())}

    for col, key, un in (("tempo_ms", "time", "ms"), ("memoria_mb", "mem", "MB")):
        J[key] = {"overall": desc(A[col]),
                  "dif": {x: desc(A.loc[A["dif"] == x, col]) for x in DIFS},
                  "lang": {x: desc(A.loc[A["linguagem"] == x, col]) for x in LANGS},
                  "model": {m: desc(A.loc[A["modelo_tex"] == m, col]) for m in ordem_acc}}
        J[key]["model_dif"] = {m: {x: desc(A.loc[(A["modelo_tex"] == m) & (A["dif"] == x), col]) for x in DIFS} for m in ordem_acc}
        J[key]["model_lang"] = {m: {x: desc(A.loc[(A["modelo_tex"] == m) & (A["linguagem"] == x), col]) for x in LANGS} for m in ordem_acc}
        J[key]["lang_dif"] = {l: {x: desc(A.loc[(A["linguagem"] == l) & (A["dif"] == x), col]) for x in DIFS} for l in LANGS}
        o = J[key]["overall"]
        lbl = "oaet" if key == "time" else "oamu"
        T["tab:" + lbl] = ("\\begin{tabular}{lr}\n\\hline\\hline\n\\textbf{Statistic} & \\textbf{Value (%s)} \\\\\n\\hline\n" % un
                           + "Mean & %.1f \\\\\nMedian & %.1f \\\\\nStd.\\ & %.1f \\\\\nP99 & %.1f \\\\\nMax & %s \\\\\n" % (
                               o["mean"], o["median"], o["std"], o["p99"], thou(o["max"]) if o["max"] >= 1000 else "%.1f" % o["max"])
                           + "\\hline\\hline\n\\end{tabular}")
        lbl2 = "etd_stats" if key == "time" else "mud_stats"
        t2 = "\\begin{tabular}{lrrrrr}\n\\hline\\hline\n\\textbf{Difficulty} & \\textbf{$n$} & \\textbf{Mean} & \\textbf{Median} & \\textbf{Std.} & \\textbf{Max} \\\\\n\\hline\n"
        for x in DIFS:
            q = J[key]["dif"][x]
            mx = thou(q["max"]) if key == "time" else "%.1f" % q["max"]
            t2 += "%s & %s & %.1f & %.1f & %.1f & %s \\\\\n" % (x, thou(q["n"]), q["mean"], q["median"], q["std"], mx)
        T["tab:" + lbl2] = t2 + "\\hline\\hline\n\\end{tabular}"
        ordem = sorted(ordem_acc, key=lambda m: J[key]["model"][m]["mean"])
        J[key]["ordem"] = ordem
        pref = "et" if key == "time" else "mu"
        T["fig:%sd" % pref] = "\\addplot coordinates {%s};" % " ".join("(%s,%.1f)" % (x, J[key]["dif"][x]["mean"]) for x in DIFS)
        T["fig:%sl" % pref] = "\\addplot coordinates {%s};" % " ".join("(%s,%.1f)" % (x, J[key]["lang"][x]["mean"]) for x in LANGS)
        T["fig:%sm:coords" % pref] = ",\n        ".join(ordem)
        T["fig:%sm" % pref] = "\\addplot coordinates {\n%s\n};" % "\n".join(
            "    (%s,%.1f)" % (m, J[key]["model"][m]["mean"]) for m in ordem)

        def cel(q):
            return "---" if q["n"] == 0 else "%.1f {\\scriptsize(%d)}" % (q["mean"], q["n"])
        for lab, cols, get in (("%sm_diff" % pref, DIFS, lambda m, c: J[key]["model_dif"][m][c]),
                               ("%sm_lang" % pref, LANGS, lambda m, c: J[key]["model_lang"][m][c])):
            t3 = "\\begin{tabular}{l%s}\n\\hline\\hline\n\\textbf{Model} & %s \\\\\n\\hline\n" % (
                "r" * len(cols), " & ".join("\\textbf{%s}" % c for c in cols))
            for m in ordem:
                t3 += "\\texttt{%s} & %s \\\\\n" % (m, " & ".join(cel(get(m, c)) for c in cols))
            T["tab:" + lab] = t3 + "\\hline\\hline\n\\end{tabular}"
        t4 = "\\begin{tabular}{lrrr}\n\\hline\\hline\n\\textbf{Language} & \\textbf{Easy} & \\textbf{Medium} & \\textbf{Hard} \\\\\n\\hline\n"
        for l in LANGS:
            t4 += "%s & %s \\\\\n" % (l, " & ".join(cel(J[key]["lang_dif"][l][x]) for x in DIFS))
        T["tab:%sl_diff" % pref] = t4 + "\\hline\\hline\n\\end{tabular}"

    # ---------------- normalidade
    J["shapiro"] = {}
    for col, key in (("tempo_ms", "time"), ("memoria_mb", "mem")):
        v = A[col].dropna()
        W, p = stats.shapiro(v)
        res = v - A.groupby("modelo_tex")[col].transform("mean")
        Wr, pr = stats.shapiro(res)
        J["shapiro"][key] = {"W": W, "p": p, "W_res": Wr, "p_res": pr}
    sh = J["shapiro"]
    T["tab:shapiro"] = ("\\begin{tabular}{lrr}\n\\hline\n\\textbf{Test} & \\textbf{$W$} & \\textbf{$p$} \\\\\n\\hline\n"
                        + "Execution time (raw) & %.3f & %s \\\\\n" % (sh["time"]["W"], pfmt(sh["time"]["p"]))
                        + "Memory usage (raw) & %.3f & %s \\\\\n" % (sh["mem"]["W"], pfmt(sh["mem"]["p"]))
                        + "Execution-time residuals (by model) & %.3f & %s \\\\\n" % (sh["time"]["W_res"], pfmt(sh["time"]["p_res"]))
                        + "Memory residuals (by model) & %.3f & %s \\\\\n" % (sh["mem"]["W_res"], pfmt(sh["mem"]["p_res"]))
                        + "\\hline\n\\end{tabular}")

    # ---------------- testes globais + post hoc
    linhas, ph = global_tests(d, A)
    J["global"] = linhas
    pd.DataFrame(ph).to_csv(os.path.join(OUT, "posthoc.csv"), index=False)
    tg = ("\\begin{tabular}{llrrrrlr}\n\\hline\n\\textbf{Factor} & \\textbf{Metric} & \\textbf{$F$} & \\textbf{$\\eta^{2}$} & "
          "\\textbf{$\\chi^2$ / $H$} & \\textbf{$p$} & \\textbf{Effect} & \\textbf{Sig. pairs} \\\\\n\\hline\n")
    for r in linhas:
        ef = "n.s." if r["efeito"] == "n.s." else "%s (%s$=%.2f$)" % (
            r["efeito"], "$\\eta^{2}$" if r["teste"] == "chi2" else "$\\varepsilon^{2}$",
            r["eta2"] if r["teste"] == "chi2" else r["efeito_val"])
        ef = ef.replace("$$", "")
        pares = "%d/%d" % (r["pares_sig"], r["n_pares"]) if r["n_pares"] else "---"
        tg += "%s & %s & %.2f & %.3f & %.2f & %s & %s & %s \\\\\n" % (
            r["fator"], r["metrica"], r["F"], r["eta2"], r["H"], pfmt(r["p"]), ef, pares)
    T["tab:anova"] = tg + "\\hline\n\\end{tabular}"
    phd = pd.DataFrame(ph)
    J["posthoc_resumo"] = {}
    if len(phd):
        for (met, fat), g in phd.groupby(["metrica", "fator"]):
            sig = g[g["p_holm"] < 0.05]
            J["posthoc_resumo"]["%s|%s" % (met, fat)] = {
                "pares": int(len(g)), "sig": int(len(sig)),
                "nao_sig": [[a, b, round(p, 4)] for a, b, p in g[g["p_holm"] >= 0.05][["a", "b", "p_holm"]].values.tolist()][:60]}

    # ---------------- tamanhos de efeito pareados
    J["cohen"] = {}
    for a_, b_ in (("C++", "Java"), ("C++", "Python3"), ("Java", "Python3")):
        x, y = d[d["linguagem"] == a_]["acc"], d[d["linguagem"] == b_]["acc"]
        J["cohen"]["%s vs %s" % (a_, b_)] = {"d": cohen_d(x, y), "h": cohen_h(x.mean(), y.mean()),
                                             "d_time": cohen_d(A[A["linguagem"] == a_]["tempo_ms"], A[A["linguagem"] == b_]["tempo_ms"]),
                                             "d_mem": cohen_d(A[A["linguagem"] == a_]["memoria_mb"], A[A["linguagem"] == b_]["memoria_mb"])}
    for a_, b_ in (("Easy", "Medium"), ("Medium", "Hard"), ("Easy", "Hard")):
        x, y = d[d["dif"] == a_]["acc"], d[d["dif"] == b_]["acc"]
        J["cohen"]["%s vs %s" % (a_, b_)] = {"d": cohen_d(x, y), "h": cohen_h(x.mean(), y.mean())}
    tc = "\\begin{tabular}{lrr}\n\\hline\n\\textbf{Comparison} & \\textbf{Cohen's $d$} & \\textbf{Cohen's $h$} \\\\\n\\hline\n"
    for kk, v in J["cohen"].items():
        tc += "%s & %.2f & %.2f \\\\\n" % (kk.replace(" vs ", " vs.\\ "), v["d"], v["h"])
    T["tab:cohen_dh"] = tc + "\\hline\n\\end{tabular}"

    # ---------------- correlacoes no nivel do modelo (N=11) e controle de composicao (Revisor C, item 2)
    acc_m = pd.Series({m: J["arm"][m]["pct"] for m in ordem_acc})
    t_m = pd.Series({m: J["time"]["model"][m]["mean"] for m in ordem_acc})
    m_m = pd.Series({m: J["mem"]["model"][m]["mean"] for m in ordem_acc})
    # memoria e tempo relativos: razao para a mediana das aceitas na mesma (questao, linguagem)
    A["mem_rel"] = A["memoria_mb"] / A.groupby(["id_questao", "linguagem"])["memoria_mb"].transform("median")
    A["time_rel"] = (A["tempo_ms"] + 1) / (A.groupby(["id_questao", "linguagem"])["tempo_ms"].transform("median") + 1)
    mr_m = A.groupby("modelo_tex")["mem_rel"].mean().reindex(ordem_acc)
    tr_m = A.groupby("modelo_tex")["time_rel"].mean().reindex(ordem_acc)

    def corr(x, y):
        r, p = stats.pearsonr(x, y)
        rho, prho = stats.spearmanr(x, y)
        return {"r": r, "p": p, "rho": rho, "p_rho": prho, "N": int(len(x))}

    J["corr"] = {"acc_time": corr(acc_m, t_m), "acc_mem": corr(acc_m, m_m), "time_mem": corr(t_m, m_m),
                 "acc_mem_rel": corr(acc_m, mr_m), "acc_time_rel": corr(acc_m, tr_m)}
    # subconjunto comum: (questao, linguagem) aceitas por todos os modelos considerados
    for rot, modelos in (("todos", ordem_acc), ("sem_allam", [m for m in ordem_acc if m != "allam-2-7b"])):
        sub = A[A["modelo_tex"].isin(modelos)]
        cnt = sub.groupby(["id_questao", "linguagem"])["modelo_tex"].nunique()
        comuns = cnt[cnt == len(modelos)].index
        sc = sub.set_index(["id_questao", "linguagem"]).loc[sub.set_index(["id_questao", "linguagem"]).index.isin(comuns)].reset_index()
        info = {"pares_comuns": int(len(comuns)), "submissoes": int(len(sc))}
        if len(comuns) >= 5:
            mm = sc.groupby("modelo_tex")["memoria_mb"].mean().reindex(modelos)
            info["acc_mem"] = corr(acc_m.reindex(modelos), mm)
            tt = sc.groupby("modelo_tex")["tempo_ms"].mean().reindex(modelos)
            info["acc_time"] = corr(acc_m.reindex(modelos), tt)
        J["corr"]["comum_" + rot] = info
    c = J["corr"]

    def lin(lbl, q):
        return "%s & %.2f (%.3f) & %.2f (%.3f) \\\\\n" % (lbl, q["r"], q["p"], q["rho"], q["p_rho"])
    tp = ("\\begin{tabular}{lrr}\n\\hline\n\\textbf{Pair} & \\textbf{Pearson $r$ ($p$)} & \\textbf{Spearman $\\rho$ ($p$)} \\\\\n\\hline\n"
          + lin("Acceptance $\\times$ execution time", c["acc_time"])
          + lin("Acceptance $\\times$ memory", c["acc_mem"])
          + lin("Execution time $\\times$ memory", c["time_mem"])
          + "\\hline\n\\multicolumn{3}{l}{\\emph{Composition control (memory relative to the same problem and language)}} \\\\\n"
          + lin("Acceptance $\\times$ relative memory", c["acc_mem_rel"])
          + lin("Acceptance $\\times$ relative time", c["acc_time_rel"]))
    cs = c["comum_sem_allam"]
    if "acc_mem" in cs:
        tp += "\\multicolumn{3}{l}{\\emph{Common subset: %d problem--language pairs accepted for all 10 models}} \\\\\n" % cs["pares_comuns"]
        tp += lin("Acceptance $\\times$ memory ($N=10$)", cs["acc_mem"])
    T["tab:pearson_spearman"] = tp + "\\hline\n\\end{tabular}"

    # ---------------- GEE (robustez do modelo misto; o GLMM do artigo e analysis/glmm.R, glmmTMB/Laplace)
    if not args.sem_misto:
        import statsmodels.api as sm
        import statsmodels.formula.api as smf
        dm = d[["acc", "modelo_tex", "linguagem", "dif", "id_questao"]].copy()
        ref = "llama3-8b-8192" if "llama3-8b-8192" in ordem_acc else ordem_acc[-1]   # referencia do artigo
        dm["modelo_tex"] = pd.Categorical(dm["modelo_tex"], categories=[ref] + [m for m in ordem_acc if m != ref])
        dm["linguagem"] = pd.Categorical(dm["linguagem"], categories=LANGS)
        dm["dif"] = pd.Categorical(dm["dif"], categories=DIFS)
        form = "acc ~ C(modelo_tex) + C(linguagem) + C(dif)"
        gee = smf.gee(form, groups="id_questao", data=dm, family=sm.families.Binomial(),
                      cov_struct=sm.cov_struct.Exchangeable()).fit()
        ci = gee.conf_int()
        J["gee"] = {nm: {"OR": math.exp(gee.params[nm]), "lo": math.exp(ci.loc[nm, 0]), "hi": math.exp(ci.loc[nm, 1]),
                         "p": float(gee.pvalues[nm])} for nm in gee.params.index}
        tm = "\\begin{tabular}{lrr}\n\\hline\n\\textbf{Fixed effect} & \\textbf{GEE OR [95\\% CI]} & \\textbf{GEE $p$} \\\\\n\\hline\n"
        for nm in gee.params.index:
            if nm == "Intercept":
                continue
            lab = nm.replace("C(modelo_tex)[T.", "\\texttt{").replace("C(linguagem)[T.", "Language: ").replace("C(dif)[T.", "Difficulty: ")
            lab = lab[:-1] + ("}" if "texttt" in lab else "")
            g_ = J["gee"][nm]
            tm += "%s & %.2f [%.2f, %.2f] & %s \\\\\n" % (lab, g_["OR"], g_["lo"], g_["hi"], pfmt(g_["p"]))
        T["tab:gee"] = tm + "\\hline\n\\end{tabular}"

    # ---------------- contaminacao (Revisor C, opcional)
    pq = d.groupby("id_questao").agg(acc=("acc", "mean"), n_subm=("n_subm_global", "first"),
                                    humana=("taxa_humana", "first"), dif=("dif", "first")).reset_index()
    J["contaminacao"] = {
        "id": dict(zip(("rho", "p"), stats.spearmanr(pq["id_questao"], pq["acc"]))),
        "n_subm": dict(zip(("rho", "p"), stats.spearmanr(pq["n_subm"], pq["acc"]))),
        "humana": dict(zip(("rho", "p"), stats.spearmanr(pq["humana"], pq["acc"])))}
    if not args.sem_misto:
        dc = d.copy()
        dc["id_z"] = (dc["id_questao"] - dc["id_questao"].mean()) / dc["id_questao"].std()
        dc["log_subm"] = np.log10(dc["n_subm_global"])
        dc["humana_z"] = (dc["taxa_humana"] - dc["taxa_humana"].mean()) / dc["taxa_humana"].std()
        g2 = smf.gee("acc ~ C(modelo_tex) + C(linguagem) + C(dif) + id_z + log_subm + humana_z", groups="id_questao",
                     data=dc, family=sm.families.Binomial(), cov_struct=sm.cov_struct.Exchangeable()).fit()
        ci = g2.conf_int()
        J["contaminacao"]["gee"] = {nm: {"OR": math.exp(g2.params[nm]), "lo": math.exp(ci.loc[nm, 0]),
                                         "hi": math.exp(ci.loc[nm, 1]), "p": float(g2.pvalues[nm])}
                                    for nm in ("id_z", "log_subm", "humana_z")}

    # ---------------- deriva do juiz (controle) e sensibilidade da memoria
    ctrl = []
    if os.path.exists(P.CONTROL):   # so existe nos dados publicados (rejulgamento de 2026)
      with open(P.CONTROL, encoding="utf-8") as f:
        for l in f:
            if l.strip():
                ctrl.append(json.loads(l))
    if ctrl:
      # veredito de 2025 de cada controle: ultimo registro do juiz em data/submissions/
      ult = {}
      for nd in sorted(P.SUBMISSIONS.glob("*.ndjson")):
          for l in open(nd, encoding="utf-8"):
              if l.strip():
                  r = json.loads(l)
                  kk = (r["modelo"], r["linguagem"], int(r["id_questao"]))
                  if kk not in ult or r.get("ts_epoch", 0) >= ult[kk].get("ts_epoch", 0):
                      ult[kk] = r
      oi = pd.DataFrame([{"modelo": q[0], "linguagem": q[1], "id_questao": q[2], "status": v["status"],
                          "tempo_ms": v.get("tempo_ms"), "memoria_mb": v.get("memoria_mb")} for q, v in ult.items()]
                        ).set_index(["modelo", "linguagem", "id_questao"])
      iguais, pares_t, pares_m = 0, [], []
      for r in ctrl:
          o = oi.loc[(r["modelo"], r["linguagem"], int(r["id"]))]
          iguais += int(o["status"] == r["status"])
          if r["status"] == "Accepted" and o["status"] == "Accepted":
              pares_t.append((float(o["tempo_ms"]), float(r["tempo_ms"])))
              pares_m.append((float(o["memoria_mb"]), float(r["memoria_mb"])))
      pt, pm_ = np.array(pares_t), np.array(pares_m)
      J["deriva"] = {"n": len(ctrl), "mesmo_veredito": iguais, "n_aceitas": int(len(pm_)),
                     "tempo": {"mediana_dif_ms": float(np.median(pt[:, 1] - pt[:, 0])),
                               "iguais": int((pt[:, 1] == pt[:, 0]).sum()),
                               "p_wilcoxon": float(stats.wilcoxon(pt[:, 0], pt[:, 1]).pvalue) if len(pt) and (pt[:, 0] != pt[:, 1]).any() else 1.0},
                     "memoria": {"razao_media": float(np.mean(pm_[:, 1] / pm_[:, 0])),
                                 "mediana_razao": float(np.median(pm_[:, 1] / pm_[:, 0])),
                                 "p_wilcoxon": float(stats.wilcoxon(pm_[:, 0], pm_[:, 1]).pvalue)}}
    s25 = A[A["fonte"].astype(str) != "2026"]   # sensibilidade: memoria so dos vereditos da rodada original (2025)
    J["mem_sens_2025"] = {"n": int(len(s25)), "overall": s25["memoria_mb"].mean(),
                          "lang": {l: s25.loc[s25["linguagem"] == l, "memoria_mb"].mean() for l in LANGS},
                          "n_2026": int((A["fonte"].astype(str) == "2026").sum())}

    # ---------------- versoes "plain": mesmo formato das tabelas do manuscrito submetido (sem IC e sem n)
    T["tab:oar:plain"] = ("\\begin{tabular}{lrr}\n\\hline\\hline\n\\textbf{Outcome} & \\textbf{Count} & \\textbf{\\%} \\\\\n\\hline\n"
                          + "".join("%s & %s & %.1f \\\\\n" % (lab, thou(c_), 100 * c_ / n)
                                    for lab, c_ in (("Accepted", k), ("Compilation Error", ce), ("Wrong Answer", n - k - ce)))
                          + "\\hline\n\\textbf{Total} & %s & 100.0 \\\\\n\\hline\\hline\n\\end{tabular}" % thou(n))

    def tab_plain(rows, cols, get, first, fmt):
        h = "\\begin{tabular}{l%s}\n\\hline\\hline\n\\textbf{%s} & %s \\\\\n\\hline\n" % (
            "r" * len(cols), first, " & ".join("\\textbf{%s}" % c for c in cols))
        for r in rows:
            nome = "\\texttt{%s}" % r if first == "Model" else r
            h += nome + " & " + " & ".join(fmt(get(r, c)) for c in cols) + " \\\\\n"
        return h + "\\hline\\hline\n\\end{tabular}"
    pc = lambda t: "%.1f" % t["pct"]
    mc = lambda q: "---" if q["n"] == 0 else "%.1f" % q["mean"]
    T["tab:arm_diff:plain"] = tab_plain(ordem_acc, DIFS, lambda r, c: J["arm_dif"][r][c], "Model", pc)
    T["tab:arm_lang:plain"] = tab_plain(ordem_acc, LANGS, lambda r, c: J["arm_lang"][r][c], "Model", pc)
    T["tab:arl_diff:plain"] = tab_plain(LANGS, DIFS, lambda r, c: J["arl_dif"][r][c], "Language", pc)
    for key, pref in (("time", "et"), ("mem", "mu")):
        o = J[key]["ordem"]
        T["tab:%sm_diff:plain" % pref] = tab_plain(o, DIFS, lambda r, c: J[key]["model_dif"][r][c], "Model", mc)
        T["tab:%sm_lang:plain" % pref] = tab_plain(o, LANGS, lambda r, c: J[key]["model_lang"][r][c], "Model", mc)
        T["tab:%sl_diff:plain" % pref] = tab_plain(LANGS, DIFS, lambda r, c: J[key]["lang_dif"][r][c], "Language", mc)
        lbl2 = "etd_stats" if key == "time" else "mud_stats"
        t2 = "\\begin{tabular}{lrrrr}\n\\hline\\hline\n\\textbf{Difficulty} & \\textbf{Mean} & \\textbf{Median} & \\textbf{Std.} & \\textbf{Max} \\\\\n\\hline\n"
        for x in DIFS:
            q = J[key]["dif"][x]
            mx = thou(q["max"]) if key == "time" else "%.1f" % q["max"]
            t2 += "%s & %.1f & %.1f & %.1f & %s \\\\\n" % (x, q["mean"], q["median"], q["std"], mx)
        T["tab:%s:plain" % lbl2] = t2 + "\\hline\\hline\n\\end{tabular}"
    G = {(r["fator"], r["metrica"]): r for r in linhas}
    ta = ("\\begin{tabular}{llrrrl}\n\\hline\n\\textbf{Factor} & \\textbf{Metric} & \\textbf{$F$} & \\textbf{$p$} & "
          "\\textbf{$\\eta^{2}$} & \\textbf{Effect} \\\\\n\\hline\n")
    nota = []
    for fat, met in (("Model", "Acc."), ("Language", "Acc."), ("Difficulty", "Acc."), ("Model", "Time"),
                     ("Language", "Time"), ("Model", "Mem."), ("Language", "Mem.")):
        r = G[(fat, met)]
        sig = r["pF"] < 0.05
        eff = efeito(r["eta2"]) if sig else "n.s."
        eta = "%.2f" % r["eta2"] if sig else "---"
        if met != "Acc." and sig != (r["p"] < 0.05):
            eff += "$^{*}$"
            nota.append("$^{*}$Kruskal--Wallis $H=%.2f$, $p=%s$ (%s)." % (
                r["H"], pfmt(r["p"]).strip("$") if r["p"] < 0.001 else "%.3f" % r["p"],
                "significant" if r["p"] < 0.05 else "not significant"))
        pv = "$\\approx0$" if r["pF"] < 1e-300 else pfmt(r["pF"])
        ta += "%s & %s & %.2f & %s & %s & %s \\\\\n" % (fat, met, r["F"], pv, eta, eff)
    ta += "\\hline\n"
    for x in nota:
        ta += "\\multicolumn{6}{l}{\\footnotesize %s}\n" % x
    T["tab:anova:plain"] = ta + "\\end{tabular}"
    T["tab:pearson_spearman:plain"] = ("\\begin{tabular}{lrr}\n\\hline\n\\textbf{Pair} & \\textbf{Pearson $r$ ($p$)} & \\textbf{Spearman $\\rho$ ($p$)} \\\\\n\\hline\n"
                                       + lin("Acceptance $\\times$ execution time", c["acc_time"])
                                       + lin("Acceptance $\\times$ memory", c["acc_mem"])
                                       + lin("Execution time $\\times$ memory", c["time_mem"])
                                       + "\\hline\n\\end{tabular}")

    # ---------------- gravar
    def conv(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)
    with open(os.path.join(OUT, "numeros.json"), "w", encoding="utf-8") as f:
        json.dump(J, f, ensure_ascii=False, indent=1, default=conv)
    with open(os.path.join(OUT, "tabelas.tex"), "w", encoding="utf-8") as f:
        f.write("%% Gerado por analysis/statistics.py --base %s. Nao editar a mao.\n" % args.base)
        for kk, v in T.items():
            f.write("%%%%BEGIN %s\n%s\n%%%%END %s\n\n" % (kk, v, kk))
    md = ["# Estatística — base %s" % args.base, "",
          "Gerado por `analysis/statistics.py --base %s`." % args.base, "",
          "- Submissões: %d; aceitação %.1f%% [%.1f, %.1f]" % (n, J["oar"]["pct_acc"], *J["oar"]["ci"]),
          "- Por linguagem: " + "; ".join("%s %.1f%%" % (l, J["arl"][l]["pct"]) for l in LANGS),
          "- Por dificuldade: " + "; ".join("%s %.1f%%" % (x, J["ard"][x]["pct"]) for x in DIFS),
          "- Tempo médio %.1f ms (mediana %.1f); memória média %.1f MB (mediana %.1f)" % (
              J["time"]["overall"]["mean"], J["time"]["overall"]["median"], J["mem"]["overall"]["mean"], J["mem"]["overall"]["median"]),
          "", "## Testes globais", "", "| Fator | Métrica | F | η² | χ²/H | p | efeito | pares sig. |", "|---|---|---|---|---|---|---|---|"]
    for r in linhas:
        md.append("| %s | %s | %.2f | %.3f | %.2f | %.3g | %s (%.3f) | %d/%d |" % (
            r["fator"], r["metrica"], r["F"], r["eta2"], r["H"], r["p"], r["efeito"], r["efeito_val"], r["pares_sig"], r["n_pares"]))
    md += ["", "## Correlações (nível do modelo)", ""]
    for kk, v in J["corr"].items():
        md.append("- %s: %s" % (kk, json.dumps(v, default=conv)))
    md += ["", "## Atrito", ""] + ["- %s: %s" % (kk, json.dumps(v, default=conv)) for kk, v in J["atrito"].items()]
    if "gee" in J:
        md += ["", "## GEE (OR)", ""] + ["- %s: %.2f [%.2f, %.2f]" % (kk, v["OR"], v["lo"], v["hi"])
                                         for kk, v in J["gee"].items() if "modelo" not in kk]
        md += ["- GEE: " + "; ".join("%s %.2f (p=%.3g)" % (kk, v["OR"], v["p"]) for kk, v in J["gee"].items() if "modelo" not in kk)]
    md += ["", "## Contaminação", "", json.dumps(J["contaminacao"], default=conv, indent=1),
           "", "## Deriva do juiz", "", json.dumps(J.get("deriva", "n/a (sem rejulgamento)"), default=conv, indent=1),
           "", "## Sensibilidade da memória (só 2025)", "", json.dumps(J["mem_sens_2025"], default=conv, indent=1)]
    with open(os.path.join(OUT, "ESTATISTICA.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md[:8]))
    print("saida:", OUT)


if __name__ == "__main__":
    main()
