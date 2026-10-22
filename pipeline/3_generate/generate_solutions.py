"""
Step 3: asks each LLM to solve every sampled problem in C++, Java and Python3 (zero-shot, temperature 0, one
attempt) and stores the raw response in data/generations/<model>/<language>/<id>.json.

Configuration (config.json, see config.example.json and pipeline/lib/config.py): provider ("groq" or
"openai_compatible" + base_url), api_key, models (default: the 11 models of the paper), temperature.
The run is resumable: progress is kept in data/.cache/generation_progress.json.

The `categoria` field (correct / plausible / invalid) is decided here with the 2025 heuristic `extrair_codigo`;
responses classified as `invalid` (no extractable code) are not submitted (they are the "incomplete
generations" of the paper). The code that is actually submitted is produced later by step 4.

Usage: python pipeline/3_generate/generate_solutions.py
"""
import os
import sys
import json
import pandas as pd
import time
import re
import ast
from collections import deque
from typing import Tuple
from datetime import datetime

# === CONFIGURAÇÕES GLOBAIS ===
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, os.pardir, os.pardir))

sys.path.insert(0, os.path.dirname(script_dir))
from lib.paths import CACHE, GENERATIONS, SAMPLE_CSV  # noqa: E402
from lib.config import load_config  # noqa: E402

PROGRESS_FILE_PATH = str(CACHE / "generation_progress.json")
STATUS_FILE_PATH = str(CACHE / "generation_status.json")
df_csv_path = str(SAMPLE_CSV)
OUTPUT_BASE = str(GENERATIONS)

# Listagem de linguagens suportadas e mapeamento para chave do starter code
LINGUAGENS = ["C++", "Java", "Python3"]
LANG_KEY = {"C++": "cpp", "Java": "java", "Python3": "python3"}
# Tempo de espera em segundos após RateLimitError antes de tentar o mesmo modelo
BACKOFF_SECONDS = 60

# === INICIALIZAÇÃO DO PROVEDOR (Groq ou qualquer servidor compatível com a API da OpenAI) ===
CFG = load_config()
try:
    if CFG["provider"] == "groq":
        from groq import Groq, RateLimitError
        client = Groq(api_key=CFG["api_key"])
    elif CFG["provider"] == "openai_compatible":
        from openai import OpenAI, RateLimitError
        client = OpenAI(api_key=CFG["api_key"] or "none", base_url=CFG["base_url"])
    else:
        raise ValueError("provider desconhecido: %s" % CFG["provider"])
except Exception as e:
    print(f"Erro na inicialização da API: {e}")
    sys.exit(1)
TEMPERATURE = CFG["temperature"]

# === DEFINIÇÃO DOS PROMPTS ===
PROMPT_SYSTEM = (
    "You are a programming and algorithms specialist. "
    "When the user provides a problem statement and programming language, analyze and efficiently solve the problem. "
    "Respond strictly and ONLY in the following format, with no additional thoughts, commentary, or step-by-step reasoning. "
    "Do NOT write any intermediate thoughts, explanations of your process, or reasoning steps before the final answer. "
    "Do not include <think>, preambles, or anything outside this format:\n\n"
    "solution: <algorithm solution in code>\n"
    "efficiency: <HIGH | MEDIUM | LOW>\n"
    "time complexity: <BIG O notation>\n"
    "space complexity: <BIG O notation>\n"
    "energy implications: <LOW | MEDIUM | HIGH>\n"
    "explanation: <Concise explanation of the main approach and key strengths/weaknesses. Do not include anything outside of this format.>"
)
USER_PROMPT = (
    "How would you efficiently solve the following LeetCode problem in {language}?\n\n"
    "Problem statement:\n{problem}\n\n"
    "Starter code ({language}):\n```{starter}```\n\n"
    "Please **insert your solution into the starter code above without altering its structure**, and respond **only** in the prescribed format (no commentary):"
)

# === FUNÇÕES DE PROGRESSO ===
def carregar_progresso():
    if not os.path.exists(PROGRESS_FILE_PATH):
        return 0
    with open(PROGRESS_FILE_PATH, "r") as f:
        return json.load(f).get("ultimo_task_index", 0)

def salvar_progresso(task_index):
    os.makedirs(os.path.dirname(PROGRESS_FILE_PATH), exist_ok=True)
    with open(PROGRESS_FILE_PATH, "w") as f:
        json.dump({"ultimo_task_index": task_index}, f, indent=2)

def carregar_status_respostas():
    if os.path.exists(STATUS_FILE_PATH):
        with open(STATUS_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_status_respostas(status_respostas):
    os.makedirs(os.path.dirname(STATUS_FILE_PATH), exist_ok=True)
    with open(STATUS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(status_respostas, f, indent=2, ensure_ascii=False)

# === EXTRAÇÃO E VALIDAÇÃO DE RESPOSTA ===
def extrair_codigo(conteudo: str) -> str:
    labels_pattern = r'(?i)\n\s*(solution:|efficiency:|time complexity:|space complexity:|energy implications:|explanation:)'
    m = re.search(r'(?i)solution:\s*```[^\n]*\n(.*?)```', conteudo, flags=re.DOTALL)
    if m:
        code = m.group(1).strip()
    else:
        m2 = re.search(r'```[^\n]*\n(.*?)```', conteudo, flags=re.DOTALL)
        if m2:
            code = m2.group(1).strip()
        else:
            m3 = re.search(r'(?i)solution:\s*(.*)', conteudo, flags=re.DOTALL)
            if m3:
                after = m3.group(1)
                code = re.split(labels_pattern, after, maxsplit=1)[0].strip()
            else:
                return ""
    return re.split(labels_pattern, code, maxsplit=1)[0].strip()

def validar_resposta(conteudo: str) -> bool:
    labels = [
        "solution:", "efficiency:", "time complexity:",
        "space complexity:", "energy implications:", "explanation:"
    ]
    low = conteudo.lower()
    return all(lbl in low for lbl in labels) and bool(extrair_codigo(conteudo))

# === CLASSIFICAÇÃO E MOTIVO ===
def classificar_resposta(conteudo: str) -> Tuple[str, str]:
    labels = [
        "solution:", "efficiency:", "time complexity:",
        "space complexity:", "energy implications:", "explanation:"
    ]
    codigo = extrair_codigo(conteudo)
    if not codigo:
        return "invalid", "código não extraído"
    count = sum(lbl in conteudo.lower() for lbl in labels)
    if count == len(labels):
        if re.search(r'^(import\s|#include\s|using\s)', codigo, flags=re.MULTILINE):
            return "plausible", "contém import/includes"
        return "correct", "todas as seções presentes corretamente"
    return "plausible", f"código extraído mas apenas {count}/{len(labels)} seções presentes"

# === PROCESSAMENTO DE UMA TAREFA ===
def processar_task(q, modelo, lang, status_respostas):
    out_dir = os.path.join(OUTPUT_BASE, modelo.replace("/","_"), lang)
    os.makedirs(out_dir, exist_ok=True)
    starter = q['starter_code'].get(LANG_KEY[lang], "")
    try:
        resp = client.chat.completions.create(
            messages=[
                {"role": "system", "content": PROMPT_SYSTEM},
                {"role": "user", "content": USER_PROMPT.format(language=lang, problem=q['enunciado'], starter=starter)}
            ],
            model=modelo,
            temperature=TEMPERATURE
        )
        txt = resp.choices[0].message.content
        st = "ok"
    except RateLimitError:
        raise
    except Exception:
        txt, st = "", "erro"
    code = extrair_codigo(txt)
    cat, motivo = classificar_resposta(txt)
    resultado = {"id": q['id'], "modelo": modelo, "linguagem": lang,
                 "status": st, "categoria": cat, "motivo": motivo,
                 "resposta": txt, "code": code,
                 "timestamp": datetime.now().isoformat()}
    with open(os.path.join(out_dir, f"{q['id']}.json"), "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    # Atualiza relatório de status incluindo categoria e motivo
    sr = status_respostas.setdefault(str(q['id']), {})
    sr.setdefault(modelo, {})[lang] = {"status": st, "categoria": cat, "motivo": motivo}
    salvar_status_respostas(status_respostas)
    print(f"q={q['id']} | modelo={modelo} | lang={lang} | categoria={cat} | motivo={motivo}")

# === LOOP PRINCIPAL COM BACKOFF POR MODELO ===
def main():
    df = pd.read_csv(df_csv_path)
    df['starter_code'] = df['starter_code'].apply(lambda s: ast.literal_eval(s) if pd.notna(s) else {})
    modelos = list(CFG["models"])   # lista explícita (padrão: os 11 modelos do artigo)
    print("Modelos:", ", ".join(modelos))
    total_q = len(df)
    tasks = [(i, modelo, lang) for i in range(total_q) for modelo in modelos for lang in LINGUAGENS]
    start_idx = carregar_progresso()
    queue = deque(tasks[start_idx:])
    paused_until = {}
    status_respostas = carregar_status_respostas()
    task_count = start_idx
    print(f"Retomando tasks a partir de {start_idx+1} de {len(tasks)}")
    rotations = 0
    while queue:
        now = time.time()
        i, modelo, lang = queue[0]
        pause_end = paused_until.get(modelo, 0)
        if now < pause_end:
            queue.rotate(-1)
            rotations += 1
            if rotations >= len(queue):
                sleep_time = max(0, min(paused_until.values()) - now)
                print(f"Todos modelos em backoff. Aguardando {sleep_time:.0f}s...")
                time.sleep(sleep_time)
                rotations = 0
            continue
        queue.popleft()
        rotations = 0
        try:
            processar_task(df.iloc[i].to_dict(), modelo, lang, status_respostas)
            task_count += 1
            salvar_progresso(task_count)
        except RateLimitError:
            paused_until[modelo] = now + BACKOFF_SECONDS
            print(f"Modelo {modelo} atingiu rate limit. Pausando por {BACKOFF_SECONDS}s...")
            queue.append((i, modelo, lang))
        except Exception as e:
            print(f"Erro em task ({i},{modelo},{lang}): {e}")
            task_count += 1
            salvar_progresso(task_count)
    print("Todas as tasks processadas.")

if __name__ == '__main__':
    print("Iniciando coleta de respostas...")
    main()
