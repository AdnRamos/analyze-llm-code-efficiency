import pandas as pd
import json
from collections import Counter

with open("leetcode_base/questoes_publicas.json", "r", encoding="utf-8") as f:
    data = json.load(f)
df = pd.DataFrame(data)
df["enunciado"] = df["enunciado"].str.replace(r'[\n\r]+', ' ', regex=True).str.strip()
df["titulo"] = df["titulo"].str.replace(r'[\n\r]+', ' ', regex=True).str.strip()

if "erro" in df.columns:
    df = df[df["erro"].isna() | (df["erro"] == "")]

# Amostragem estratificada proporcional
df["temas_list"] = df["temas"].apply(lambda x: [t.strip() for t in x] if isinstance(x, list) else [])

df_easy = df[df["dificuldade"] == "Fácil"]
df_med = df[df["dificuldade"] == "Média"]
df_hard = df[df["dificuldade"] == "Difícil"]

N_total = len(df)
N_easy = len(df_easy)
N_med = len(df_med)
N_hard = len(df_hard)

n_total = 336
n_easy = round(N_easy / N_total * n_total)
n_med = round(N_med / N_total * n_total)
n_hard = n_total - n_easy - n_med

seed = 2025

sample_easy = df_easy.sample(n=n_easy, random_state=seed)
sample_med = df_med.sample(n=n_med, random_state=seed)
sample_hard = df_hard.sample(n=n_hard, random_state=seed)

amostra = pd.concat([sample_easy, sample_med, sample_hard]).reset_index(drop=True)
amostra["temas_list"] = amostra["temas"].apply(lambda x: [t.strip() for t in x] if isinstance(x, list) else [])

# Cálculo de temas frequentes
temas_contagem = Counter([tema for sublist in df["temas_list"] for tema in sublist])
temas_frequentes = {tema for tema, count in temas_contagem.items() if count >= 50}

# --- LOOP para garantir a cobertura temática mínima --- #
# Repete enquanto houver algum tema frequente < 5 ocorrências
while True:
    tema_na_amostra = Counter([tema for sublist in amostra["temas_list"] for tema in sublist])
    faltando = {tema: 5 - tema_na_amostra.get(tema, 0) for tema in temas_frequentes if tema_na_amostra.get(tema, 0) < 5}
    if not faltando:
        break
    for tema, faltam in faltando.items():
        for dificuldade in ["Fácil", "Média", "Difícil"]:
            if faltam <= 0:
                break
            candidatos = df[
                (df["dificuldade"] == dificuldade) &
                (df["temas_list"].apply(lambda x: tema in x)) &
                (~df["id"].isin(amostra["id"]))
            ]
            if not candidatos.empty:
                add = candidatos.sample(n=min(faltam, len(candidatos)), random_state=seed)
                amostra = pd.concat([amostra, add], ignore_index=True)
                faltam -= len(add)
    # Atualiza as listas após cada rodada
    amostra = amostra.drop_duplicates(subset="id").reset_index(drop=True)
    amostra["temas_list"] = amostra["temas"].apply(lambda x: [t.strip() for t in x] if isinstance(x, list) else [])

# Ordenação e exportação
ordem_dificuldade = pd.CategoricalDtype(categories=["Fácil", "Média", "Difícil"], ordered=True)
amostra["dificuldade"] = amostra["dificuldade"].astype(ordem_dificuldade)

amostra.rename(columns={
    "id": "ID",
    "url": "URL",
    "dificuldade": "Dificuldade",
    "tema_principal": "Tema Principal",
    "titulo": "Título",
    "enunciado": "Enunciado"
}, inplace=True)
colunas = ["ID", "URL", "Dificuldade", "Tema Principal", "Título", "Enunciado"]
amostra = amostra.sort_values(["Tema Principal", "Dificuldade", "ID"]).reset_index(drop=True)

amostra.to_csv("leetcode_base/amostra_final.csv", index=False, encoding="utf-8", columns=colunas)
print(f"Amostra final: {amostra.shape}")

# Diagnóstico final por tema frequente (opcional)
tema_final = Counter([tema for sublist in amostra["temas_list"] for tema in sublist])
print("\nTemas frequentes e sua contagem na amostra (deve ser >=5):")
for tema in sorted(temas_frequentes):
    print(f"{tema:25s}: {tema_final.get(tema, 0)}")
