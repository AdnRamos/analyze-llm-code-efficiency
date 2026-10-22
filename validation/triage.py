#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Triagem automatica (Fase 2, Revisor A, ponto A1).

Aplica as regras de validation/CRITERIA.md a cada submissao (modelo x linguagem x questao):
reconstroi o codigo submetido, calcula as flags F1-F16 e sugere A/B/C/indefinido/aceita.
Somente biblioteca padrao (Python >= 3.10). Escreve apenas em validation/reports/triage/.
Analisa as submissoes JULGADAS EM 2025: o codigo enviado e reconstruido a partir de `code_2025`
(validation/audit_2025/code_2025.jsonl, juntado ao cache por build_cache.py).

Uso: python validation/build_cache.py && python validation/triage.py
"""
import ast
import csv
import collections
import datetime
import json
import os
import random
import re
import sys
import textwrap
import time
import warnings

warnings.simplefilter("ignore")
sys.setrecursionlimit(10000)
csv.field_size_limit(10 ** 9)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from lib.paths import CACHE as _CACHE, SAMPLE_CSV as _SAMPLE  # noqa: E402  (honours STUDY_DATA_DIR)
CACHE = str(_CACHE / "validation")
OUT = os.path.join(HERE, "reports", "triage")
SAMPLE_CSV = str(_SAMPLE)
SEED = 20261012

UTC = datetime.timezone.utc
# submit_missing.py passa a valer a partir de 2025-10-13 UTC (CRITERIOS.md)
TS_SCRIPT_MISSING = datetime.datetime(2025, 10, 13, tzinfo=UTC).timestamp()
# commit 6cbda464: reconstrucao incerta antes disso (CRITERIOS.md)
TS_INCERTA = datetime.datetime(2025, 9, 17, 20, 34, tzinfo=UTC).timestamp()
DATA_INCERTA = datetime.date(2025, 10, 9)

LANGS = ["C++", "Java", "Python3"]
STATUS_ORDER = ["Accepted", "Compile Error", "Wrong Answer", "Runtime Error",
                "Time Limit Exceeded", "Memory Limit Exceeded", "Timeout"]
SUGS = ["A", "B", "C", "indefinido", "aceita"]

# ----------------------------------------------------------------------------
# Pipeline real (copiado de src/, nao reinventado)
# ----------------------------------------------------------------------------
# --- reavaliar_extracao.py (apenas as funcoes usadas para localizar candidatos) ---
_KNOWN_LANG_TAGS = {
    "c", "cpp", "c++", "cc", "h", "hpp", "java", "python", "python3", "py", "go", "javascript", "js", "typescript", "ts",
    "csharp", "c#", "cs", "rust", "rs", "ruby", "rb", "php", "swift", "kotlin", "scala", "perl", "pl", "r", "julia",
    "solidity", "sol", "dart", "zig", "lua", "haskell", "hs", "ocaml", "ml", "shell", "bash", "sh", "powershell", "ps1",
    "sql", "mysql", "postgresql"
}
_FENCE_RE = re.compile(r"(?is)(?P<fence>`{3,}|~{3,})(?P<inner>.*?)(?P=fence)")
_LABELS_PATTERN = r"(?i)\n\s*(efficiency:|time complexity:|space complexity:|energy implications:|explanation:)"


def _looks_like_lang_tag(line0):
    t = line0.strip().lower()
    if " " in t:
        return False
    t = t.strip(" :;,.")
    return t in _KNOWN_LANG_TAGS


# --- submit_problems.py (usado ate 2025-10-12 UTC) ---
def is_valid_code(code):
    return bool(code and code.strip())


def ensure_python_solution_wrapper_problems(slug, codigo):
    if "class Solution" not in codigo:
        body = "\n".join(("    " + line if line.strip() else line) for line in codigo.splitlines())
        return "class Solution:\n" + body + ("\n" if not body.endswith("\n") else "")
    return codigo


def try_extract_code_from_resposta(resposta):
    if not resposta:
        return None
    m = re.search(r"```(?:[a-zA-Z0-9+#]*)\s*([\s\S]*?)```", resposta)
    if m:
        return m.group(1).strip()
    return None


# --- submit_missing.py (a partir de 2025-10-13 UTC) ---
def _ensure_indented_body(code):
    lines = code.splitlines()
    out = []
    pending = False
    for i, line in enumerate(lines):
        out.append(line)
        if re.match(r"^\s*def\s+\w+\(.*\):\s*$", line):
            pending = True
            continue
        if pending:
            if line.strip() == "" or not line.startswith((" ", "\t")):
                out.insert(len(out) - 1, "    pass")
                pending = False
            else:
                pending = False
    if pending:
        out.append("    pass")
    return "\n".join(out) + ("\n" if not code.endswith("\n") else "")


def ensure_python_solution_wrapper_missing(slug, codigo):
    code = codigo.rstrip("\n") + "\n"
    if "class Solution" not in code:
        body = "\n".join(("    " + line if line.strip() else "") for line in code.splitlines())
        code = "class Solution:\n" + body + ("\n" if not body.endswith("\n") else "")
    code = _ensure_indented_body(code)
    return code


def reconstruir(g, ts_epoch):
    """Reconstroi o codigo enviado ao LeetCode. Retorna (codigo|None, script, wrapped)."""
    script = "submit_missing" if ts_epoch >= TS_SCRIPT_MISSING else "submit_problems"
    codigo = g.get("code_2025", g.get("code"))   # codigo extraido em 2025
    if not is_valid_code(codigo):
        codigo = try_extract_code_from_resposta(g.get("resposta", ""))
    if not is_valid_code(codigo):
        return None, script, False
    wrapped = False
    if g["linguagem"] == "Python3":
        wrapped = "class Solution" not in (codigo if script == "submit_problems" else codigo.rstrip("\n") + "\n")
        if script == "submit_missing":
            codigo = ensure_python_solution_wrapper_missing(g.get("slug", ""), codigo)
        else:
            codigo = ensure_python_solution_wrapper_problems(g.get("slug", ""), codigo)
    return codigo, script, wrapped


# ----------------------------------------------------------------------------
# Utilitarios de texto
# ----------------------------------------------------------------------------
def balanced(s, idx, open_ch="(", close_ch=")"):
    """Conteudo entre o parentese em s[idx] e o seu par; (conteudo, indice_apos) ou (None, idx)."""
    depth = 0
    for j in range(idx, len(s)):
        c = s[j]
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return s[idx + 1:j], j + 1
    return None, idx


def split_top(s, angle=False):
    """Divide por virgulas no nivel superior, respeitando () [] {} e (opcionalmente) <>."""
    parts, depth, cur = [], 0, []
    opens = "([{" + ("<" if angle else "")
    closes = ")]}" + (">" if angle else "")
    prev = ""
    for c in s:
        if c in opens:
            depth += 1
        elif c in closes and not (c == ">" and prev == "-"):
            depth -= 1
        if c == "," and depth <= 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        prev = c
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def strip_think(text):
    t = re.sub(r"(?is)<think>.*?</think>", "", text)
    i = t.lower().find("<think>")
    if i >= 0:
        t = t[:i]
    j = t.lower().rfind("</think>")
    if j >= 0:
        t = t[j + len("</think>"):]
    return t


def think_content(text):
    parts = re.findall(r"(?is)<think>(.*?)(?:</think>|$)", text)
    j = text.lower().find("</think>")
    if "<think>" not in text.lower() and j >= 0:
        parts.append(text[:j])
    return "\n".join(parts)


def clean_block(inner):
    inner = inner.strip("\n\r\t ")
    lines = inner.splitlines()
    if lines and _looks_like_lang_tag(lines[0]):
        lines = lines[1:]
    return "\n".join(lines).strip()


_LABEL_SOL = re.compile(r"(?im)^[ \t*#_>\-]*solution[ \t*_]*:[ \t]*")


def candidatos_bruto(resposta):
    """Candidatos da resposta bruta (CRITERIOS.md): blocos cercados + trecho apos o rotulo
    'solution:' (somente quando sem cerca), com <think> removido."""
    t = strip_think(resposta)
    cands = []
    last_end = 0
    for m in _FENCE_RE.finditer(t):
        c = clean_block(m.group("inner"))
        if c:
            cands.append(c)
        last_end = m.end()
    rest = t[last_end:]
    m = re.search(r"`{3,}|~{3,}", rest)
    if m:  # cerca aberta e nunca fechada (resposta truncada)
        tail = re.split(_LABELS_PATTERN, rest[m.end():], maxsplit=1)[0]
        c = clean_block(tail)
        if c:
            cands.append(c)
    m_sol = _LABEL_SOL.search(t)
    section = t[m_sol.end():] if m_sol else t
    trecho = re.split(_LABELS_PATTERN, section, maxsplit=1)[0].strip()
    if trecho and not re.search(r"`{3,}|~{3,}", trecho):
        cands.append(trecho)
    seen, out = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


# ----------------------------------------------------------------------------
# Esperado por questao (starter) e aderencia ao driver (F14)
# ----------------------------------------------------------------------------
KW = {"if", "for", "while", "switch", "catch", "return", "sizeof", "else", "do", "new", "throw"}


def strip_cj_comments(s):
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    s = re.sub(r"//[^\n]*", " ", s)
    return s


def strip_cj_literals(s):
    s = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', s)
    s = re.sub(r"'(?:\\.|[^'\\\n])*'", "''", s)
    return s


def parse_py_starter(s):
    m = re.search(r"(?m)^class\s+(\w+)", s)
    cls = m.group(1) if m else None
    methods = {}
    for mm in re.finditer(r"(?m)^[ \t]+def\s+(\w+)\s*\(", s):
        content, _ = balanced(s, mm.end() - 1)
        if content is None:
            continue
        names = split_top(content)
        if names and names[0].split(":")[0].split("=")[0].strip() in ("self", "cls"):
            names = names[1:]
        methods.setdefault(mm.group(1), len(names))
    return {"cls": cls, "methods": methods}


def cj_param_count(content):
    ps = split_top(content, angle=True)
    if len(ps) == 1 and ps[0] == "void":
        ps = []
    required = sum(1 for p in ps if "=" not in p)
    varargs = any("..." in p for p in ps)
    return required, len(ps), varargs


def cj_methods(code):
    """Todas as 'definicoes' de metodo: lista (nome, obrigatorios, total, varargs)."""
    res = []
    for m in re.finditer(r"(?<![\w.])([A-Za-z_]\w*)\s*\(", code):
        name = m.group(1)
        if name in KW:
            continue
        pre = code[max(0, m.start() - 2):m.start()]
        if pre.endswith("->"):
            continue
        content, end = balanced(code, m.end() - 1)
        if content is None:
            continue
        tail = code[end:end + 80]
        if re.match(r"\s*(?:const\b\s*)?(?:noexcept\b\s*)?(?:override\b\s*)?(?:final\b\s*)?(?:throws\b[^{;]*)?(?:->[^{;]*)?\{", tail) \
                or re.match(r"\s*(?:noexcept\b\s*)?:(?!:)", tail):
            req, tot, va = cj_param_count(content)
            res.append((name, req, tot, va))
    return res


def parse_cj_starter(s):
    s = strip_cj_comments(s)
    m = re.search(r"\b(?:class|struct)\s+(\w+)", s)
    cls = m.group(1) if m else None
    methods = {}
    for name, req, tot, va in cj_methods(s):
        methods.setdefault(name, tot)
    return {"cls": cls, "methods": methods}


def cj_adherent(code, spec, need_class=True, implicit_ctor=False):
    t = strip_cj_literals(strip_cj_comments(code))
    cls = spec["cls"]
    if need_class and not re.search(r"\b(?:class|struct)\s+" + re.escape(cls) + r"\b", t):
        return False
    defs = cj_methods(t)
    for name, k in spec["methods"].items():
        if implicit_ctor and name == cls and k == 0:
            continue
        ok = False
        for n, req, tot, va in defs:
            if n == name and (va or req <= k <= tot):
                ok = True
                break
        if not ok:
            return False
    return True


def safe_parse(code):
    try:
        return ast.parse(code)
    except Exception:
        return None


def _arity_ok(fn, k):
    a = fn.args
    pos = list(a.posonlyargs) + list(a.args)
    decos = [ast.unparse(d) for d in fn.decorator_list]
    skip = 0 if any(d.endswith("staticmethod") for d in decos) else 1
    if len(pos) < skip:
        return bool(a.vararg)
    total = len(pos) - skip
    required = max(0, len(pos) - len(a.defaults) - skip)
    if any(d is None for d in a.kw_defaults):
        return False
    return bool(a.vararg) or (required <= k <= total)


def py_tree_adherent(tree, spec, implicit_ctor=False):
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == spec["cls"]]
    if not classes:
        return False
    defs = {}
    for n in classes[-1].body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs[n.name] = n
    for name, k in spec["methods"].items():
        if implicit_ctor and name == "__init__" and k == 0 and name not in defs:
            continue
        fn = defs.get(name)
        if fn is None or not _arity_ok(fn, k):
            return False
    return True


def py_strict(code, spec):
    """'sim'/'nao'/'nao_parseavel'"""
    tree = safe_parse(code)
    if tree is None:
        return "nao_parseavel"
    return "sim" if py_tree_adherent(tree, spec) else "nao"


def _is_docstring(n):
    return isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)


def py_tolerant(code, spec, implicit_ctor=False):
    """Candidato so com metodos (self) que, envolvidos na classe esperada, ficam aderentes."""
    c = textwrap.dedent(code)
    tree = safe_parse(c)
    if tree is None:
        return False
    if any(isinstance(n, ast.ClassDef) and n.name == spec["cls"] for n in tree.body):
        return False
    funcs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not funcs:
        return False
    for n in tree.body:
        if not (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Import, ast.ImportFrom)) or _is_docstring(n)):
            return False
    for n in funcs:
        if n.name in spec["methods"] and not (n.args.args and n.args.args[0].arg == "self"):
            return False
    wrapped = "class " + spec["cls"] + ":\n" + "\n".join(("    " + l if l.strip() else "") for l in c.splitlines()) + "\n"
    t2 = safe_parse(wrapped)
    return t2 is not None and py_tree_adherent(t2, spec, implicit_ctor)


_BENIGN_SIMPLE = (ast.Assign, ast.AnnAssign, ast.AugAssign)


def module_stmts(tree):
    """Instrucoes de nivel de modulo 'nao benignas' (testes/print/input soltos): lista de strings."""
    out = []
    for n in tree.body:
        if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Import, ast.ImportFrom, ast.Pass)):
            continue
        if _is_docstring(n):
            continue
        if isinstance(n, _BENIGN_SIMPLE):
            val = getattr(n, "value", None)
            if val is None or not any(isinstance(x, ast.Call) for x in ast.walk(val)):
                continue
        try:
            out.append(ast.unparse(n))
        except Exception:
            out.append(ast.dump(n))
    return out


# ----------------------------------------------------------------------------
# Parsing de mensagens de erro e validacao da reconstrucao
# ----------------------------------------------------------------------------
def norm_ws(x):
    return re.sub(r"\s+", " ", x).strip()


_CARET = re.compile(r"^\s*[\^~\-\s]*$")


def py_frames(err):
    """[(N, eco|None)] na ordem do traceback do LeetCode (mais interno primeiro)."""
    lines = err.split("\n")
    fr = []
    for i, l in enumerate(lines):
        m = re.match(r"^Line (\d+)\b(?!:)", l)
        if not m:
            continue
        echo = None
        if i - 1 >= 1:
            p = lines[i - 1]
            if p.strip() and not _CARET.match(p) and not p.lstrip().startswith("[Previous line") and not p.startswith("Line "):
                echo = p
        fr.append((int(m.group(1)), echo))
    return fr


def cpp_pairs(err):
    """Pares (N, eco) somente de diagnosticos do arquivo do usuario ('Line N: Char M: ...' seguido de 'N | texto');
    notas de cabecalhos (./precompiled/X.h:7:7, /usr/lib/...) nao entram."""
    out = []
    for m in re.finditer(r"(?m)^Line (\d+): Char \d+: [^\n]*\n\s*(\d+) \|(.*)$", err):
        if m.group(1) == m.group(2):
            out.append((int(m.group(1)), m.group(3)))
    return out


def java_pairs(err):
    """Pares (N, eco) dos erros no arquivo do usuario; erros marcados '[in __Driver__.java]' sao do driver."""
    out = []
    for m in re.finditer(r"(?m)^Line (\d+): error:([^\n]*)\n([^\n]*)\n", err):
        if re.search(r"\[in [^\]]+\]\s*$", m.group(2)):
            continue
        out.append((int(m.group(1)), m.group(3)))
    return out


def validar_reconstrucao(s, recon):
    """sim/nao/sem_info: linha N do erro bate com a linha N reconstruida (eco da linha)."""
    if recon is None:
        return "sem_info"
    err = s.get("erro_runtime") if s.get("erro_runtime") else s.get("erro_compilacao")
    if not err:
        return "sem_info"
    rl = recon.splitlines()
    if re.search(r"(?m)^\s*\d+ \|", err):
        pairs = cpp_pairs(err)
    elif re.search(r"(?m)^Line \d+: error:", err) and not re.search(r"(?m)^Line \d+: Char", err):
        pairs = java_pairs(err)
    else:
        pairs = [(n, e) for n, e in py_frames(err) if e is not None]
    cmp = [(n, e) for n, e in pairs if 1 <= n <= len(rl)]
    if not cmp:
        return "sem_info"
    for n, e in cmp:
        if norm_ws(e) != norm_ws(rl[n - 1]):
            return "nao"
    return "sim"


def primeiro_frame_py(err):
    fr = py_frames(err or "")
    return fr[0][0] if fr else None


def linha_dentro_da_classe(code, tree, n, cls):
    """True se a linha n (1-based) esta dentro da classe cls (nivel de modulo)."""
    if tree is not None:
        cs = [x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == cls]
        if not cs:
            return False
        c = cs[-1]
        return c.lineno <= n <= (c.end_lineno or c.lineno)
    lines = code.splitlines()
    idx = None
    for i, l in enumerate(lines):
        if re.match(r"class\s+" + re.escape(cls) + r"\b", l):
            idx = i
    if idx is None or n - 1 < idx:
        return False
    if n - 1 == idx:
        return True
    for j in range(idx + 1, n):
        l = lines[j]
        if l.strip() and not l[0].isspace() and not l.lstrip().startswith("#"):
            return False
    return True


# ----------------------------------------------------------------------------
# Tipo de erro
# ----------------------------------------------------------------------------
def tipo_erro(s):
    st = s["status"]
    if st == "Runtime Error":
        e = s.get("erro_runtime") or ""
        first = e.split("\n", 1)[0].strip()
        m = re.match(r"^([A-Za-z_][\w.]*?(?:Error|Exception|Exit|Interrupt))\b", first)
        if m:
            return m.group(1).split(".")[-1]
        m = re.search(r"AddressSanitizer:\s*([\w-]+)", e)
        if m:
            return "AddressSanitizer:" + m.group(1)
        m = re.search(r"runtime error:\s*([A-Za-z ]+)", e)
        if m:
            return "UBSan:" + m.group(1).strip()
        m = re.search(r"terminate called after throwing an instance of '([^']+)'", e)
        if m:
            return m.group(1)
        return re.sub(r"^Line \d+(: Char \d+)?:\s*", "", first)[:80]
    if st == "Compile Error":
        e = s.get("erro_compilacao") or ""
        first = e.split("\n", 1)[0].strip()
        return re.sub(r"^Line \d+(: Char \d+)?:\s*", "", first)[:120]
    return ""


# ----------------------------------------------------------------------------
# Flags textuais
# ----------------------------------------------------------------------------
LC_CLASSES = {"ListNode", "TreeNode", "Node", "Employee", "NestedInteger", "Interval", "Point", "MountainArray",
              "ArrayReader", "BinaryMatrix", "Master", "Robot", "Sea", "Reader", "ImmutableListNode", "Quad",
              "Plane", "Relation", "VersionControl"}
_CLASS_RE = re.compile(r"(?m)^[ \t]*(?:(?:public|private|protected|static|final|abstract)\s+)*(?:class|struct)\s+(\w+)")


def classes_definidas(code):
    return _CLASS_RE.findall(code)


_LABEL_LINE = re.compile(r"(?im)^[ \t*#_>\-]*(solution|efficiency|time complexity|space complexity|energy implications|explanation)\s*:")


def residuo(code):
    t = []
    if "```" in code or "~~~" in code:
        t.append("cerca")
    if _LABEL_LINE.search(code):
        t.append("rotulo")
    return "+".join(t)


_CODE_START = re.compile(r"^\s*(return|if|elif|else|for|while|def|class|import|from|print|try|except|finally|with|pass|break|"
                         r"continue|raise|assert|yield|lambda|del|global|nonlocal|public|private|protected|static|int|long|"
                         r"double|float|bool|boolean|char|string|String|vector|void|auto|using|struct|template|case|switch|"
                         r"do|new|throw|this|self|const|unsigned|List|Map|Set|ListNode|TreeNode)\b|^\s*(#|//|\*|/\*|@|\}|\{)")
_PROSE_BAD = re.compile(r"[=;{}\[\]<>+*/%&|^~(]")


def tem_prosa(code):
    c = re.sub(r'("""|\'\'\').*?\1', " ", code, flags=re.S)
    c = re.sub(r"/\*.*?\*/", " ", c, flags=re.S)
    for l in c.splitlines():
        s = l.strip()
        if len(s) < 20 or _CODE_START.match(s) or _PROSE_BAD.search(s):
            continue
        words = s.split()
        if len(words) < 5 or not words[0][0].isalpha():
            continue
        if sum(1 for w in words if re.fullmatch(r"[A-Za-z'.,:!?\-]+", w)) / len(words) >= 0.85:
            return True
    return False


def f13(resposta, code_field, submetido):
    t = []
    low = resposta.lower()
    if "<think>" in low or "</think>" in low:
        t.append("think")
        tc = think_content(resposta)
        if code_field and len(code_field.strip()) >= 10 and code_field.strip() in tc:
            t.append("code_em_think")
    if submetido and tem_prosa(submetido):
        t.append("prosa")
    return "+".join(t) if t else "nao"


# ----------------------------------------------------------------------------
# Carga
# ----------------------------------------------------------------------------
def carregar():
    with open(SAMPLE_CSV, encoding="utf-8", newline="") as f:
        qs = {int(r["id"]): r for r in csv.DictReader(f)}
    specs = {}
    for qid, r in qs.items():
        sc = ast.literal_eval(r["starter_code"])
        specs[qid] = {
            "Python3": parse_py_starter(sc["python3"]),
            "C++": parse_cj_starter(sc["cpp"]),
            "Java": parse_cj_starter(sc["java"]),
        }
    gen = {}
    with open(os.path.join(CACHE, "gen_all.jsonl"), encoding="utf-8") as f:
        for line in f:
            g = json.loads(line)
            gen[(g["modelo"].replace("/", "_"), g["linguagem"], int(g["id"]))] = g
    subs = []
    with open(os.path.join(CACHE, "sub_all.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                subs.append(json.loads(line))
    return qs, specs, gen, subs


# ----------------------------------------------------------------------------
# Processamento de uma submissao
# ----------------------------------------------------------------------------
def bruto_adherence(cands, spec, py, implicit_ctor):
    """(estrito_ok, tolerante_ok_sem_estrito, algum_parseia, instrucoes_de_modulo_do_melhor_candidato)."""
    strict_ok = tol_ok = any_parse = False
    best_key, best_mods = None, None
    for i, c in enumerate(cands):
        if py:
            tr = safe_parse(c)
            if tr is None:
                tr = safe_parse(textwrap.dedent(c))
            if tr is not None:
                any_parse = True
            if tr is not None and py_tree_adherent(tr, spec, implicit_ctor):
                strict_ok = True
                ms = module_stmts(tr)
                key = (0, len(ms), i)
                if best_key is None or key < best_key:
                    best_key, best_mods = key, ms
            elif py_tolerant(c, spec, implicit_ctor):
                tol_ok = True
                tr2 = safe_parse(textwrap.dedent(c))
                ms = module_stmts(tr2) if tr2 is not None else []
                key = (1, len(ms), i)
                if best_key is None or key < best_key:
                    best_key, best_mods = key, ms
        else:
            if cj_adherent(c, spec, True, implicit_ctor):
                strict_ok = True
            elif cj_adherent(c, spec, False, implicit_ctor):
                tol_ok = True
    return strict_ok, (tol_ok and not strict_ok), any_parse, best_mods


def processar(s, g, q, spec_all):
    ling = s["linguagem"]
    qid = int(s["id_questao"])
    spec = spec_all[ling]
    py = ling == "Python3"
    resposta = g.get("resposta") or ""
    code_field = g.get("code_2025", g.get("code")) or ""
    ts = s["ts_epoch"]
    st = s["status"]
    err = s.get("erro_runtime") or s.get("erro_compilacao") or ""

    r = collections.OrderedDict()
    r["modelo"] = g["modelo"]
    r["linguagem"] = ling
    r["id"] = qid
    r["slug"] = s.get("slug") or q["slug"]
    r["dificuldade"] = q["dificuldade"]
    r["status"] = st
    r["tipo_erro"] = tipo_erro(s)
    r["lang_julgada"] = s.get("lang_pretty") or ""

    recon, script, wrapped = reconstruir(g, ts)
    d = datetime.datetime.fromtimestamp(ts, UTC)
    r["script_submissao"] = script
    r["recon_incerta"] = "sim" if (ts < TS_INCERTA or d.date() == DATA_INCERTA or recon is None) else "nao"
    r["recon_validada"] = validar_reconstrucao(s, recon) if st != "Accepted" else "sem_info"
    r["classe_esperada"] = spec["cls"]
    eh_design = spec["cls"] != "Solution"
    r["eh_design"] = "sim" if eh_design else "nao"

    # F1
    r["n_blocos_bruto"] = len(_FENCE_RE.findall(resposta))

    cands = candidatos_bruto(resposta)
    sub_tree = None
    mods = None
    if py:
        sub_tree = safe_parse(recon) if recon is not None else None
        r["final_parseia"] = "sim" if sub_tree is not None else "nao"
        mods = module_stmts(sub_tree) if sub_tree is not None else None
        r["stmts_modulo"] = len(mods) if mods is not None else ""
    else:
        r["final_parseia"] = "n/a"
        r["stmts_modulo"] = "n/a"

    # F4
    f4 = "n/a"
    n_err = None
    if py and st == "Runtime Error" and (s.get("lang_pretty") in (None, "Python3")):
        n_err = primeiro_frame_py(s.get("erro_runtime"))
        if recon is None or n_err is None:
            f4 = "sem_info"
        elif n_err > len(recon.splitlines()):
            f4 = "driver"
        else:
            f4 = "nao" if linha_dentro_da_classe(recon, sub_tree, n_err, spec["cls"]) else "sim"
    r["erro_fora_classe"] = f4
    r["erro_linha"] = n_err if n_err is not None else ""

    # F5, F6, F7, F8
    m5 = re.search(r"AttributeError: '(\w+)' object has no attribute", s.get("erro_runtime") or "")
    r["attr_error_solution"] = "sim" if (m5 and m5.group(1) in ("Solution", spec["cls"])) else "nao"
    m6 = re.search(r"NameError: name '([^']+)' is not defined", s.get("erro_runtime") or "")
    r["nameerror_nome"] = m6.group(1) if m6 else ""
    defs = classes_definidas(recon) if recon else []
    redef = sorted({c for c in defs if c in LC_CLASSES and c != spec["cls"]})
    r["redefine_classe_lc"] = "sim" if redef else "nao"
    r["redefine_nomes"] = ";".join(redef)
    r["excecao"] = r["tipo_erro"] if st == "Runtime Error" else ""

    # F9
    cls_re = re.compile(r"\b(?:class|struct)\s+" + re.escape(spec["cls"]) + r"\b")
    r["cabecalho_perdido"] = "sim" if (cls_re.search(resposta) and not cls_re.search(code_field)) else "nao"
    # F10
    lp = s.get("lang_pretty")
    r["lingua_errada"] = "sem_info" if not lp else ("sim" if lp != ling else "nao")
    # F17: questao errada no juiz. Reproduz o bug de submit_problems.resolve_question/get_question_id:
    # um slug que comeca com "<digitos>-" (ex.: '2-keys-keyboard') e lido como frontend id ('2'), e o
    # question_id enviado e o de OUTRA questao (o driver chama addTwoNumbers). Deterministico pelo slug.
    r["questao_errada_juiz"] = "sim" if re.match(r"^\d+[-_].+$", (s.get("slug") or "").lower()) else "nao"
    # F11
    r["design_envelopada"] = ("sim" if (eh_design and wrapped) else "nao") if py else "n/a"
    # F12
    res = residuo(recon) if recon else ""
    r["residuo_rotulo_cerca"] = "sim" if res else "nao"
    r["residuo_tipo"] = res
    # F13
    r["think_ou_prosa"] = f13(resposta, code_field, recon)

    # F14
    strict_ok, tol_ok, any_parse, best_mods = bruto_adherence(cands, spec, py, False)
    if py:
        r["ader_bruto_estrito"] = "sim" if strict_ok else ("nao" if any_parse else "nao_parseavel")
        r["ader_bruto_tolerante"] = "sim" if (strict_ok or tol_ok) else ("nao" if any_parse else "nao_parseavel")
        r["ader_extraido"] = py_strict(code_field, spec) if code_field.strip() else "nao_parseavel"
        r["ader_submetido"] = py_strict(recon, spec) if recon is not None else "nao_parseavel"
    else:
        # C++/Java: CRITERIOS.md define 'tolerante' so para Python (metodos com self). Resposta so com metodos
        # (sem classe) e AMBIGUA em C++/Java: valor 'so_metodos', tratado como indefinido na sugestao.
        r["ader_bruto_estrito"] = "sim" if strict_ok else "nao"
        r["ader_bruto_tolerante"] = "sim" if strict_ok else ("so_metodos" if tol_ok else "nao")
        r["ader_extraido"] = "sim" if cj_adherent(code_field, spec, True) else "nao"
        r["ader_submetido"] = "sim" if (recon is not None and cj_adherent(recon, spec, True)) else "nao"
    # informativo: bruto aderente se um construtor implicito (0 parametros) fosse aceito
    r["_bruto_ctor_implicito"] = "nao"
    if r["ader_bruto_tolerante"] != "sim" and (("__init__" if py else spec["cls"]) in spec["methods"]) \
            and spec["methods"].get("__init__" if py else spec["cls"]) == 0:
        s2, t2, _, _ = bruto_adherence(cands, spec, py, True)
        if s2 or (py and t2):
            r["_bruto_ctor_implicito"] = "sim"
    # F16
    r["bruto_tem_candidato_valido"] = "sim" if r["ader_bruto_tolerante"] == "sim" else "nao"

    sug, regra = sugerir(r, mods, best_mods)
    r["sugestao"] = sug
    r["regra_sugestao"] = regra
    r["_resposta"] = resposta
    r["_submetido"] = recon if recon is not None else ""
    r["_erro"] = err
    return r


def sugerir(r, mods, best_mods):
    if r["status"] == "Accepted":
        return "aceita", "0"
    if r["lingua_errada"] == "sim":
        return "A", "1"
    if r["questao_errada_juiz"] == "sim":
        return "A", "1b"
    if r["ader_bruto_tolerante"] == "so_metodos":
        return "indefinido", "7"
    bruto_ok = r["ader_bruto_tolerante"] == "sim"
    sub_ok = r["ader_submetido"] == "sim"
    if bruto_ok and not sub_ok:
        return "A", "2"
    if r["cabecalho_perdido"] == "sim" and bruto_ok:
        return "A", "3"
    if not bruto_ok:
        return "B", "4"
    # bruto aderente e submetido aderente a partir daqui
    if r["linguagem"] == "Python3" and mods and r["erro_fora_classe"] == "sim":
        if best_mods is not None and set(mods) <= set(best_mods):
            return "B", "5"
        # instrucoes soltas que NAO estavam no melhor candidato: caso misto (CRITERIOS.md, intro)
        return "indefinido", "7"
    if sub_ok:
        return "C", "6"
    return "indefinido", "7"


# ----------------------------------------------------------------------------
# Saidas
# ----------------------------------------------------------------------------
TRIAGEM_COLS = [
    "modelo", "linguagem", "id", "slug", "dificuldade", "status", "tipo_erro", "lang_julgada", "script_submissao",
    "recon_incerta", "recon_validada", "classe_esperada", "eh_design", "n_blocos_bruto", "final_parseia",
    "stmts_modulo", "erro_fora_classe", "erro_linha", "attr_error_solution", "nameerror_nome", "redefine_classe_lc",
    "redefine_nomes", "excecao", "cabecalho_perdido", "lingua_errada", "design_envelopada", "residuo_rotulo_cerca",
    "residuo_tipo", "think_ou_prosa", "ader_bruto_estrito", "ader_bruto_tolerante", "ader_extraido", "ader_submetido",
    "bruto_tem_candidato_valido", "questao_errada_juiz", "sugestao", "regra_sugestao",
]


def write_csv(path, header, rows, bom=False):
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def chave(r):
    return "%s|%s|%d" % (r["modelo"], r["linguagem"], r["id"])


FLAGS = [
    ("F1_n_blocos_bruto", lambda r: "0" if r["n_blocos_bruto"] == 0 else ("1" if r["n_blocos_bruto"] == 1 else "2+")),
    ("F2_final_parseia", lambda r: r["final_parseia"]),
    ("F3_stmts_modulo", lambda r: r["stmts_modulo"] if r["stmts_modulo"] in ("", "n/a") else ("0" if r["stmts_modulo"] == 0 else ">0")),
    ("F4_erro_fora_classe", lambda r: r["erro_fora_classe"]),
    ("F5_attr_error_solution", lambda r: r["attr_error_solution"]),
    ("F6_nameerror", lambda r: "sim" if r["nameerror_nome"] else "nao"),
    ("F7_redefine_classe_lc", lambda r: r["redefine_classe_lc"]),
    ("F8_excecao", lambda r: r["excecao"] or "(nao RE)"),
    ("F9_cabecalho_perdido", lambda r: r["cabecalho_perdido"]),
    ("F10_lingua_errada", lambda r: r["lingua_errada"]),
    ("F11_design_envelopada", lambda r: r["design_envelopada"]),
    ("F12_residuo_rotulo_cerca", lambda r: r["residuo_rotulo_cerca"]),
    ("F13_think_ou_prosa", lambda r: r["think_ou_prosa"]),
    ("F14_ader_bruto_estrito", lambda r: r["ader_bruto_estrito"]),
    ("F14_ader_bruto_tolerante", lambda r: r["ader_bruto_tolerante"]),
    ("F14_ader_extraido", lambda r: r["ader_extraido"]),
    ("F14_ader_submetido", lambda r: r["ader_submetido"]),
    ("F15_recon_incerta", lambda r: r["recon_incerta"]),
    ("F16_bruto_tem_candidato_valido", lambda r: r["bruto_tem_candidato_valido"]),
    ("F17_questao_errada_juiz", lambda r: r["questao_errada_juiz"]),
    ("recon_validada", lambda r: r["recon_validada"]),
    ("script_submissao", lambda r: r["script_submissao"]),
    ("eh_design", lambda r: r["eh_design"]),
]
ST_SHORT = [("Accepted", "Accepted"), ("Compile Error", "CE"), ("Wrong Answer", "WA"), ("Runtime Error", "RE"),
            ("Time Limit Exceeded", "TLE"), ("Memory Limit Exceeded", "MLE"), ("Timeout", "Timeout")]


def resumo_por_flag(rows):
    cnt = collections.defaultdict(collections.Counter)
    for r in rows:
        for fname, fn in FLAGS:
            for lg in (r["linguagem"], "TODAS"):
                c = cnt[(fname, str(fn(r)), lg)]
                c["total"] += 1
                c["st:" + r["status"]] += 1
                c["sug:" + r["sugestao"]] += 1
    hdr = ["flag", "valor", "linguagem", "total"] + [a for _, a in ST_SHORT] + ["sug_" + x for x in SUGS]
    out = []
    for key in sorted(cnt, key=lambda k: (k[0], k[2] == "TODAS", k[2], k[1])):
        c = cnt[key]
        out.append(list(key) + [c["total"]] + [c["st:" + s] for s, _ in ST_SHORT] + [c["sug:" + x] for x in SUGS])
    return hdr, out


def resumo_por_modelo(rows):
    cnt = collections.defaultdict(collections.Counter)
    for r in rows:
        c = cnt[(r["modelo"], r["linguagem"])]
        c["n"] += 1
        c["st:" + r["status"]] += 1
        c["sug:" + r["sugestao"]] += 1
    hdr = ["modelo", "linguagem", "n"] + [a for _, a in ST_SHORT] + ["sug_" + x for x in SUGS]
    out = []
    for k in sorted(cnt):
        c = cnt[k]
        out.append([k[0], k[1], c["n"]] + [c["st:" + s] for s, _ in ST_SHORT] + [c["sug:" + x] for x in SUGS])
    return hdr, out


def resumo_por_questao(rows, qs):
    by = collections.defaultdict(dict)
    for r in rows:
        by[r["id"]][(r["modelo"], r["linguagem"])] = r
    out = []
    for qid in sorted(qs):
        d = by.get(qid, {})
        models = sorted({m for (m, _) in d})
        falha_py = py_re = 0
        sugc = collections.Counter()
        for m in models:
            p, c, j = d.get((m, "Python3")), d.get((m, "C++")), d.get((m, "Java"))
            if not (p and c and j):
                continue
            if p["status"] != "Accepted" and c["status"] == "Accepted" and j["status"] == "Accepted":
                falha_py += 1
                if p["status"] == "Runtime Error":
                    py_re += 1
                sugc[p["sugestao"]] += 1
        eh = next(iter(d.values()))["eh_design"] if d else ""
        row = [qid, qs[qid]["slug"], qs[qid]["dificuldade"], eh, len(models)]
        for lg in LANGS:
            row.append(sum(1 for m in models if (m, lg) in d and d[(m, lg)]["status"] != "Accepted"))
        for lg in LANGS:
            row.append(sum(1 for m in models if (m, lg) in d and d[(m, lg)]["status"] == "Accepted"))
        row += [falha_py, py_re] + [sugc[x] for x in ("A", "B", "C", "indefinido")]
        row.append("sim" if falha_py >= 5 else "")
        out.append(row)
    hdr = ["id", "slug", "dificuldade", "eh_design", "n_modelos_submetidos",
           "nao_aceitas_C++", "nao_aceitas_Java", "nao_aceitas_Python3",
           "aceitas_C++", "aceitas_Java", "aceitas_Python3",
           "n_modelos_py_falha_e_cpp_java_passam", "dos_quais_py_RE",
           "py_falha_sug_A", "py_falha_sug_B", "py_falha_sug_C", "py_falha_sug_indefinido", "destaque(>=5 modelos)"]
    out.sort(key=lambda x: (-x[11], x[0]))
    return hdr, out


def resumo_reconstrucao(rows):
    cnt = collections.defaultdict(collections.Counter)
    for r in rows:
        for key in ((r["linguagem"], r["script_submissao"], "todas"),
                    (r["linguagem"], r["script_submissao"], "recon_incerta=" + r["recon_incerta"]),
                    (r["linguagem"], "(ambos)", "todas"), ("(todas)", "(ambos)", "todas")):
            if r["status"] == "Accepted":
                cnt[key]["aceita_sem_erro"] += 1
            else:
                cnt[key][r["recon_validada"]] += 1
            cnt[key]["n"] += 1
    hdr = ["linguagem", "script", "estrato", "n_total", "n_aceitas_sem_erro_para_validar", "sim", "nao", "sem_info",
           "taxa_validacao_entre_com_info"]
    out = []
    for k in sorted(cnt):
        c = cnt[k]
        com = c["sim"] + c["nao"]
        out.append([k[0], k[1], k[2], c["n"], c["aceita_sem_erro"], c["sim"], c["nao"], c["sem_info"],
                    ("%.4f" % (c["sim"] / com)) if com else ""])
    return hdr, out


def amostra_fase3(rows):
    rnd = random.Random(SEED)
    py_re = [r for r in rows if r["linguagem"] == "Python3" and r["status"] == "Runtime Error"]

    def obrig(r):
        return r["n_blocos_bruto"] > 1 or r["final_parseia"] == "nao" or r["erro_fora_classe"] == "sim" or r["redefine_classe_lc"] == "sim"

    todos = [r for r in py_re if obrig(r)]
    resto = [r for r in py_re if not obrig(r)]
    by = collections.defaultdict(list)
    for r in resto:
        by[r["modelo"]].append(r)
    total_alvo = 100
    models = sorted(by)
    n_resto = len(resto)
    quotas, fr = {}, []
    for m in models:
        exact = total_alvo * len(by[m]) / n_resto if n_resto else 0
        quotas[m] = min(len(by[m]), int(exact))
        fr.append((exact - int(exact), m))
    falta = min(total_alvo, n_resto) - sum(quotas.values())
    for _, m in sorted(fr, key=lambda x: (-x[0], x[1])):
        if falta <= 0:
            break
        if quotas[m] < len(by[m]):
            quotas[m] += 1
            falta -= 1
    sel = []
    for m in models:
        lst = sorted(by[m], key=lambda r: r["id"])
        sel += rnd.sample(lst, quotas[m])
    sel.sort(key=lambda r: (r["modelo"], r["id"]))
    todos.sort(key=lambda r: (r["modelo"], r["id"]))
    hdr = ["chave", "grupo", "flags_principais", "sugestao", "regra_sugestao", "trecho_bruto_sem_think_1500",
           "codigo_submetido_reconstruido_1500", "erro_600", "classe_adenilson", "classe_rodrigo", "obs"]
    out = []
    for grupo, lst in (("obrigatorio_F1>1_F2_F4_F7", todos), ("amostra_estratificada", sel)):
        for r in lst:
            fl = "F1=%s;F2=%s;F3=%s;F4=%s;F5=%s;F6=%s;F7=%s;F8=%s;F9=%s;F10=%s;F11=%s;F12=%s;F13=%s;F14=%s/%s/%s/%s;F16=%s" % (
                r["n_blocos_bruto"], r["final_parseia"], r["stmts_modulo"], r["erro_fora_classe"], r["attr_error_solution"],
                r["nameerror_nome"] or "-", r["redefine_classe_lc"], r["excecao"], r["cabecalho_perdido"], r["lingua_errada"],
                r["design_envelopada"], r["residuo_rotulo_cerca"], r["think_ou_prosa"], r["ader_bruto_estrito"],
                r["ader_bruto_tolerante"], r["ader_extraido"], r["ader_submetido"], r["bruto_tem_candidato_valido"])
            out.append([chave(r), grupo, fl, r["sugestao"], r["regra_sugestao"], strip_think(r["_resposta"]).strip()[:1500],
                        r["_submetido"][:1500], r["_erro"][:600], "", "", ""])
    return hdr, out, len(todos), len(sel), len(resto)


EXPECT = {
    "C++": {"Accepted": 1718, "Compile Error": 413, "Wrong Answer": 1099, "Runtime Error": 160,
            "Time Limit Exceeded": 118, "Memory Limit Exceeded": 11, "Timeout": 3},
    "Java": {"Accepted": 1665, "Compile Error": 500, "Wrong Answer": 1094, "Runtime Error": 142,
             "Time Limit Exceeded": 126, "Memory Limit Exceeded": 8, "Timeout": 1},
    "Python3": {"Accepted": 1171, "Compile Error": 380, "Wrong Answer": 693, "Runtime Error": 1259,
                "Time Limit Exceeded": 76, "Memory Limit Exceeded": 7, "Timeout": 22},
}
EXPECT_TOTAL = {"C++": 3522, "Java": 3536, "Python3": 3608}


def md_table(hdr, rows):
    s = "| " + " | ".join(hdr) + " |\n|" + "|".join("---" for _ in hdr) + "|\n"
    for r in rows:
        s += "| " + " | ".join(str(x) for x in r) + " |\n"
    return s


def relatorio(rows, gen, subs, join_ok, amostra_info, tempo, extras):
    L = []
    A = L.append
    A("# Relatório da triagem (Fase 2, Revisor A, ponto A1)\n")
    A("Gerado por `validation/triage.py` (Python %s). Todos os números abaixo saem do script; semente de amostragem %d.\n" % (sys.version.split()[0], SEED))
    A("A triagem apenas SUGERE a categoria; a classificação A/B/C final é dos autores (Fase 3).\n")
    A("## 1. Reconciliação\n")
    A("- Linhas em `gen_all.jsonl`: %d; em `sub_all.jsonl`: %d." % (len(gen), len(subs)))
    A("- Junção (modelo com `/`→`_`, linguagem, id): %d/%d (%s)." % (join_ok, len(subs), "100%" if join_ok == len(subs) else "FALHOU"))
    A("- Linhas em `triagem_submissoes.csv`: %d (esperado 10666): %s.\n" % (len(rows), "OK" if len(rows) == 10666 else "DIVERGE"))
    cnt = collections.Counter((r["linguagem"], r["status"]) for r in rows)
    A("### Veredito × linguagem vs. manuscrito\n")
    hdr = ["Linguagem"] + [a for _, a in ST_SHORT] + ["Total", "Confere?"]
    tb = []
    allok = True
    for lg in LANGS:
        got = [cnt[(lg, s)] for s, _ in ST_SHORT]
        exp = [EXPECT[lg][s] for s, _ in ST_SHORT]
        ok = got == exp and sum(got) == EXPECT_TOTAL[lg]
        allok &= ok
        tb.append([lg] + ["%d" % g_ + ("" if g_ == e else " (esp. %d)" % e) for g_, e in zip(got, exp)] + [sum(got), "SIM" if ok else "NÃO"])
    A(md_table(hdr, tb))
    A("Resultado: **%s**.\n" % ("todas as células batem exatamente com o manuscrito" if allok else "HÁ DIVERGÊNCIA"))

    A("## 2. Números de sanidade (análise exploratória prévia × este script)\n")
    A(md_table(["Item", "Esperado", "Obtido", "Comentário"], extras["sanidade"]))

    A("## 3. Sugestão automática\n")
    A("### 3.1 Entre as submissões NÃO aceitas, por linguagem\n")
    tb = []
    for lg in LANGS + ["TODAS"]:
        sel = [r for r in rows if r["status"] != "Accepted" and (lg == "TODAS" or r["linguagem"] == lg)]
        c = collections.Counter(r["sugestao"] for r in sel)
        tb.append([lg, len(sel), c["A"], c["B"], c["C"], c["indefinido"]])
    A(md_table(["Linguagem", "Não aceitas", "A", "B", "C", "indefinido"], tb))
    A("### 3.2 Por linguagem × veredito (não aceitas)\n")
    tb = []
    for lg in LANGS:
        for s, _ in ST_SHORT[1:]:
            sel = [r for r in rows if r["linguagem"] == lg and r["status"] == s]
            c = collections.Counter(r["sugestao"] for r in sel)
            tb.append([lg, s, len(sel), c["A"], c["B"], c["C"], c["indefinido"]])
    A(md_table(["Linguagem", "Veredito", "n", "A", "B", "C", "indefinido"], tb))
    A("### 3.3 Regra de CRITERIOS.md que decidiu (não aceitas)\n")
    tb = []
    for lg in LANGS:
        c = collections.Counter(r["regra_sugestao"] for r in rows if r["linguagem"] == lg and r["status"] != "Accepted")
        tb.append([lg] + [c[k] for k in ["1", "1b", "2", "3", "4", "5", "6", "7"]])
    A(md_table(["Linguagem", "R1 (A)", "R1b (A)", "R2 (A)", "R3 (A)", "R4 (B)", "R5 (B)", "R6 (C)", "R7 (indef.)"], tb))
    A("### 3.4 Python3, Runtime Error: sugestão × tipo de exceção\n")
    pr = [r for r in rows if r["linguagem"] == "Python3" and r["status"] == "Runtime Error"]
    ce = collections.defaultdict(collections.Counter)
    for r in pr:
        ce[r["excecao"]][r["sugestao"]] += 1
    tb = [[k, sum(v.values()), v["A"], v["B"], v["C"], v["indefinido"]] for k, v in sorted(ce.items(), key=lambda kv: -sum(kv[1].values()))]
    A(md_table(["Exceção", "n", "A", "B", "C", "indefinido"], tb))
    A("Simetria: Compile Error em C++/Java = %d + %d; Runtime Error em Python3 = %d (os %d Compile Error de Python3 são todos de submissões julgadas como C++)." % (
        cnt[("C++", "Compile Error")], cnt[("Java", "Compile Error")], cnt[("Python3", "Runtime Error")], cnt[("Python3", "Compile Error")]))
    A("")
    A("### 3.5 Python3: Runtime Error + Compile Error vs. C++/Java (CE + RE somados), por sugestão\n")
    tb = []
    for lg in LANGS:
        sel = [r for r in rows if r["linguagem"] == lg and r["status"] in ("Runtime Error", "Compile Error")]
        c = collections.Counter(r["sugestao"] for r in sel)
        tb.append([lg, len(sel), c["A"], c["B"], c["C"], c["indefinido"]])
    A(md_table(["Linguagem", "CE+RE", "A", "B", "C", "indefinido"], tb))

    A("## 4. Reconstrução do código submetido\n")
    hdr, out = resumo_reconstrucao(rows)
    A("Validação = linha `N` do erro, com a linha ecoada na mensagem, bate com a linha `N` do código reconstruído (espaços colapsados). Só há validação quando a mensagem ecoa a linha e `N` cai dentro do código reconstruído (frames do driver são ignorados); `sem_info` não entra na taxa.\n")
    A(md_table(hdr, [x for x in out if x[2] == "todas"]))
    A("Por estrato de incerteza (F15):\n")
    A(md_table(hdr, [x for x in out if x[2].startswith("recon_incerta")]))
    A("Divergências de validação (`nao`) por linguagem: %s.\n" % ", ".join("%s=%d" % (lg, sum(1 for r in rows if r["linguagem"] == lg and r["recon_validada"] == "nao")) for lg in LANGS))

    A("## 5. Amostra para a Fase 3\n")
    A("- `amostra_fase3.csv`: %d Runtime Errors de Python obrigatórios (F1>1, F2 falso, F4=sim ou F7=sim) + %d amostrados dos %d demais (estratificação proporcional ao nº de RE de cada modelo entre os demais; alvo total 100).\n" % amostra_info)

    A("## 6. Ambiguidades, decisões conservadoras e limitações\n")
    for x in extras["limitacoes"]:
        A("- " + x)
    A("")
    A("## 7. Tempo\n")
    A("Execução do script até esta linha: %.1f s (meta < 180 s).\n" % tempo)
    return "\n".join(L)


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    qs, specs, gen, subs = carregar()
    subs.sort(key=lambda s: (s["modelo"], s["linguagem"], int(s["id_questao"])))
    rows = []
    join_ok = 0
    for s in subs:
        g = gen.get((s["modelo"], s["linguagem"], int(s["id_questao"])))
        if g is None:
            continue
        join_ok += 1
        qid = int(s["id_questao"])
        rows.append(processar(s, g, qs[qid], specs[qid]))
    print("junção: %d/%d" % (join_ok, len(subs)))

    write_csv(os.path.join(OUT, "triagem_submissoes.csv"), TRIAGEM_COLS, [[r[c] for c in TRIAGEM_COLS] for r in rows])
    h, o = resumo_por_flag(rows)
    write_csv(os.path.join(OUT, "resumo_por_flag.csv"), h, o)
    h, o = resumo_por_modelo(rows)
    write_csv(os.path.join(OUT, "resumo_por_modelo.csv"), h, o)
    h, o = resumo_por_questao(rows, qs)
    write_csv(os.path.join(OUT, "resumo_por_questao.csv"), h, o)
    h, o = resumo_reconstrucao(rows)
    write_csv(os.path.join(OUT, "resumo_reconstrucao.csv"), h, o)
    h, o, n_todos, n_sel, n_resto = amostra_fase3(rows)
    write_csv(os.path.join(OUT, "amostra_fase3.csv"), h, o, bom=True)

    # ---- sanidade ----
    py = [r for r in rows if r["linguagem"] == "Python3"]
    pyre = [r for r in py if r["status"] == "Runtime Error"]
    exc = collections.Counter(r["excecao"] for r in pyre)
    n_hdr = sum(1 for r in py if r["cabecalho_perdido"] == "sim")
    n_hdr_sol = sum(1 for r in py if r["cabecalho_perdido"] == "sim" and r["classe_esperada"] == "Solution")
    n_wrap = 0
    for r in py:
        g = gen[(r["modelo"].replace("/", "_"), "Python3", r["id"])]
        c = g.get("code_2025", g.get("code"))
        if not is_valid_code(c):
            c = try_extract_code_from_resposta(g.get("resposta", ""))
        if c and "class Solution" not in c:
            n_wrap += 1
    anc = [r for r in rows if r["modelo"] == "gemma2-9b-it" and r["linguagem"] == "Python3" and r["id"] == 2586]
    anc_txt, anc_ok = "ausente", False
    if anc:
        a = anc[0]
        anc_ok = a["sugestao"] == "A"
        gg = gen[("gemma2-9b-it", "Python3", 2586)]
        anc_txt = "code=%r; submetido=%r; erro=%s; sugestão=%s (regra %s); recon_validada=%s" % (
            gg.get("code_2025", gg.get("code")), a["_submetido"], a["tipo_erro"], a["sugestao"], a["regra_sugestao"], a["recon_validada"])
    san = [
        ["Python3 julgadas como C++ (lang_pretty)", "380", str(sum(1 for r in rows if r["linguagem"] == "Python3" and r["lang_julgada"] == "C++")), "F10"],
        ["Java julgadas como C++", "9", str(sum(1 for r in rows if r["linguagem"] == "Java" and r["lang_julgada"] == "C++")), "F10"],
        ["Python RE: SyntaxError", "740", str(exc["SyntaxError"]), ""],
        ["Python RE: IndentationError", "34", str(exc["IndentationError"]), ""],
        ["Python RE: NameError", "301", str(exc["NameError"]), ""],
        ["Python com cabeçalho da classe perdido (F9: classe esperada na resposta bruta e ausente em `code`)", "~799", str(n_hdr),
         "F9 usa a classe esperada (inclui classes de design); só classe Solution: %d" % n_hdr_sol],
        ["Python envelopadas pelo wrapper (`'class Solution' not in code`, mesmo teste do pipeline)", "1416", str(n_wrap), ""],
        ["Âncora gemma2-9b-it / Python3 / 2586 → sugestão A", "A", anc_txt, "OK" if anc_ok else "FALHOU"],
    ]

    # ---- limitações dinâmicas ----
    nrecon_none = sum(1 for r in rows if r["_submetido"] == "")
    b_aderente = sum(1 for r in rows if r["status"] in ("Wrong Answer", "Time Limit Exceeded", "Memory Limit Exceeded") and r["sugestao"] == "B" and r["ader_submetido"] == "sim")
    wa_b = sum(1 for r in rows if r["status"] in ("Wrong Answer", "Time Limit Exceeded", "Memory Limit Exceeded") and r["sugestao"] == "B")
    acc_f10 = sum(1 for r in rows if r["status"] == "Accepted" and r["lingua_errada"] == "sim")
    mixed = sum(1 for r in rows if r["regra_sugestao"] == "7" and r["status"] != "Accepted")
    mixed_f3 = sum(1 for r in rows if r["regra_sugestao"] == "7" and r["linguagem"] == "Python3" and r["erro_fora_classe"] == "sim" and r["stmts_modulo"] not in ("", "n/a", 0))
    f10_sem = sum(1 for r in rows if r["lingua_errada"] == "sem_info")
    drv = sum(1 for r in pyre if r["erro_fora_classe"] == "driver")
    n_sm = collections.Counter(r["linguagem"] for r in rows if r["status"] != "Accepted" and r["ader_bruto_tolerante"] == "so_metodos")
    n_ci = collections.Counter(r["linguagem"] for r in rows if r["status"] != "Accepted" and r["regra_sugestao"] == "4" and r["_bruto_ctor_implicito"] == "sim")
    lim = [
        "**Candidatos do bruto**: blocos cercados (regex do extrator, cercas de 3+ crases ou til), cerca final aberta e nunca fechada (resposta truncada), e o trecho após o rótulo `solution:` somente quando não contém cerca. O rótulo é buscado no INÍCIO de linha, diferente do regex do extrator (`(?i)solution\\s*:`), que casa também com `class Solution:` e é a causa do cabeçalho perdido. `<think>…</think>` é removido (também `<think>` sem fechamento e `</think>` órfão).",
        "**F1** conta as cercas pareadas na resposta bruta INTEIRA (inclui eventuais blocos dentro de `<think>`, que é o que o extrator enxerga).",
        "**Aderência tolerante (F14)** é cumulativa (estrito OU tolerante) e, como em CRITERIOS.md, só está definida para Python: só funções/imports/docstring no nível do módulo, métodos esperados com `self`, e após envolver na classe esperada o candidato fica aderente. **Em C++/Java a tolerância não está definida** (não há `self` nem wrapper): resposta com todos os cabeçalhos esperados mas SEM a classe recebe `ader_bruto_tolerante=so_metodos` e sugestão `indefinido` (regra 7) em vez de A (a regra 2 a faria A, mas o pipeline não envelopa C++/Java, então a ausência da classe é do modelo). Ocorrências (não aceitas): C++=%d, Java=%d. **F16 coincide com `ader_bruto_tolerante=sim`** (definição do enunciado), portanto é redundante com F14." % (n_sm["C++"], n_sm["Java"]),
        "**Construtor implícito**: CRITERIOS.md exige que TODOS os métodos do starter existam, incluindo `__init__`/construtor. Seguido à letra. Uma classe de design sem construtor de 0 parâmetros é aceita pelo driver (construtor implícito), então esse critério pode produzir B espúrio. Casos B (regra 4, não aceitos) que passariam a ter bruto aderente se o construtor implícito de 0 parâmetros fosse aceito: C++=%d, Java=%d, Python3=%d (não alterados na sugestão; coluna não exportada, número apenas informativo)." % (n_ci["C++"], n_ci["Java"], n_ci["Python3"]),
        "**C++/Java** são verificados só por regex de cabeçalho (nome + contagem de parâmetros no nível superior, `<>` e `()` respeitados, parâmetros com valor padrão opcionais); a definição deve ser seguida de `{` (ou `const`/`override`/`throws`/lista de inicialização), de modo que protótipos terminados em `;` não contam. Não verifica retorno, tipos nem se o método está dentro da classe.",
        "**Aderência em Python** usa a última definição da classe/método; `@staticmethod` não desconta `self`; parâmetros extras sem padrão tornam o método não aderente.",
        "**F3 (stmts_modulo)**: conta instruções de módulo que não sejam classe, função, import, docstring, `pass`, ou atribuição sem chamada. `if __name__…`, `print`, chamadas soltas, `for`, `with` e atribuições com chamada (`sol = Solution()`) contam. Como o wrapper indenta tudo dentro de `class Solution:`, o F3 só dispara quando o modelo já trouxe a classe.",
        "**F4 (erro_fora_classe)** usa o PRIMEIRO frame do traceback (o mais interno; o LeetCode lista o mais interno primeiro). `driver` = a linha do frame excede o tamanho do código reconstruído (código do driver do LeetCode, anexado depois), contabilizado à parte e NÃO como `sim` (%d casos). Só é calculado para Runtime Error de Python julgado em Python. Se a classe esperada não existe no código submetido, a linha é considerada fora dela." % drv,
        "**Validação da reconstrução**: exige eco da linha na mensagem; Runtime Error de C++ (sanitizers) e Java (`at line N`) não ecoam a linha e ficam `sem_info`; Accepted não tem erro e fica `sem_info`. Para Python julgado como C++ usa-se o eco no formato `N | texto` do clang.",
        "**F15 (recon_incerta)**: submissões anteriores a 2025-09-17 20:34 UTC, a submissão de 2025-10-09 e as sem código reconstruível (%d). O instante do commit foi tomado de CRITERIOS.md; não há `.git` no espelho para conferir." % nrecon_none,
        "**Código lido do cache atual**: a reconstrução usa `code`/`resposta` de `gen_all.jsonl`, i.e. o JSON como está hoje; `reavaliado_em` (2025-08-17) é anterior a todas as submissões, mas edições posteriores não são rastreáveis. A validação por linha é a evidência independente (seção 4).",
        "**F2/F3/F14 dependem do `ast` do interpretador usado** (esta execução: Python %s). Gramática de versões mais novas (por exemplo f-strings aninhadas, PEP 701, aceitas em 3.12+) pode não parsear em 3.10 e inflar `nao_parseavel`; o LeetCode usa outra versão. Comparar F2=nao entre interpretadores antes de fechar números." % sys.version.split()[0],
        "**F13 (think_ou_prosa)**: `think` = a resposta bruta contém `<think>`/`</think>` (modelos de raciocínio; não é erro por si só); `code_em_think` = o campo `code` é um trecho do bloco de raciocínio; `prosa` = heurística (linha ≥20 caracteres, ≥5 palavras, sem símbolos de código, fora de comentários/docstrings), sujeita a falsos positivos e negativos.",
        "**F7**: conjunto fixo de classes fornecidas pelo LeetCode (%s). Redefinir em Python normalmente é inofensivo; em C++/Java costuma causar erro de compilação." % ", ".join(sorted(LC_CLASSES)),
        "**F10**: %d submissões não trazem `lang_pretty` (Timeouts) → `sem_info`, NÃO tratadas como F10. Submissões Accepted com F10=sim: %d." % (f10_sem, acc_f10),
        "**Regra 5 e casos mistos**: a regra 5 exige que as instruções soltas do submetido já constem do melhor candidato bruto (aderente, com menos instruções de módulo). Quando o submetido tem instruções soltas e erro fora da classe mas elas NÃO estavam no melhor candidato (o extrator as acrescentou), o caso é misto e foi para `indefinido` (regra 7) em vez da regra 6 (C), conforme a introdução de CRITERIOS.md. Ocorrências: %d. Total de `indefinido` entre as não aceitas: %d." % (mixed_f3, mixed),
        "**Regra 4** é aplicada à letra: bruto não aderente → B, mesmo quando o extrator piorou o resultado. WA/TLE/MLE sugeridos B: %d; destes o submetido era aderente em %d (indício de falso negativo da checagem de aderência, ou de extração que 'consertou' a resposta); vale revisão manual." % (wa_b, b_aderente),
        "**Amostra da Fase 3**: ~100 amostrados NO TOTAL (não por modelo), com alocação proporcional ao tamanho de cada modelo entre os demais RE de Python (maior resto), semente %d. Se a intenção era ~100 POR modelo, ajustar `total_alvo` em `amostra_fase3`." % SEED,
        "**Destaque em `resumo_por_questao.csv`**: limiar `>=5` modelos com Python falhando e C++ e Java passando no mesmo modelo é escolha operacional (cerca de metade dos 11 modelos), não vem de CRITERIOS.md.",
        "**F17 (questao_errada_juiz)**, adicionada na revisão da sessão principal: o `resolve_question` do pipeline lê um slug que começa com `<dígitos>-` como frontend id; em `2-keys-keyboard` (questão 650) o question_id enviado foi o da questão 2 e o driver chamou `addTwoNumbers`. As 33 submissões da questão 650 (3 linguagens) foram julgadas em outra questão; regra 1b → A. Única questão da amostra com slug iniciado por dígito.",
        "**Dificuldade** vem de `sample.csv`; **eh_design** = classe esperada do starter Python diferente de `Solution`; **F11** só para Python.",
    ]
    rep = relatorio(rows, gen, subs, join_ok, (n_todos, n_sel, n_resto), time.time() - t0, {"sanidade": san, "limitacoes": lim})
    with open(os.path.join(OUT, "RELATORIO.md"), "w", encoding="utf-8") as f:
        f.write(rep)
    print("ok em %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
