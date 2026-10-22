# Guia de reprodução

*English version: [REPRODUCING.md](REPRODUCING.md).*

Há duas formas de reproduzir o estudo. As duas começam pela mesma preparação.

| | O que você obtém | Tempo | Precisa de |
|---|---|---|---|
| **A. A partir dos dados publicados** | todos os números e tabelas do artigo, recalculados a partir dos registros do juiz em `data/` | ~10 min | Python (R opcional) |
| **B. Do zero** | o estudo inteiro de novo: novo catálogo (opcional), novas gerações, novos vereditos | dias a semanas | chave de API de LLM, conta no LeetCode |

Você só chama o **`run.py`**: ele roda os scripts das outras pastas na ordem certa e para no primeiro erro. Os
README de cada pasta descrevem cada arquivo, para quem quiser rodar ou inspecionar uma etapa isolada.

## 0. Preparação

```bash
git clone <este repositório> && cd analyze-llm-code-efficiency
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Opcional: R ≥ 4.1 com `install.packages("glmmTMB")` para o modelo misto (o `run.py` pula essa etapa se não houver R).

---

## A. Reproduzir o artigo a partir dos dados publicados

```bash
python run.py paper
```

Executa, nesta ordem:

| # | Script | O que faz | O que deve aparecer |
|---|---|---|---|
| A1 | `validation/build_cache.py` | lê as 11.088 gerações e os 10.666 registros do juiz para um cache local | `cache -> .../data/.cache/validation` (≈2 min) |
| A2 | `validation/check_consistency.py` | verificações de integridade de `data/` | todas as linhas começam com `[ok]` (um rejulgamento pendente é informado, não é falha) |
| A3 | `pipeline/5_submit/build_results.py` | remonta `data/results.csv` a partir dos registros do juiz | `rows 10666 \| re-judged 2559 \| not matched 0 \| acceptance 51.5%` |
| A4 | `analysis/statistics.py` | todos os números e tabelas → `results/statistics/` | `results/statistics/ESTATISTICA.md` começa com `Submissões: 10666; aceitação 51.5% [50.6, 52.5]` |
| A5 | `analysis/glmm.R` | modelo misto → `results/glmm/` | `glmm_resumo.txt`: `n=10666 questoes=336 aceitas=5495`, `convergence=0` |

Para comparar com o artigo: `results/statistics/tabelas.tex` tem cada tabela entre `%%BEGIN <rótulo>` e
`%%END <rótulo>`; `results/statistics/numeros.json` tem cada número citado no texto. O dashboard abre com
`python run.py dashboard`.

Para refazer também a auditoria que encontrou os defeitos de 2025 (triagem A/B/C, conferência da extração, grupo de
controle, validação cega): `python run.py audit` (ver `validation/README.md`).

---

## B. Rodar o estudo do zero

### B0. Escolha uma pasta para a nova execução e configure

```bash
export STUDY_DATA_DIR=runs/minha-execucao/data STUDY_RESULTS_DIR=runs/minha-execucao/results   # Windows: set VAR=valor
cp config.example.json config.json
```

Edite o `config.json`:

| Chave | Significado |
|---|---|
| `provider` | `groq` (como no artigo) ou `openai_compatible` (vLLM, Ollama, qualquer nuvem compatível com a API da OpenAI; `pip install openai`) |
| `base_url` | endereço do servidor, só para `openai_compatible` (ex.: `http://localhost:8000/v1`) |
| `api_key` | chave de API do provedor |
| `models` | modelos avaliados (padrão: os 11 do artigo; a maioria não é mais servida pelo Groq) |
| `temperature` | 0 no artigo |
| `leetcode_user`, `leetcode_pass` | só para o submissor alternativo `submit_missing.py` |

Tudo vai para `runs/minha-execucao/`; `data/` e `results/` nunca são alterados. Cada etapa pode ser interrompida e
rodada de novo: ela continua de onde parou.

### B1. Coletar o catálogo — `python run.py collect`

Baixa todas as questões públicas de algoritmos do LeetCode (enunciado, dificuldade, temas, estatísticas, starter
code). Saída: `runs/minha-execucao/data/problems/`. Não precisa de login; leva várias horas.

**Quer a mesma amostra do artigo?** Pule a B1 e copie o catálogo publicado:
`mkdir -p runs/minha-execucao/data && cp -r data/problems runs/minha-execucao/data/` (a B2 então gera exatamente as
mesmas 336 questões).

### B2. Selecionar a amostra — `python run.py select`

Sorteia 336 questões estratificadas por dificuldade e tema (semente 2025). Saída: `problems/sample.csv`.
Deve aparecer `Total esperado: 336`, `Diferença: 0`, `Todos os temas estão representados na amostra.`

### B3. Gerar as soluções — `python run.py generate`

Um pedido por (questão, modelo, linguagem), zero-shot, temperatura 0. Saída: `generations/<modelo>/<linguagem>/<id>.json`
e figuras em `results/figures/generation_validation/`. Número de pedidos = 336 × 3 × número de modelos (11.088 para os
11 modelos). Limites de taxa são tratados automaticamente (o modelo é pausado e tentado de novo).

### B4. Extrair o código — `python run.py extract`

Grava o código a submeter no campo `code` de cada geração. Na primeira vez deve aparecer `files N | updated N`.

### B5. Submeter ao LeetCode — `python run.py submit`

**Rode no seu próprio computador** (o LeetCode bloqueia IPs de nuvem). Entre no leetcode.com pelo navegador, copie os
cookies `LEETCODE_SESSION` e `csrftoken` e exporte:

```bash
export LEETCODE_SESSION=... LEETCODE_CSRFTOKEN=...
python run.py submit
```

Submete toda geração com código (as classificadas `invalid` são puladas), grava cada veredito em `submissions/` e,
no fim, lista o que ainda falta (`check_submissions.py`: só as gerações `invalid` devem
sobrar). O LeetCode aceita cerca de 450–500 submissões por conta por dia; as mais de 10 mil levam algumas semanas —
basta rodar o comando de novo a cada dia. Se o LeetCode passar a recusar a API, use
`python pipeline/5_submit/submit_missing.py` (login e alternativas pelo navegador).

### B6–B7. Montar a base, conferir e analisar

```bash
python run.py results      # results.csv
python run.py check        # verificações de integridade: toda linha deve ser [ok]
python run.py analysis     # runs/minha-execucao/results/statistics/ e glmm/
STUDY_DATA_DIR=runs/minha-execucao/data STUDY_RESULTS_DIR=runs/minha-execucao/results python run.py dashboard
```

(`python run.py scratch` roda B2, B3, B4, B6, B7 e as verificações de uma vez, para quando B1 e B5 já foram feitas
ou não são necessárias.)

### O que vai sair diferente do artigo, e por quê

- **Catálogo:** o LeetCode continua adicionando questões; uma nova B1 gera um catálogo mais novo e outra amostra.
  Reaproveite `data/problems/` para manter a amostra do artigo (a B2 é determinística).
- **Modelos:** o Groq descontinuou a maioria dos 11 modelos depois do estudo. São modelos abertos e podem ser servidos
  em outro lugar (`openai_compatible`), mas as respostas podem não sair idênticas mesmo com temperatura 0.
- **Juiz:** o LeetCode pode mudar testes e versões das linguagens. Nossas 100 submissões de controle mantiveram o
  veredito entre 2025 e 2026; a memória medida ficou um pouco maior (razão mediana 1,03).

## Problemas comuns

| Problema | Solução |
|---|---|
| `[stop] ... ended with code 1` depois de `check` | leia as linhas `[FAIL]`; o relatório está em `validation/reports/consistency.md` (ou `<data>/.cache/consistency.md` em outra execução) |
| `Erro na inicialização da API` na B3 | confira `api_key`, `provider` e `base_url` no `config.json`; `pip install groq` ou `pip install openai` |
| A B5 mostra `[FAIL] Não encontrou question_id` ou HTTP 403/429 | cookies expirados ou limite diário atingido: atualize os cookies e rode mais tarde |
| A B5 mostra `julgada como <linguagem>. Não gravado.` | o LeetCode julgou em outra linguagem; não foi gravado e será tentado de novo na próxima execução |
| `[skip] Rscript analysis/glmm.R` | instale o R e o pacote `glmmTMB` para obter o modelo misto |
