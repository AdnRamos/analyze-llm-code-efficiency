"""
Step 5b: re-judging after the pipeline fix (run in October 2026).

Submits again, with the same account type and languages, every submission whose code or judging changed with
the corrected pipeline (list produced by validation/check_extraction.py), plus 100 unchanged submissions as a
control for judge drift between 2025 and 2026. Nothing in data/generations or data/submissions is modified.

RUN ON YOUR OWN COMPUTER (LeetCode blocks cloud IPs):
    pip install requests browser_cookie3
    python pipeline/5_submit/rejudge.py --dry-run        # shows the plan, no network
    python pipeline/5_submit/rejudge.py                  # runs (can be interrupted and resumed)
    python pipeline/5_submit/rejudge.py --export         # writes data/rejudging_2026/*.ndjson from the log

Login (tenta nesta ordem, e guarda os cookies em ~/.leetcode_cookies_auditoria.json, fora do repositório):
  1. variáveis de ambiente LEETCODE_SESSION e LEETCODE_CSRFTOKEN;
  2. cookies já guardados de uma execução anterior;
  3. cookies do navegador (browser_cookie3; funciona no Firefox; no Chrome/Edge recentes no Windows
     a criptografia "app-bound" costuma bloquear);
  4. janela de login do Playwright: abre um Chromium, você entra no LeetCode e o script lê os cookies
     (pip install playwright && python -m playwright install chromium);
  5. colar os dois valores à mão (entrada oculta).

Inputs:
  validation/reports/rejudge_plan.jsonl     submissions to re-judge (code from the corrected pipeline)
  validation/reports/rejudge_control.jsonl  100 unchanged submissions, re-judged as a drift control
Local log (append, resumable; not versioned because it contains the account name):
  data/.cache/rejudge_log.ndjson
Published records (--export): data/rejudging_2026/rejudged.ndjson and control.ndjson

Ritmo: 15 s entre submissões e no máximo 450 por conta por dia (UTC). Em limite de taxa (HTTP 429 ou mensagem de
limite), espera com backoff exponencial (1 min, 2, 4 … até 30 min) e continua na MESMA conta.
Sessão expirada no meio da execução: o script percebe, pede cookies novos (sem perder nada) e repete a
tarefa em que parou. Interrompido (Ctrl+C, queda de energia), basta rodar de novo: cada resultado é gravado
assim que chega e o que já foi concluído é pulado; "Timeout" é tentado de novo.
Nada em data/generations ou data/submissions é alterado.
"""
import argparse
import datetime
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORTS = os.path.join(ROOT, "validation", "reports")
OUT = os.path.join(ROOT, "data", ".cache")                  # log local (contém o nome da conta)
PUBLIC = os.path.join(ROOT, "data", "rejudging_2026")
ENTRADAS = [("ressubmissao", os.path.join(REPORTS, "rejudge_plan.jsonl")),
            ("controle", os.path.join(REPORTS, "rejudge_control.jsonl"))]
SAIDA = os.path.join(OUT, "rejudge_log.ndjson")
LANG_API = {"C++": "cpp", "Java": "java", "Python3": "python3"}
LANG_PRETTY = {"C++": "C++", "Java": "Java", "Python3": "Python3"}
SUBMIT_COOLDOWN = 15.0
LIMITE_DIARIO = 450   # por conta e por dia (UTC); as contas pararam em exatamente 500/dia
REQUEST_COOLDOWN = 0.5
MAX_POLL = 120.0
BACKOFF_MAX = 30 * 60
# cookies ficam FORA do repositório, na pasta do usuário
COLAR = False
COOKIE_CACHE = os.path.join(os.path.expanduser("~"), ".leetcode_cookies_auditoria.json")


def chave(r):
    return "%s|%s|%s|%s" % (r["tipo"], r["modelo"], r["linguagem"], r["id"])


def carregar_tarefas():
    tarefas = []
    for tipo, path in ENTRADAS:
        if not os.path.exists(path):
            print("[aviso] não encontrado: %s" % path)
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    r["tipo"] = tipo
                    tarefas.append(r)
    return tarefas


def enviadas_hoje(conta):
    hoje = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    n = 0
    if os.path.exists(SAIDA):
        with open(SAIDA, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    if r.get("conta") == conta and str(r.get("data_utc", "")).startswith(hoje):
                        n += 1
    return n


def feitas():
    ok = set()
    if os.path.exists(SAIDA):
        with open(SAIDA, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    if r.get("status") and r.get("status") != "Timeout":
                        ok.add(chave(r))
    return ok


BLOQ = os.path.join(OUT, "rejudge_blocked_cloudflare.ndjson")
JS = os.path.join(OUT, "submit_in_browser.js")


def carregar_bloqueios():
    d = {}
    if os.path.exists(BLOQ):
        with open(BLOQ, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    d[r["chave"]] = r
    return d


def registrar_bloqueio(t, msg):
    with open(BLOQ, "a", encoding="utf-8") as f:
        f.write(json.dumps({"chave": chave(t), "msg": msg,
                            "data_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}) + "\n")


def gerar_script_navegador():
    """Gera um script para colar no Console (F12) de uma aba logada do leetcode.com. O próprio navegador faz
    as submissões (passa pelo Cloudflare como um uso normal), no mesmo ritmo de 8 s, e baixa um .ndjson."""
    ja = feitas()
    bloq = carregar_bloqueios()
    tarefas = [t for t in carregar_tarefas() if chave(t) in bloq and chave(t) not in ja]
    if not tarefas:
        print("nenhuma tarefa bloqueada pendente.")
        return
    lote = [{"tipo": t["tipo"], "modelo": t["modelo"], "linguagem": t["linguagem"], "id": t["id"], "slug": t["slug"],
             "motivos": t.get("motivos"), "lang": LANG_API[t["linguagem"]], "codigo": t["codigo"]} for t in tarefas]
    js = JS_MODELO.replace("__TAREFAS__", json.dumps(lote, ensure_ascii=False)).replace("__PAUSA__", str(int(SUBMIT_COOLDOWN * 1000)))
    with open(JS, "w", encoding="utf-8") as f:
        f.write(js)
    print("gerado %s com %d tarefas (~%.0f min)." % (JS, len(lote), len(lote) * (SUBMIT_COOLDOWN + 6) / 60))
    print("1. abra https://leetcode.com logado no seu navegador normal, aperte F12 e vá na aba Console;")
    print("2. se o Chrome pedir, digite: allow pasting (ou 'permitir colar') e Enter;")
    print("3. abra o .js num editor, copie TUDO, cole no Console e Enter. Deixe a aba aberta até o fim;")
    print("4. no fim o navegador baixa resultados_navegador.ndjson; rode:")
    print("   python pipeline/5_submit/rejudge.py --importar <caminho do arquivo baixado>")


def importar(path):
    """Aceita o .ndjson baixado pelo navegador OU o conteúdo do localStorage (um array JSON) salvo num arquivo."""
    path = os.path.expandvars(os.path.expanduser(path.strip().strip('"')))
    if not os.path.exists(path):
        sys.exit("Arquivo não encontrado: %s" % path)
    txt = open(path, encoding="utf-8-sig").read().strip()
    linhas = json.loads(txt) if txt.startswith("[") else [json.loads(l) for l in txt.splitlines() if l.strip()]
    ja = feitas()
    novos = 0
    with open(SAIDA, "a", encoding="utf-8") as fo:
        for r in linhas:
            if r.get("status") and r.get("status") != "Timeout" and chave(r) not in ja:
                r["lingua_conferida"] = r.get("lang_pretty") == LANG_PRETTY.get(r["linguagem"])
                fo.write(json.dumps(r, ensure_ascii=False) + "\n")
                ja.add(chave(r))
                novos += 1
    print("lidas %d linhas; importadas %d submissões novas para %s" % (len(linhas), novos, SAIDA))


JS_MODELO = r"""
(async () => {
  const TAREFAS = __TAREFAS__;
  const PAUSA = __PAUSA__;
  const dorme = ms => new Promise(r => setTimeout(r, ms));
  const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1];
  if (!csrf) { console.error("Sem csrftoken: faça login no leetcode.com nesta aba."); return; }
  const H = {"content-type": "application/json", "x-csrftoken": csrf};
  const u = await (await fetch("/graphql", {method: "POST", headers: H,
    body: JSON.stringify({query: "query { userStatus { username isSignedIn } }"})})).json();
  const conta = u.data.userStatus.username;
  if (!u.data.userStatus.isSignedIn) { console.error("Não está logado."); return; }
  const idx = {};
  for (const q of (await (await fetch("/api/problems/all/")).json()).stat_status_pairs) idx[q.stat.question__title_slug] = q.stat.question_id;
  const chaveLS = "auditoria_resultados";
  const out = JSON.parse(localStorage.getItem(chaveLS) || "[]");
  const feitos = new Set(out.map(r => [r.tipo, r.modelo, r.linguagem, r.id].join("|")));
  const num = s => { const m = String(s || "").match(/[\d.]+/); return m ? parseFloat(m[0]) : null; };
  const baixar = () => {
    const b = new Blob([out.map(r => JSON.stringify(r)).join("\n") + "\n"], {type: "application/x-ndjson"});
    const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "resultados_navegador.ndjson"; a.click();
  };
  window.baixarResultados = baixar;
  console.log("conta:", conta, "| tarefas:", TAREFAS.length, "| já feitas nesta aba:", feitos.size,
              "| para baixar a qualquer momento: baixarResultados()");
  let k = 0;
  for (const t of TAREFAS) {
    k++;
    if (feitos.has([t.tipo, t.modelo, t.linguagem, t.id].join("|"))) continue;
    let r;
    try {
      r = await fetch(`/problems/${t.slug}/submit/`, {method: "POST", headers: H,
        body: JSON.stringify({lang: t.lang, question_id: String(idx[t.slug]), typed_code: t.codigo})});
    } catch (e) { console.warn(k, t.slug, "erro de rede", e); await dorme(30000); continue; }
    if (r.status === 429) { console.warn("limite; aguardando 5 min"); await dorme(300000); continue; }
    if (!r.ok) { console.warn(k, t.slug, "HTTP", r.status); await dorme(PAUSA); continue; }
    const sid = (await r.json()).submission_id;
    let d = {}, t0 = Date.now();
    while (Date.now() - t0 < 120000) {
      await dorme(1500);
      d = await (await fetch(`/submissions/detail/${sid}/check/`)).json();
      if (d.state === "SUCCESS") break;
    }
    const st = d.state === "SUCCESS" ? d.status_msg : "Timeout";
    const ok = (st || "").toLowerCase().startsWith("accepted");
    const linha = {tipo: t.tipo, modelo: t.modelo, linguagem: t.linguagem, id: t.id, slug: t.slug, motivos: t.motivos,
      conta, data_utc: new Date().toISOString(), via: "navegador", status: st, aceito: ok, compilou: !!d.run_success,
      tempo_ms: num(d.status_runtime), memoria_mb: num(d.status_memory), testes_passados: d.total_correct,
      total_testes: d.total_testcases, percentil_tempo: d.runtime_percentile, percentil_memoria: d.memory_percentile,
      submission_id: String(sid), lang_pretty: d.pretty_lang};
    if (!ok) Object.assign(linha, {erro_compilacao: d.full_compile_error || d.compile_error || null,
      erro_runtime: d.full_runtime_error || d.runtime_error || null, ultimo_caso_teste: d.last_testcase || null,
      saida_esperada: d.expected_output || null, sua_saida: d.code_output || null});
    out.push(linha);
    localStorage.setItem(chaveLS, JSON.stringify(out));
    console.log(`[${k}/${TAREFAS.length}] ${t.modelo} ${t.linguagem} ${t.slug} -> ${st}`);
    await dorme(PAUSA);
  }
  baixar();
  console.log("fim. Arquivo resultados_navegador.ndjson baixado.");
})();
"""


# ----------------------------------------------------------------------------- rede
class LeetCode:
    def __init__(self):
        import requests
        self.s = requests.Session()
        self.s.headers.update({"user-agent": "Mozilla/5.0", "referer": "https://leetcode.com",
                               "origin": "https://leetcode.com"})
        self._t = 0.0
        self.idx = {}
        self.usuario = None

    def _pace(self, gap=REQUEST_COOLDOWN):
        w = gap - (time.monotonic() - self._t)
        if w > 0:
            time.sleep(w)
        self._t = time.monotonic()

    def get(self, url, **kw):
        self._pace()
        kw.setdefault("timeout", 20)
        return self.s.get(url, **kw)

    def post(self, url, **kw):
        self._pace()
        kw.setdefault("timeout", 20)
        return self.s.post(url, **kw)

    # ---------------------------------------------------------------- login
    def _cookies_navegador(self):
        """browser_cookie3. No Chrome/Edge >= 127 (Windows) a criptografia 'app-bound' costuma impedir a leitura."""
        try:
            import browser_cookie3
        except ImportError:
            print("  [navegador] browser_cookie3 não instalado")
            return None
        for nav in ("firefox", "chrome", "edge", "brave", "chromium"):
            try:
                cj = getattr(browser_cookie3, nav)(domain_name="leetcode.com")
                c = {k.name: k.value for k in cj}
            except Exception as e:
                print("  [navegador] %s: não consegui ler (%s)" % (nav, type(e).__name__))
                continue
            if c.get("LEETCODE_SESSION") and c.get("csrftoken"):
                return c["LEETCODE_SESSION"], c["csrftoken"], "navegador " + nav
            print("  [navegador] %s: sem cookies do LeetCode" % nav)
        return None

    def _cookies_playwright(self):
        """Abre uma janela do Chromium; você faz login (inclusive captcha) e o script lê os cookies dela."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("  [janela] Playwright não instalado (pip install playwright && python -m playwright install chromium)")
            return None
        print("  [janela] abrindo o Chromium: faça login no LeetCode nessa janela; o script continua sozinho.")
        with sync_playwright() as p:
            br = p.chromium.launch(headless=False)
            ctx = br.new_context()
            pg = ctx.new_page()
            pg.goto("https://leetcode.com/accounts/login/")
            t0 = time.time()
            while time.time() - t0 < 600:
                c = {k["name"]: k["value"] for k in ctx.cookies("https://leetcode.com")}
                if c.get("LEETCODE_SESSION") and c.get("csrftoken"):
                    br.close()
                    return c["LEETCODE_SESSION"], c["csrftoken"], "janela de login (Playwright)"
                time.sleep(2)
            br.close()
        print("  [janela] tempo esgotado (10 min) sem login")
        return None

    def _cookies_manual(self):
        import getpass
        print("  [manual] No navegador logado: F12 > Application (Aplicativo) > Cookies > https://leetcode.com")
        limpa = lambda v: v.strip().strip('"').strip("'").strip()
        print("  (no PowerShell, cole com o botão direito do mouse; Ctrl+V pode não funcionar nesse campo oculto)")
        sess = limpa(getpass.getpass("  cole o valor de LEETCODE_SESSION (não aparece na tela): "))
        csrf = limpa(getpass.getpass("  cole o valor de csrftoken: "))
        print("  recebido: LEETCODE_SESSION com %d caracteres, csrftoken com %d" % (len(sess), len(csrf)))
        return (sess, csrf, "colados manualmente") if sess and csrf else None

    def _aplicar(self, sess, csrf):
        self.s.cookies.set("LEETCODE_SESSION", sess, domain=".leetcode.com")
        self.s.cookies.set("csrftoken", csrf, domain=".leetcode.com")
        self.s.headers["x-csrftoken"] = csrf
        r = self.post("https://leetcode.com/graphql", json={"query": "query { userStatus { username isSignedIn } }"})
        self.ultimo_http = r.status_code
        if r.status_code != 200:
            print("  [login] o LeetCode respondeu HTTP %d na verificação do login" % r.status_code)
        try:
            st = (r.json().get("data") or {}).get("userStatus") or {}
        except Exception:
            st = {}
        return st.get("username") if st.get("isSignedIn") else None

    def logado(self):
        try:
            r = self.post("https://leetcode.com/graphql", json={"query": "query { userStatus { isSignedIn } }"})
            if r.status_code != 200:
                return None   # não dá para saber (Cloudflare/erro): não pede login de novo
            return bool(((r.json().get("data") or {}).get("userStatus") or {}).get("isSignedIn"))
        except Exception:
            return False

    def login_por_cookies(self):
        tentativas = []
        if COLAR:
            tentativas += [self._cookies_manual, self._cookies_manual]   # 3 tentativas de colar
        if COLAR:   # --colar: sempre pede cookies novos (troca de conta); ignora cache e variáveis de ambiente
            tentativas.append(self._cookies_manual)
        if not COLAR and os.environ.get("LEETCODE_SESSION") and os.environ.get("LEETCODE_CSRFTOKEN"):
            tentativas.append(lambda: (os.environ["LEETCODE_SESSION"], os.environ["LEETCODE_CSRFTOKEN"], "variáveis de ambiente"))
        if not COLAR and os.path.exists(COOKIE_CACHE):
            def _cache():
                d = json.load(open(COOKIE_CACHE, encoding="utf-8"))
                return d["LEETCODE_SESSION"], d["csrftoken"], "cache local " + COOKIE_CACHE
            tentativas.append(_cache)
        if not COLAR:
            tentativas += [self._cookies_navegador, self._cookies_playwright, self._cookies_manual]
        for f in tentativas:
            try:
                got = f()
            except Exception as e:
                print("  [login] falhou: %s" % e)
                got = None
            if not got:
                continue
            sess, csrf, origem = got
            user = self._aplicar(sess, csrf)
            if user:
                self.usuario = user
                print("[ok] login como %s (cookies: %s)" % (user, origem))
                with open(COOKIE_CACHE, "w", encoding="utf-8") as fo:   # reaproveita na próxima execução
                    json.dump({"LEETCODE_SESSION": sess, "csrftoken": csrf}, fo)
                return
            if getattr(self, "ultimo_http", 200) != 200:
                sys.exit("O LeetCode está recusando a conexão (HTTP %d) antes mesmo de olhar os cookies: é o bloqueio "
                         "de ontem, que ainda não passou. Não é problema da conta nova. Tente de novo mais tarde."
                         % self.ultimo_http)
            print("  [login] cookies de %s não são aceitos pelo LeetCode (sessão expirada?)" % origem)
            if origem == "colados manualmente":
                print("  dica: copie os DOIS valores logo depois de entrar na conta nova (o csrftoken muda a cada login);"
                      " não copie espaços nem aspas.")
        sys.exit("Não consegui login no LeetCode. Veja as mensagens acima.")

    def carregar_indice(self):
        r = self.get("https://leetcode.com/api/problems/all/")
        r.raise_for_status()
        for q in r.json().get("stat_status_pairs", []):
            st = q.get("stat") or {}
            if st.get("question__title_slug"):
                self.idx[st["question__title_slug"]] = st.get("question_id")
        print("[ok] índice: %d questões" % len(self.idx))

    def submeter(self, slug, lang, code):
        """Retorna (submission_id | None, motivo: False | True(limite) | "cloudflare" | "transitorio", msg)."""
        qid = self.idx.get(slug)          # S2: question_id resolvido pelo slug completo
        if qid is None:
            return None, False, "slug não encontrado no índice"
        r = self.post("https://leetcode.com/problems/%s/submit/" % slug,
                      json={"lang": lang, "question_id": str(qid), "typed_code": code})
        txt = r.text[:300]
        if r.status_code == 403 and re.search(r"(?i)just a moment|cloudflare|cf-chl", r.text[:3000]):
            return None, "cloudflare", "HTTP 403 (desafio do Cloudflare)"
        if r.status_code in (499, 500, 502, 503, 504):
            corpo = re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", r.text[:2000])).strip()[:160]
            return None, "transitorio", "HTTP %d %s" % (r.status_code, corpo)
        if r.status_code == 429 or re.search(r"(?i)too many|rate limit|limit exceeded|try again later", txt):
            return None, True, "HTTP %d: %s" % (r.status_code, txt)
        if r.status_code != 200:
            return None, False, "HTTP %d: %s" % (r.status_code, txt)
        try:
            sid = r.json().get("submission_id")
        except Exception:
            sid = None
        return (int(sid) if sid else None), False, txt

    def resultado(self, sid):
        t0, back = time.monotonic(), 1.0
        while time.monotonic() - t0 < MAX_POLL:
            r = self.get("https://leetcode.com/submissions/detail/%d/check/" % sid)
            try:
                d = r.json()
            except Exception:
                time.sleep(2)
                continue
            if d.get("state") == "SUCCESS":
                st = d.get("status_msg")
                ok = (st or "").lower().startswith("accepted")
                out = {"status": st, "aceito": ok, "compilou": bool(d.get("run_success")),
                       "tempo_ms": _num(d.get("status_runtime")), "memoria_mb": _num(d.get("status_memory")),
                       "testes_passados": d.get("total_correct"), "total_testes": d.get("total_testcases"),
                       "percentil_tempo": d.get("runtime_percentile"), "percentil_memoria": d.get("memory_percentile"),
                       "submission_id": str(sid), "lang_pretty": d.get("pretty_lang")}
                if not ok:
                    out.update({"erro_compilacao": d.get("full_compile_error") or d.get("compile_error"),
                                "erro_runtime": d.get("full_runtime_error") or d.get("runtime_error"),
                                "ultimo_caso_teste": d.get("last_testcase"), "saida_esperada": d.get("expected_output"),
                                "sua_saida": d.get("code_output")})
                return out
            time.sleep(back)
            back = min(5.0, back * 1.5)
        return {"status": "Timeout", "aceito": False, "submission_id": str(sid)}


def _num(s):
    m = re.search(r"[\d.]+", str(s or ""))
    return float(m.group()) if m else None


# ----------------------------------------------------------------------------- execução
def exportar():
    """Splits the local log into the published files, without the account name."""
    os.makedirs(PUBLIC, exist_ok=True)
    out = {"ressubmissao": open(os.path.join(PUBLIC, "rejudged.ndjson"), "w", encoding="utf-8"),
           "controle": open(os.path.join(PUBLIC, "control.ndjson"), "w", encoding="utf-8")}
    n = {"ressubmissao": 0, "controle": 0}
    with open(SAIDA, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                t = r.pop("tipo")
                r.pop("conta", None)
                r["via"] = r.get("via") or "script"
                out[t].write(json.dumps(r, ensure_ascii=False) + "\n")
                n[t] += 1
    for fo in out.values():
        fo.close()
    print("rejudged: %d | control: %d -> %s" % (n["ressubmissao"], n["controle"], PUBLIC))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="só mostra o plano, sem rede")
    ap.add_argument("--limite", type=int, default=0, help="para depois de N submissões nesta execução")
    ap.add_argument("--so-controle", action="store_true", help="envia só o grupo de controle")
    ap.add_argument("--colar", action="store_true", help="pula as tentativas automáticas e pede os cookies para colar")
    ap.add_argument("--retentar-bloqueados", action="store_true", help="tenta de novo, por aqui, as bloqueadas pelo Cloudflare")
    ap.add_argument("--gerar-script-navegador", action="store_true",
                    help="gera data/.cache/submit_in_browser.js com as bloqueadas pelo Cloudflare e sai")
    ap.add_argument("--importar", metavar="ARQUIVO", help="importa o .ndjson baixado pelo script do navegador e sai")
    ap.add_argument("--export", action="store_true", help="grava data/rejudging_2026/*.ndjson a partir do log e sai")
    a = ap.parse_args()
    if a.export:
        return exportar()
    if a.gerar_script_navegador:
        return gerar_script_navegador()
    if a.importar:
        return importar(a.importar)
    global COLAR
    COLAR = a.colar

    tarefas = carregar_tarefas()
    if a.so_controle:
        tarefas = [t for t in tarefas if t["tipo"] == "controle"]
    ja = feitas()
    bloq = set() if a.retentar_bloqueados else set(carregar_bloqueios())
    pend = [t for t in tarefas if chave(t) not in ja and chave(t) not in bloq]
    if bloq:
        print("bloqueadas pelo Cloudflare e reservadas para o navegador: %d" % len([t for t in tarefas if chave(t) in bloq and chave(t) not in ja]))
    pend.sort(key=lambda t: (t["tipo"] != "controle", t["slug"], t["modelo"], t["linguagem"]))  # controle primeiro
    print("tarefas: %d | já concluídas: %d | pendentes: %d | tempo estimado: ~%.1f h"
          % (len(tarefas), sum(1 for t in tarefas if chave(t) in ja), len(pend), len(pend) * (SUBMIT_COOLDOWN + 6) / 3600))
    if a.dry_run:
        for t in pend[:5]:
            print("  exemplo:", t["tipo"], t["modelo"], t["linguagem"], t["slug"], t.get("motivos"))
        return

    lc = LeetCode()
    lc.login_por_cookies()
    lc.carregar_indice()
    os.makedirs(OUT, exist_ok=True)
    hoje_conta = enviadas_hoje(lc.usuario)
    print("[conta] %s já enviou %d hoje (limite usado pelo script: %d por dia)" % (lc.usuario, hoje_conta, LIMITE_DIARIO))
    if hoje_conta >= LIMITE_DIARIO:
        sys.exit("Limite diário desta conta atingido. Rode de novo amanhã (UTC); o script continua de onde parou.")
    n, espera, falhas_seguidas, tent_trans, bloqueados, tarefas_trans = 0, 60, 0, 0, 0, 0
    with open(SAIDA, "a", encoding="utf-8") as fo:
        i = 0
        while i < len(pend):
            t = pend[i]
            sid, limite, msg = lc.submeter(t["slug"], LANG_API[t["linguagem"]], t["codigo"])
            if limite == "cloudflare":
                # bloqueio por questão/conteúdo (se repete a cada tentativa): registra e segue; vai pelo navegador
                registrar_bloqueio(t, msg)
                bloqueados += 1
                print("[cloudflare] %s %s %s — registrado para envio pelo navegador" % (t["modelo"], t["linguagem"], t["slug"]))
                i += 1
                time.sleep(SUBMIT_COOLDOWN)
                continue
            if limite == "transitorio":
                tent_trans += 1
                if tent_trans <= 3:
                    print("[%s] erro temporário; nova tentativa em 30 s (%d/3)" % (msg[:120], tent_trans))
                    time.sleep(30)
                    continue
                tent_trans = 0
                tarefas_trans += 1
                if tarefas_trans >= 2:
                    # o erro persiste em tarefas diferentes: é limite do servidor/conta, não da questão.
                    # espera (sem pular tarefas e sem trocar de conta) e tenta a MESMA tarefa de novo
                    if espera >= 8 * 60:
                        sys.exit("O LeetCode continua recusando as submissões depois de ~15 min de pausas (%s). "
                                 "Isso indica bloqueio da conexão/limite diário: pare por algumas horas (ou até amanhã) "
                                 "e rode de novo; nada se perde." % msg[:60])
                    print("[pausa] o LeetCode recusa todas as submissões (%s); aguardando %d min"
                          % (msg[:60], espera // 60))
                    time.sleep(espera)
                    espera = min(BACKOFF_MAX, espera * 2)
                    continue
                print("[falha] %s %s %s: %s após 3 tentativas — fica pendente" % (t["modelo"], t["linguagem"], t["slug"], msg[:80]))
                i += 1
                time.sleep(SUBMIT_COOLDOWN)
                continue
            tent_trans = 0
            if sid:
                tarefas_trans = 0
            if limite:
                print("[limite] %s — aguardando %d min e tentando de novo na mesma conta" % (msg[:80], espera // 60))
                time.sleep(espera)
                espera = min(BACKOFF_MAX, espera * 2)
                continue
            if sid:
                espera = 60
            if not sid and lc.logado() is False:
                # sessão expirou no meio da execução: pede login de novo e repete a MESMA tarefa
                print("[sessão] o LeetCode encerrou a sessão; é preciso renovar os cookies.")
                try:
                    os.remove(COOKIE_CACHE)
                except OSError:
                    pass
                lc.login_por_cookies()
                hoje_conta = enviadas_hoje(lc.usuario)
                if hoje_conta >= LIMITE_DIARIO:
                    sys.exit("Limite diário da conta %s atingido. Rode de novo amanhã." % lc.usuario)
                continue
            if not sid:
                falhas_seguidas += 1
                print("[falha] %s %s %s: %s" % (t["modelo"], t["linguagem"], t["slug"], msg[:120]))
                if falhas_seguidas >= 10:
                    sys.exit("10 falhas seguidas: verifique o login e rode de novo (retoma de onde parou).")
                i += 1
                time.sleep(SUBMIT_COOLDOWN)
                continue
            falhas_seguidas = 0
            res = lc.resultado(sid)
            linha = {"tipo": t["tipo"], "modelo": t["modelo"], "linguagem": t["linguagem"], "id": t["id"],
                     "slug": t["slug"], "motivos": t.get("motivos"), "conta": lc.usuario,
                     "data_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), **res,
                     "lingua_conferida": res.get("lang_pretty") == LANG_PRETTY[t["linguagem"]]}
            fo.write(json.dumps(linha, ensure_ascii=False) + "\n")
            fo.flush()
            n += 1
            hoje_conta += 1
            print("[%d/%d] %s %s %s -> %s%s" % (i + 1, len(pend), t["modelo"], t["linguagem"], t["slug"], res["status"],
                                                "" if linha["lingua_conferida"] else "  (ATENÇÃO: julgado como %s)" % res.get("lang_pretty")))
            i += 1
            if hoje_conta >= LIMITE_DIARIO:
                print("Limite diário de %d submissões da conta %s atingido. Para seguir com outra conta: "
                      "python pipeline/5_submit/rejudge.py --colar" % (LIMITE_DIARIO, lc.usuario))
                break
            if a.limite and n >= a.limite:
                print("limite de %d atingido; rode de novo para continuar." % a.limite)
                break
            time.sleep(SUBMIT_COOLDOWN)
    print("fim desta execução: %d submissões gravadas em %s" % (n, SAIDA))
    if bloqueados or os.path.exists(BLOQ):
        print("bloqueadas pelo Cloudflare (total no arquivo): %d — quando terminar o resto, rode:" % len(carregar_bloqueios()))
        print("  python pipeline/5_submit/rejudge.py --gerar-script-navegador")


if __name__ == "__main__":
    main()
