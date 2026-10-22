"""
Checks the extraction step: applies the corrected extractor and wrapper (pipeline/lib/extraction.py) to every raw
response and compares the result with the code that was judged in 2025. NÃO submete nada e não altera data/.
Every submission whose code changes, or that was judged in another language/problem, goes to
validation/reports/rejudge_plan.jsonl, the input of pipeline/5_submit/rejudge.py.

Aplica um extrator + wrapper corrigidos às saídas brutas existentes (campo `resposta`) e compara
com o código que foi efetivamente submetido (reconstruído por validation/triage.py).

Regras corrigidas (definidas ANTES de olhar resultados e independentes do veredito):
  E1  Remove blocos <think>…</think> (e um <think> não fechado até o fim) antes de procurar código.
  E2  O rótulo do template só é reconhecido no início de linha (`solution:` com decoração markdown
      opcional). Não casa mais com o "Solution:" de `class Solution:`.
  E3  Região = do rótulo (ou do início, se não houver rótulo) até o próximo rótulo do template.
      Na região: 2+ cercas -> conteúdo entre as duas primeiras; 1 cerca -> o texto antes dela (se houver;
      é o fechamento de um bloco aberto antes do rótulo) ou depois dela (cerca aberta); sem cerca na região ->
      primeiro bloco cercado da resposta, se houver e se não contiver o próprio rótulo;
      senão o texto da região. Região vazia -> primeiro bloco cercado completo depois do rótulo.
      A escolha não depende de o código parsear ou de seguir o starter.
  E4  Preserva o recuo da primeira linha (só remove linhas em branco nas pontas) e aplica dedent.
  E5  Não remove imports/includes (o código vai como o modelo escreveu).
  W1  Python: se a classe esperada (Solution ou a classe de design do starter) não está declarada,
      move para dentro dela as funções de nível de módulo cujo 1º parâmetro é `self`; imports e classes
      auxiliares ficam no módulo. Código que não parseia é envolvido inteiro (como no pipeline original).
      C++/Java: sem wrapper (igual ao pipeline original).
  S1  Linguagem da submissão = linguagem da resposta (corrige as 389 julgadas como C++).
  S2  question_id resolvido pelo slug completo (corrige a questão 650 julgada como a questão 2).

Saídas:
  validation/reports/extraction/plano_ressubmissao.csv   uma linha por submissão (10.666) + as 422 não submetidas
  validation/reports/rejudge_plan.jsonl                  código novo das submissões a rejulgar
  validation/reports/extraction/RELATORIO.md             resumo, confirmação mecânica dos casos A

Uso: python validation/check_extraction.py   (depois de validation/triage.py)
"""
import collections
import csv
import json
import os
import re
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import triage as T  # noqa: E402
from lib.extraction import extract_code, wrap_python  # noqa: E402  (o MESMO extrator usado pelo pipeline)

OUT = os.path.join(HERE, "reports", "extraction")
PLAN = os.path.join(HERE, "reports", "rejudge_plan.jsonl")
csv.field_size_limit(10 ** 9)

def extrair_corrigido(resposta):
    return extract_code(resposta)


def wrapper_corrigido(code, ling, spec):
    return wrap_python(code, ling, spec)


def aderencia(code, ling, spec):
    if ling == "Python3":
        return T.py_strict(code, spec)
    return "sim" if T.cj_adherent(code, spec, True) else "nao"


def norm(c):
    return "\n".join(l.rstrip() for l in (c or "").strip("\n").split("\n"))


def main():
    os.makedirs(OUT, exist_ok=True)
    qs, specs, gen, subs = T.carregar()
    tri = {}
    with open(os.path.join(HERE, "reports", "triage", "triagem_submissoes.csv"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            tri[(r["modelo"].replace("/", "_"), r["linguagem"], int(r["id"]))] = r

    linhas, codigos = [], []
    sub_keys = set()
    for s in subs:
        key = (s["modelo"], s["linguagem"], int(s["id_questao"]))
        sub_keys.add(key)
        g, ling, spec = gen[key], s["linguagem"], specs[int(s["id_questao"])][s["linguagem"]]
        antigo = T.reconstruir(g, s.get("ts_epoch"))[0] or ""
        ext, origem = extrair_corrigido(g.get("resposta"))
        novo, acao = wrapper_corrigido(ext, ling, spec)
        t = tri[key]
        motivos = []
        if norm(novo) != norm(antigo):
            motivos.append("codigo_mudou")
        if t["lingua_errada"] == "sim":
            motivos.append("lingua_errada")
        if t["questao_errada_juiz"] == "sim":
            motivos.append("questao_errada")
        ad_ant = aderencia(antigo, ling, spec)
        ad_novo = aderencia(novo, ling, spec)
        linhas.append({
            "modelo": s["modelo"], "linguagem": ling, "id": key[2], "slug": s["slug"], "status_original": s["status"],
            "sugestao_triagem": t["sugestao"], "regra_triagem": t["regra_sugestao"],
            "origem_extracao": origem, "acao_wrapper": acao,
            "aderente_antigo": ad_ant, "aderente_novo": ad_novo,
            "ressubmeter": "sim" if motivos else "nao", "motivos": ";".join(motivos), "submetido": "sim",
        })
        if motivos:
            codigos.append({"modelo": s["modelo"], "linguagem": ling, "id": key[2], "slug": s["slug"],
                            "motivos": motivos, "codigo": novo})

    # 422 respostas nunca submetidas (categoria 'invalid' na geração): só informativo
    for key, g in gen.items():
        if key in sub_keys:
            continue
        ling, spec = key[1], specs[key[2]][key[1]]
        ext, origem = extrair_corrigido(g.get("resposta"))
        novo, acao = wrapper_corrigido(ext, ling, spec)
        linhas.append({
            "modelo": key[0], "linguagem": ling, "id": key[2], "slug": qs[key[2]]["slug"], "status_original": "(não submetida)",
            "sugestao_triagem": "", "regra_triagem": "", "origem_extracao": origem, "acao_wrapper": acao,
            "aderente_antigo": "", "aderente_novo": aderencia(novo, ling, spec) if novo.strip() else "vazio",
            "ressubmeter": "decisao_autores", "motivos": "nunca_submetida", "submetido": "nao",
        })

    cab = list(linhas[0].keys())
    with open(os.path.join(OUT, "plano_ressubmissao.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cab)
        w.writeheader()
        w.writerows(linhas)
    with open(PLAN, "w", encoding="utf-8") as f:
        for c in codigos:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    relatorio(linhas)


def tabela(cab, rows):
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def relatorio(linhas):
    S = [l for l in linhas if l["submetido"] == "sim"]
    N = [l for l in linhas if l["submetido"] == "nao"]
    C = collections.Counter
    L = ["# Fase 4 — dry-run do pipeline corrigido (Revisor A, ponto A1)", "",
         "Gerado por `validation/check_extraction.py` (Python %s). **Nada foi submetido.** "
         "Regras E1–E5, W1, S1 e S2 no cabeçalho do script.\n" % sys.version.split()[0]]

    L += ["## 1. O que mudaria", ""]
    rows = []
    for lg in T.LANGS + ["TODAS"]:
        sel = [l for l in S if lg == "TODAS" or l["linguagem"] == lg]
        c = C(l["ressubmeter"] for l in sel)
        m = C(x for l in sel for x in l["motivos"].split(";") if x)
        rows.append([lg, len(sel), c["sim"], m["codigo_mudou"], m["lingua_errada"], m["questao_errada"]])
    L.append(tabela(["Linguagem", "Submissões", "A ressubmeter", "código mudou", "linguagem errada", "questão errada"], rows))

    L += ["### Por veredito original (Python3)", ""]
    rows = []
    for st in T.STATUS_ORDER:
        sel = [l for l in S if l["linguagem"] == "Python3" and l["status_original"] == st]
        if sel:
            rows.append([st, len(sel), sum(l["ressubmeter"] == "sim" for l in sel),
                         sum(l["aderente_antigo"] == "sim" for l in sel), sum(l["aderente_novo"] == "sim" for l in sel)])
    L.append(tabela(["Veredito", "n", "a ressubmeter", "aderente (antigo)", "aderente (corrigido)"], rows))

    L += ["## 2. Confirmação mecânica das sugestões da triagem (não aceitas)", "",
          "Um caso sugerido como A é **confirmado mecanicamente** quando o motivo é linguagem/questão errada, "
          "ou quando o código produzido pelo pipeline corrigido é aderente ao driver (Python: parseia e tem a "
          "classe/métodos/aridade do starter; C++/Java: cabeçalho), sem gerar código novo.\n"]
    rows = []
    for lg in T.LANGS:
        for sg in ("A", "B", "C", "indefinido"):
            sel = [l for l in S if l["linguagem"] == lg and l["sugestao_triagem"] == sg]
            if not sel:
                continue
            conf = [l for l in sel if ("lingua_errada" in l["motivos"] or "questao_errada" in l["motivos"]
                                       or l["aderente_novo"] == "sim")]
            rows.append([lg, sg, len(sel), len(conf), "%.1f%%" % (100 * len(conf) / len(sel)),
                         sum(l["ressubmeter"] == "sim" for l in sel)])
    L.append(tabela(["Linguagem", "Sugestão", "n", "corrigido aderente / motivo mecânico", "%", "a ressubmeter"], rows))
    L.append("Para B e C, a coluna mostra quantos ficariam aderentes com o pipeline corrigido: em B espera-se "
             "pouco (a falha é do modelo); valores altos em B indicam regra da triagem a revisar.\n")

    L += ["## 3. Respostas nunca submetidas (422)", "",
          "Informativo: com o extrator corrigido, quantas das 422 respostas classificadas como `invalid` na geração "
          "teriam código aderente. Submetê-las muda o denominador do artigo; é decisão dos autores.\n"]
    rows = [[lg, sum(1 for l in N if l["linguagem"] == lg),
             sum(1 for l in N if l["linguagem"] == lg and l["aderente_novo"] == "sim")] for lg in T.LANGS]
    L.append(tabela(["Linguagem", "não submetidas", "aderentes com o extrator corrigido"], rows))

    L += ["## 4. Para a ressubmissão (Fase 4 propriamente dita — exige confirmação)", "",
          "- `codigo_corrigido.jsonl` tem o código exato a enviar para cada linha com `ressubmeter=sim`.",
          "- Mesma conta, mesmas linguagens, registro de data; checar a versão do Python no LeetCode.",
          "- Ressubmeter também os casos cujo código mudou sem ser A (ex.: imports preservados), para que todo o "
          "conjunto passe pelo mesmo pipeline.", ""]
    with open(os.path.join(OUT, "RELATORIO.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
