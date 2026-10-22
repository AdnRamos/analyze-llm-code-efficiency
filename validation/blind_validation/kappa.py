"""
Fase 3 (Revisor A, A1): concordância entre os autores na classificação manual A/B/C.

Lê as duas planilhas preenchidas (aba 'Classificar', coluna 'categoria') e o mapa cego, e grava:
  validation/blind_validation/out/kappa.md            kappa de Cohen (núcleo), IC 95%, matriz de confusão,
                                      concordância de cada autor com a sugestão automática
  validation/blind_validation/out/discordancias.csv   casos do núcleo com categorias diferentes (para consenso)
  validation/blind_validation/out/classificacao_consolidada.csv
                                      todas as linhas com as duas classificações e a sugestão automática

Uso: python validation/blind_validation/kappa.py [planilha_adenilson.xlsx planilha_rodrigo.xlsx]
Requer openpyxl.
"""
import csv
import math
import os
import sys
from collections import Counter

from openpyxl import load_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "reports", "blind_validation")
CATS = ["A", "B", "C", "?"]


def ler_planilha(path):
    ws = load_workbook(path, read_only=True, data_only=True)["Classificar"]
    rows = ws.iter_rows(values_only=True)
    cab = list(next(rows))
    i_id, i_cat, i_obs = cab.index("id_cego"), cab.index("categoria"), cab.index("observacao")
    res = {}
    for r in rows:
        if r[i_id]:
            cat = (str(r[i_cat]).strip().upper() if r[i_cat] is not None else "")
            res[r[i_id]] = (cat, r[i_obs] or "")
    return res


def kappa(pares, cats):
    """Kappa de Cohen com erro-padrão assintótico (Fleiss, Cohen & Everitt, 1969)."""
    n = len(pares)
    if n == 0:
        return None
    idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    m = [[0] * k for _ in range(k)]
    for a, b in pares:
        m[idx[a]][idx[b]] += 1
    p = [[m[i][j] / n for j in range(k)] for i in range(k)]
    pr = [sum(p[i]) for i in range(k)]
    pc = [sum(p[i][j] for i in range(k)) for j in range(k)]
    po = sum(p[i][i] for i in range(k))
    pe = sum(pr[i] * pc[i] for i in range(k))
    if pe >= 1:
        return {"n": n, "po": po, "pe": pe, "kappa": float("nan"), "ic": (float("nan"),) * 2, "m": m}
    kap = (po - pe) / (1 - pe)
    a = sum(p[i][i] * (1 - (pr[i] + pc[i]) * (1 - kap)) ** 2 for i in range(k))
    b = (1 - kap) ** 2 * sum(p[i][j] * (pc[i] + pr[j]) ** 2 for i in range(k) for j in range(k) if i != j)
    c = (kap - pe * (1 - kap)) ** 2
    var = max(a + b - c, 0) / (n * (1 - pe) ** 2)
    se = math.sqrt(var)
    return {"n": n, "po": po, "pe": pe, "kappa": kap, "ic": (kap - 1.96 * se, kap + 1.96 * se), "m": m}


def tabela_confusao(res, cats, rot_l, rot_c):
    linhas = ["| %s \\ %s | %s | total |" % (rot_l, rot_c, " | ".join(cats)),
              "|---|" + "---|" * (len(cats) + 1)]
    for i, c in enumerate(cats):
        linhas.append("| %s | %s | %d |" % (c, " | ".join(str(x) for x in res["m"][i]), sum(res["m"][i])))
    return "\n".join(linhas)


def fmt(res):
    if not res:
        return "sem dados"
    return "n=%d; concordância observada=%.3f; esperada=%.3f; **kappa=%.3f** (IC 95%% %.3f a %.3f)" % (
        res["n"], res["po"], res["pe"], res["kappa"], res["ic"][0], res["ic"][1])


def main():
    pa = sys.argv[1] if len(sys.argv) > 2 else os.path.join(HERE, "fase3_classificacao_adenilson.xlsx")
    pb = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "fase3_classificacao_rodrigo.xlsx")
    ca, cb = ler_planilha(pa), ler_planilha(pb)
    with open(os.path.join(HERE, "fase3_mapa_cego.csv"), encoding="utf-8-sig", newline="") as f:
        mapa = {r["id_cego"]: r for r in csv.DictReader(f)}
    os.makedirs(OUT, exist_ok=True)

    nucleo = [i for i in mapa if mapa[i]["lote"] == "nucleo_kappa"]
    val = lambda c: c in CATS  # noqa: E731
    faltam_a = [i for i in nucleo if not val(ca.get(i, ("",))[0])]
    faltam_b = [i for i in nucleo if not val(cb.get(i, ("",))[0])]
    completos = [i for i in nucleo if i not in faltam_a and i not in faltam_b]

    pares4 = [(ca[i][0], cb[i][0]) for i in completos]
    pares3 = [(a, b) for a, b in pares4 if a != "?" and b != "?"]
    k4, k3 = kappa(pares4, CATS), kappa(pares3, CATS[:3])

    L = ["# Concordância na classificação manual (Fase 3, Revisor A, ponto A1)", "",
         "Gerado por `validation/blind_validation/kappa.py`. Núcleo: %d casos; completos nas duas planilhas: %d "
         "(faltam %d em Adenilson, %d em Rodrigo)." % (len(nucleo), len(completos), len(faltam_a), len(faltam_b)), "",
         "## Kappa de Cohen no núcleo", "",
         "- Categorias A/B/C/?: " + fmt(k4),
         "- Só A/B/C (excluindo pares com '?'): " + fmt(k3), ""]
    if k4:
        L += ["### Matriz de confusão (A/B/C/?)", "", tabela_confusao(k4, CATS, "Adenilson", "Rodrigo"), ""]

    L += ["## Cada autor × sugestão automática (todas as linhas classificadas)", ""]
    for nome, cl in (("Adenilson", ca), ("Rodrigo", cb)):
        pr = [(cl[i][0], mapa[i]["sugestao_auto"]) for i in mapa if val(cl.get(i, ("",))[0]) and cl[i][0] != "?"]
        L.append("- %s: %s" % (nome, fmt(kappa(pr, CATS[:3]))))
    L.append("")

    desc = [i for i in completos if ca[i][0] != cb[i][0]]
    with open(os.path.join(OUT, "discordancias.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id_cego", "chave", "adenilson", "rodrigo", "obs_adenilson", "obs_rodrigo",
                    "sugestao_auto", "consenso"])
        for i in desc:
            w.writerow([i, mapa[i]["chave"], ca[i][0], cb[i][0], ca[i][1], cb[i][1], mapa[i]["sugestao_auto"], ""])
    with open(os.path.join(OUT, "classificacao_consolidada.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id_cego", "lote", "chave", "adenilson", "rodrigo", "sugestao_auto", "regra_sugestao", "tipo_erro"])
        for i, m in mapa.items():
            w.writerow([i, m["lote"], m["chave"], ca.get(i, ("",))[0], cb.get(i, ("",))[0], m["sugestao_auto"],
                        m["regra_sugestao"], m["tipo_erro"]])

    tot = Counter((ca.get(i, ("",))[0] or "(vazio)") for i in mapa)
    L += ["## Andamento", "",
          "- Discordâncias no núcleo: %d (em `out/discordancias.csv`, coluna `consenso` para preencher)." % len(desc),
          "- Classificações de Adenilson em todas as linhas: " + ", ".join("%s=%d" % kv for kv in sorted(tot.items())),
          ""]
    with open(os.path.join(OUT, "kappa.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
