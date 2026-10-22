"""
Code extraction and formatting for LeetCode submission (corrected pipeline, October 2026).

This module turns a raw LLM response (field `resposta` in data/generations/<model>/<language>/<id>.json)
into the code that is submitted to LeetCode. It replaces the 2025 extraction, which had defects found
during the revision of the paper (see README, "Pipeline fix"):

  E1  <think>...</think> blocks (and an unclosed <think> up to the end) are removed before searching.
  E2  The template label `solution:` is only recognised at the start of a line, so the `Solution:`
      inside `class Solution:` is no longer mistaken for the label (2025 bug: the class header and
      everything before it, imports included, were dropped).
  E3  Region = from the label (or the start, if there is no label) to the next template label
      (Efficiency / Time complexity / Space complexity / Energy implications / Explanation).
      2+ fences -> content between the first two; 1 fence -> text before it (closing a block opened
      before the label) or after it (unclosed block); no fence in the region -> first fenced block of the
      response, if it does not contain the label itself; otherwise the region text.
      Empty region -> first complete fenced block after the label.
  E4  Keeps the indentation of the first line (only blank lines at the ends are removed) and dedents.
  E5  Imports/includes are never removed.
  W1  Python3 only: if the class expected by the starter code (Solution or a design class) is not
      declared, module-level functions whose first parameter is `self` are moved into it; imports and
      helper classes stay at module level. Code that does not parse is wrapped as a whole.
      C++/Java: no wrapper.

The choice never depends on whether the code compiles or on the verdict.
"""
import ast
import re
import textwrap

_KNOWN_LANG_TAGS = {
    "c", "cpp", "c++", "cc", "h", "hpp", "java", "python", "python3", "py", "go", "javascript", "js", "typescript", "ts",
    "csharp", "c#", "cs", "rust", "rs", "ruby", "rb", "php", "swift", "kotlin", "scala", "perl", "pl", "r", "julia",
    "solidity", "sol", "dart", "zig", "lua", "haskell", "hs", "ocaml", "ml", "shell", "bash", "sh", "powershell", "ps1",
    "sql", "mysql", "postgresql"
}

def _looks_like_lang_tag(line0):
    t = line0.strip().lower()
    if " " in t:
        return False
    t = t.strip(" :;,.")
    return t in _KNOWN_LANG_TAGS

def strip_think(text):
    t = re.sub(r"(?is)<think>.*?</think>", "", text)
    i = t.lower().find("<think>")
    if i >= 0:
        t = t[:i]
    j = t.lower().rfind("</think>")
    if j >= 0:
        t = t[j + len("</think>"):]
    return t

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

KW = {"if", "for", "while", "switch", "catch", "return", "sizeof", "else", "do", "new", "throw"}

def strip_cj_comments(s):
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    s = re.sub(r"//[^\n]*", " ", s)
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

def safe_parse(code):
    try:
        return ast.parse(code)
    except Exception:
        return None


LABEL_SOL = re.compile(r"(?im)^[ \t*#_>\-]*solution[ \t*_]*:[ \t]*")


FENCE = re.compile(r"(?s)(`{3,}|~{3,})(.*?)\1")


OPEN_FENCE = re.compile(r"`{3,}|~{3,}")


NEXT_LABEL = re.compile(r"(?im)^[ \t*#_>\-]*(efficiency|time complexity|space complexity|energy implications|explanation)[ \t*_]*:")


def clean_block(inner):
    linhas = inner.split("\n")
    while linhas and not linhas[0].strip():
        linhas.pop(0)
    if linhas and _looks_like_lang_tag(linhas[0]):
        linhas.pop(0)
    while linhas and not linhas[0].strip():
        linhas.pop(0)
    while linhas and not linhas[-1].strip():
        linhas.pop()
    return textwrap.dedent("\n".join(l.rstrip() for l in linhas))


def extract_code(resposta):
    """Retorna (codigo, origem)."""
    t = strip_think(resposta or "")                                   # E1
    m = LABEL_SOL.search(t)                                             # E2
    sec = t[m.end():] if m else t
    origem = "rotulo" if m else "sem_rotulo"
    n = NEXT_LABEL.search(sec)                                          # E3: região até o próximo rótulo
    regiao = sec[:n.start()] if n else sec
    cercas = list(OPEN_FENCE.finditer(regiao))
    if len(cercas) >= 2:
        code, tipo = regiao[cercas[0].end():cercas[1].start()], "bloco"
    elif len(cercas) == 1:
        antes, depois = regiao[:cercas[0].start()], regiao[cercas[0].end():]
        if antes.strip():   # cerca que fecha um bloco aberto antes do rótulo
            code, tipo = antes, "texto_antes_da_cerca"
        else:               # cerca aberta e não fechada
            code, tipo = depois, "cerca_aberta"
    else:
        f = FENCE.search(t)
        if f and m and f.start() < m.start() < f.end():
            f = None  # o rótulo está DENTRO do bloco (template inteiro cercado): a região já é o código
        if f:   # região sem cerca, mas há bloco cercado na resposta (ex.: código antes do rótulo)
            code, tipo = f.group(2), "bloco_fora_do_rotulo"
        else:
            code, tipo = regiao, "texto"
    code = clean_block(code)
    if not code.strip():    # região vazia: primeiro bloco cercado completo depois do rótulo
        f = FENCE.search(sec)
        if f:
            code, tipo = clean_block(f.group(2)), "bloco_apos_regiao_vazia"
    return code, origem + "+" + tipo


def wrap_python(code, ling, spec):                               # W1
    """Python: se a classe esperada não existe, move para dentro dela as funções de nível de módulo
    cujo 1º parâmetro é self (com decoradores); o resto (imports, classes auxiliares) fica no módulo.
    Se o código não parseia, envolve tudo (comportamento do pipeline original)."""
    if ling != "Python3" or not code.strip():
        return code, "sem_wrapper"
    cls = spec["cls"]
    if re.search(r"(?m)^class\s+%s\b" % re.escape(cls), code):
        return code, "inalterado"
    tree = safe_parse(code)
    linhas = code.split("\n")
    if tree is None:
        corpo = "\n".join(("    " + l) if l.strip() else "" for l in linhas)
        return "class %s:\n%s\n" % (cls, corpo), "envolvido_tudo:" + cls
    metodos = [nd for nd in tree.body if isinstance(nd, (ast.FunctionDef, ast.AsyncFunctionDef))
               and nd.args.args and nd.args.args[0].arg == "self"]
    if not metodos:
        return code, "sem_metodos_self"
    usadas, blocos = set(), []
    for nd in metodos:
        ini = min([nd.lineno] + [d.lineno for d in nd.decorator_list]) - 1
        fim = nd.end_lineno
        usadas.update(range(ini, fim))
        blocos.append("\n".join(("    " + l) if l.strip() else "" for l in linhas[ini:fim]))
    resto = "\n".join(l for i, l in enumerate(linhas) if i not in usadas).strip("\n")
    novo = (resto + "\n\n" if resto.strip() else "") + "class %s:\n" % cls + "\n\n".join(blocos) + "\n"
    return novo, "metodos_movidos:" + cls


def starter_spec(starter_code, language):
    """Expected class and methods for one language, from the `starter_code` dict of data/problems/sample.csv."""
    key = {"Python3": "python3", "C++": "cpp", "Java": "java"}[language]
    s = starter_code[key]
    return parse_py_starter(s) if language == "Python3" else parse_cj_starter(s)


def prepare_submission(resposta, language, starter_code):
    """Raw LLM response -> code sent to LeetCode. Returns (code, details)."""
    code, origin = extract_code(resposta)
    code, wrap = wrap_python(code, language, starter_spec(starter_code, language))
    return code, {"extraction": origin, "wrapper": wrap}
