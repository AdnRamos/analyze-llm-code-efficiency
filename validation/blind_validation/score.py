"""
Compara uma classificação cega (padrão: validacao_regras_llm.xlsx, preenchida por um classificador LLM sem acesso
ao mapa, às flags e às sugestões; ver validacao_classificacao_llm.csv) com as regras automáticas da triagem.

Uso: python validation/blind_validation/score.py [planilha.xlsx [planilha_do_segundo_autor.xlsx]]
Saída: validation/blind_validation/out/validacao.md — concordância humano × regra por estrato e no total (IC de Wilson 95%),
matriz de confusão e, se houver duas planilhas, o kappa de Cohen entre os autores.
"""
import csv
import math
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kappa import CATS, fmt, kappa, ler_planilha, tabela_confusao  # noqa: E402


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def main():
    p1 = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "validacao_regras_llm.xlsx")
    h1 = ler_planilha(p1)
    h2 = ler_planilha(sys.argv[2]) if len(sys.argv) > 2 else None
    with open(os.path.join(HERE, "validacao_mapa_cego.csv"), encoding="utf-8-sig", newline="") as f:
        mapa = {r["id_cego"]: r for r in csv.DictReader(f)}
    ok = {i: h1[i][0] for i in mapa if h1.get(i, ("",))[0] in CATS}
    L = ["# Validação das regras automáticas por classificação cega", "",
         "**Classificador: modelo de linguagem sem acesso ao mapa, às flags e às sugestões (não é validação humana).** "
         "Na tabela, \"humano\" deve ser lido como \"classificador\".\n",
         "Gerado por `validation/blind_validation/score.py`. Linhas classificadas: %d de %d ('?' conta como discordância).\n"
         % (len(ok), len(mapa)),
         "| Estrato | n | humano = regra | % | IC 95% (Wilson) |", "|---|---|---|---|---|"]
    estratos = sorted({m["estrato"] for m in mapa.values()})
    tot_k = tot_n = 0
    # 'indefinido' não tem regra a validar: entra só na distribuição humana (abaixo)
    for e in [x for x in estratos if x != "indefinido"] + ["TOTAL (sem indefinido)"]:
        ids = [i for i in ok if mapa[i]["estrato"] != "indefinido" and (e.startswith("TOTAL") or mapa[i]["estrato"] == e)]
        k = sum(ok[i] == mapa[i]["sugestao_auto"] for i in ids)
        lo, hi = wilson(k, len(ids))
        L.append("| %s | %d | %d | %s | %.1f%% a %.1f%% |" % (e, len(ids), k,
                 ("%.1f%%" % (100 * k / len(ids))) if ids else "-", max(0, 100 * lo), 100 * hi))
    pares = [(mapa[i]["sugestao_auto"], ok[i]) for i in ok if mapa[i]["estrato"] != "indefinido"]
    res = kappa(pares, CATS)
    L += ["", "## Regra × humano", "", "- " + fmt(res), ""]
    if res:
        L += [tabela_confusao(res, CATS, "Regra", "Humano"), ""]
    if h2:
        pr = [(h1[i][0], h2[i][0]) for i in mapa if h1.get(i, ("",))[0] in CATS and h2.get(i, ("",))[0] in CATS]
        L += ["## Concordância entre os dois autores", "", "- " + fmt(kappa(pr, CATS)), ""]
    L += ["## Distribuição humana por estrato", ""]
    for e in estratos:
        c = Counter(ok[i] for i in ok if mapa[i]["estrato"] == e)
        L.append("- %s: %s" % (e, ", ".join("%s=%d" % kv for kv in sorted(c.items()))))
    os.makedirs(os.path.join(os.path.dirname(HERE), "reports", "blind_validation"), exist_ok=True)
    with open(os.path.join(os.path.dirname(HERE), "reports", "blind_validation", "validacao.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
