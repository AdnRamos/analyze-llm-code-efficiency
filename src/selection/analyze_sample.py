import pandas as pd
import json
# Diagnóstico correto: contagem baseada em todas as tags (temas_list)
from collections import Counter

# População
# Load population data first
with open("datasets\leetcode\public_problems.json", "r", encoding="utf-8") as f:
    pop_data = json.load(f)
df_pop = pd.DataFrame(pop_data)
df_pop["temas_list"] = df_pop["temas"].apply(lambda x: [t.strip() for t in x] if isinstance(x, list) else [])

pop_tags = [t for sub in df_pop["temas_list"] for t in sub]
temas_pop = set(pop_tags)
temas_contagem = Counter(pop_tags)
temas_frequentes = {t for t, count in temas_contagem.items() if count >= 50}

# Amostra
amostra = pd.read_csv("datasets\leetcode\sample.csv")
with open("datasets\leetcode\public_problems.json", "r", encoding="utf-8") as f:
    data = json.load(f)
df_amostra_full = pd.DataFrame(data)
df_amostra = df_amostra_full[df_amostra_full["id"].isin(amostra["ID"])]
df_amostra["temas_list"] = df_amostra["temas"].apply(lambda x: [t.strip() for t in x] if isinstance(x, list) else [])

tags_amostra = [t for sub in df_amostra["temas_list"] for t in sub]
temas_amostra = set(tags_amostra)

# Diagnóstico final correto
temas_freq_fora = temas_frequentes - temas_amostra

print(f"Total de temas frequentes na população: {len(temas_frequentes)}")
print(f"Total de temas frequentes presentes na amostra: {len(temas_frequentes & temas_amostra)}")
print("Temas frequentes ausentes da amostra:", sorted(temas_freq_fora))
