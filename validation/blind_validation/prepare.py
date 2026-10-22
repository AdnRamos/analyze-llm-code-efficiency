"""
Fase 3 (versão reduzida): validação humana das regras automáticas da triagem.

Substitui a classificação manual de 960 casos. Sorteia 100 submissões NÃO aceitas, estratificadas pelo
grau de incerteza da regra automática, e gera UMA planilha cega (sem modelo, sem sugestão, sem flags):

  estrato                          n   de onde vem
  A_confirmado_mecanicamente       20  sugestão A e o pipeline corrigido (validation/check_extraction.py) produz código aderente
                                       ou o motivo é linguagem/questão errada
  A_nao_confirmado                 20  sugestão A sem confirmação mecânica (casos mistos)
  B                                25  sugestão B
  C_formato_sensivel               25  sugestão C em veredito sensível a formato (CE em C++/Java, RE em Python)
  indefinido                       10  sugestão indefinido

Saídas: validation/blind_validation/validacao_regras.xlsx (para preencher) e validation/blind_validation/validacao_mapa_cego.csv.
Se os dois autores preencherem cópias da mesma planilha, validar.py também calcula o kappa entre eles.
Uso: python validation/blind_validation/preparar_validacao.py   (requer openpyxl; rodar depois de validation/check_extraction.py/corrigir_pipeline.py)
"""
import csv
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VALID = os.path.dirname(HERE)
sys.path.insert(0, VALID)
sys.path.insert(0, HERE)
import triage as triagem  # noqa: E402
import sheets as P  # noqa: E402

SEED = 20261014
COTAS = [("A_confirmado_mecanicamente", 20), ("A_nao_confirmado", 20), ("B", 25),
         ("C_formato_sensivel", 25), ("indefinido", 10)]
csv.field_size_limit(10 ** 9)


def estrato(r):
    sug = r["sugestao_triagem"]
    if sug == "A":
        mec = ("lingua_errada" in r["motivos"] or "questao_errada" in r["motivos"] or r["aderente_novo"] == "sim")
        return "A_confirmado_mecanicamente" if mec else "A_nao_confirmado"
    if sug == "B":
        return "B"
    if sug == "C":
        sens = (r["linguagem"] in ("C++", "Java") and r["status_original"] == "Compile Error") or \
               (r["linguagem"] == "Python3" and r["status_original"] == "Runtime Error")
        return "C_formato_sensivel" if sens else None
    if sug == "indefinido":
        return "indefinido"
    return None


def main():
    plano = P.ler_csv(os.path.join(VALID, "reports", "extraction", "plano_ressubmissao.csv"))
    por = {}
    for r in plano:
        if r["submetido"] == "sim" and r["status_original"] != "Accepted":
            e = estrato(r)
            if e:
                por.setdefault(e, []).append(r)
    rng = random.Random(SEED)
    sel = []
    for e, n in COTAS:
        pool = sorted(por.get(e, []), key=lambda r: (r["modelo"], r["linguagem"], int(r["id"])))
        sel += [(e, r) for r in rng.sample(pool, min(n, len(pool)))]
    rng.shuffle(sel)

    qs, specs, gen, subs = triagem.carregar()
    sub = {(s["modelo"], s["linguagem"], int(s["id_questao"])): s for s in subs}
    linhas, mapa = [], []
    for i, (e, r) in enumerate(sel, 1):
        key = (r["modelo"], r["linguagem"], int(r["id"]))
        g, s = gen[key], sub[key]
        recon = triagem.reconstruir(g, s.get("ts_epoch"))[0] or ""
        erro = s.get("erro_runtime") or s.get("erro_compilacao") or ""
        spec = specs[key[2]][key[1]]
        id_cego = "V-%03d" % i
        linhas.append([id_cego, key[1], s["slug"], P.assinatura(spec), s["status"], P.corta(erro),
                       P.corta(g.get("resposta")), P.corta(recon), "", "", ""])
        mapa.append([id_cego, e, "%s|%s|%d" % key, r["sugestao_triagem"], r["regra_triagem"],
                     r["aderente_novo"], r["motivos"]])
    P.CAB[1] = "linguagem"
    P.LARG[1] = 10
    P.INSTRUCOES[2] = ("O que fazer", "Para cada uma das 100 linhas da aba 'Classificar', leia a resposta bruta "
                       "do modelo, o código que foi submetido e o erro do LeetCode, e preencha a coluna amarela "
                       "'categoria' (A/B/C/?). Observação é opcional. Leva de 1 a 2 horas.")
    P.INSTRUCOES[3] = ("Classificação cega", "A planilha não mostra o modelo, a sugestão automática nem as flags. "
                       "Não abra validacao_mapa_cego.csv antes de terminar.")
    P.INSTRUCOES[-1] = ("Depois", "Salve com o mesmo nome. O script validation/blind_validation/score.py compara sua "
                        "classificação com as regras automáticas, por estrato, com intervalos de Wilson.")
    P.escrever_xlsx(os.path.join(HERE, "validacao_regras.xlsx"), "(seu nome)", linhas)
    with open(os.path.join(HERE, "validacao_mapa_cego.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id_cego", "estrato", "chave", "sugestao_auto", "regra", "aderente_pipeline_corrigido", "motivos"])
        w.writerows(mapa)
    print("validação: %d linhas;" % len(linhas), {e: sum(1 for x, _ in sel if x == e) for e, _ in COTAS})


if __name__ == "__main__":
    main()
