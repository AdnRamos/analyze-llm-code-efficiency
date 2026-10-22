"""
Grupo de controle da ressubmissão: 100 submissões cujo código NÃO muda com o pipeline corrigido,
reenviadas como estavam, para medir a deriva do juiz do LeetCode entre 2025 e a ressubmissão
(testes novos, versão de linguagem). Estratificado por linguagem e por aceito/não aceito; semente fixa.
Saída: validation/reports/rejudge_control.jsonl (entrada de pipeline/5_submit/rejudge.py)
"""
import csv, json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import triage as T  # noqa: E402
csv.field_size_limit(10 ** 9)
SEED, POR_CELULA = 20261016, {"C++": (17, 17), "Java": (17, 16), "Python3": (17, 16)}  # (aceitas, não aceitas) = 100


def main():
    with open(os.path.join(HERE, "reports", "extraction", "plano_ressubmissao.csv"), encoding="utf-8-sig", newline="") as f:
        plano = [r for r in csv.DictReader(f) if r["submetido"] == "sim" and r["ressubmeter"] == "nao"]
    qs, specs, gen, subs = T.carregar()
    sub = {(s["modelo"], s["linguagem"], int(s["id_questao"])): s for s in subs}
    rng = random.Random(SEED); sel = []
    for lg, (na, nn) in POR_CELULA.items():
        for aceito, n in ((True, na), (False, nn)):
            pool = sorted([r for r in plano if r["linguagem"] == lg and (r["status_original"] == "Accepted") == aceito],
                          key=lambda r: (r["modelo"], int(r["id"])))
            sel += rng.sample(pool, n)
    with open(os.path.join(HERE, "reports", "rejudge_control.jsonl"), "w", encoding="utf-8") as f:
        for r in sel:
            k = (r["modelo"], r["linguagem"], int(r["id"]))
            code = T.reconstruir(gen[k], sub[k]["ts_epoch"])[0]
            f.write(json.dumps({"modelo": k[0], "linguagem": k[1], "id": k[2], "slug": r["slug"],
                                "motivos": ["controle"], "status_original": r["status_original"], "codigo": code},
                               ensure_ascii=False) + "\n")
    print("controle: %d" % len(sel))


if __name__ == "__main__":
    main()
