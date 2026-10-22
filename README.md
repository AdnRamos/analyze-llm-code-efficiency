# Correctness, Execution Time, and Memory Usage of LLM-Generated Code on LeetCode

[English](#english) · [Português](#português)

---

## English

Replication package of *"Correctness, Execution Time, and Memory Usage of LLM-Generated Code: A Large-Scale
Empirical Study on LeetCode"* (Ramos and Andrade, JBCS, under revision). Archived version:
https://zenodo.org/records/18771666

The repository contains **all the code and all the data** of the study, from the collection of the LeetCode
catalogue to the tables of the paper, so that every step can be checked or run again.

### The study

We asked **11 freely available open-weight LLMs** hosted on Groq Cloud to solve a stratified sample of **336 LeetCode
problems** (92 Easy, 169 Medium, 75 Hard) in **C++, Java and Python3**, with a single zero-shot prompt (temperature
0) and one attempt per (problem, language, model). Of the 11,088 generation requests, **10,666** produced code that
was judged by LeetCode's online judge; the other 422 had no extractable code. Main results (`data/results.csv`):

| | |
|---|---|
| Single-attempt, zero-shot acceptance | 51.5% (5,495 / 10,666) |
| By language | C++ 50.3% · Java 51.9% · Python3 52.4% |
| By difficulty | Easy 74.5% · Medium 51.6% · Hard 21.0% |
| Mean execution time (accepted) | C++ 28.3 ms · Java 25.4 ms · Python3 151.2 ms |
| Mean memory (accepted) | C++ 29.1 MB · Java 48.0 MB · Python3 22.4 MB |

### How the repository is organised

| Folder | What it is | Details |
|---|---|---|
| `pipeline/` | The study as code, in five steps: collect the catalogue → select the sample → generate solutions with the LLMs → extract the code → submit to LeetCode's judge and build the final dataset. | [`pipeline/README.md`](pipeline/README.md) |
| `data/` | Everything collected and produced: catalogue and sample, raw LLM responses, judge records, final dataset. | [`data/README.md`](data/README.md) |
| `validation/` | Integrity checks of the data and the audit that found and fixed the 2025 pipeline defects. | [`validation/README.md`](validation/README.md) |
| `analysis/` | Statistics and mixed model that produce every number and table of the paper. | [`analysis/README.md`](analysis/README.md) |
| `results/` | Outputs of `analysis/` (generated, not edited). | [`results/README.md`](results/README.md) |
| `dashboard/` | Interactive dashboard (Streamlit, English/Portuguese). | [`dashboard/README.md`](dashboard/README.md) |

```
pipeline/1_collect -> 2_select -> 3_generate -> 4_extract -> 5_submit -> data/results.csv -> analysis/ -> results/
                                                                         validation/ checks every stage
run.py                 one command per step (see REPRODUCING.md)
REPRODUCING.md         step-by-step reproduction guide (REPRODUZINDO.md in Portuguese)
```

### Reproducing

Everything runs through one script, **`run.py`**, which calls the other folders in the right order and stops at the
first error. The full step-by-step guide, with what you should see after each step and what to do when something
fails, is in **[REPRODUCING.md](REPRODUCING.md)**.

```bash
pip install -r requirements.txt
python run.py paper        # A. the paper's numbers from the published data (~10 min, no credentials)
python run.py dashboard
```

To run the **whole study from scratch** (new catalogue, new generations, new verdicts), set `STUDY_DATA_DIR` /
`STUDY_RESULTS_DIR` to a new folder, configure `config.json` and run `collect`, `select`, `generate`, `extract`,
`submit`, `results`, `check`, `analysis` — see [REPRODUCING.md, part B](REPRODUCING.md#b-run-the-study-from-scratch).
What cannot be reproduced exactly: the LeetCode catalogue grows over time (reuse `data/problems/` to keep the same
sample — the selection is deterministic); Groq retired most of the 11 models after the study (they are open-weight
and can be served elsewhere, but generations may differ); the judge can change slightly over time.

### Pipeline fix (October 2026)

During the revision, the audit in `validation/` found three defects in the 2025 pipeline:

1. **Code extraction.** The case-insensitive search for the template label `solution:` also matched the `Solution:`
   of `class Solution:`, so the extracted code lost the class header and everything before it (imports included).
   Python3 was the most affected language.
2. **Judged language.** 389 submissions (380 Python3, 9 Java) were judged by LeetCode as C++.
3. **Judged problem.** `2-keys-keyboard` (problem 650) was resolved as id 2 and judged as another problem.

The corrected extractor is `pipeline/lib/extraction.py`, and step 5 now resolves slugs before ids and refuses
verdicts judged in another language. The raw responses were **not** regenerated: the corrected extractor was applied
to the stored responses, and the 2,560 affected submissions were re-judged on 16–18 October 2026 together with 100
unchanged control submissions (all 100 kept their verdict; memory readings were slightly higher, median ratio 1.03).
One re-judging is still pending (`llama-3.1-8b-instant`, Python3, problem 1358) and keeps its 2025 verdict.
The repository contains only the corrected dataset; the column `fonte` of `data/results.csv` tells whether each
verdict was obtained in 2025 (code unchanged by the fix) or in the 2026 re-judging.

### Credentials

Never versioned: `config.json` (LLM API key; LeetCode login for `submit_missing.py`), or the environment variables
`LLM_API_KEY`, `LEETCODE_SESSION`, `LEETCODE_CSRFTOKEN`, `LC_LOGIN_USER`, `LC_LOGIN_PASS`.

### License

MIT (see `LICENSE`). Contact: adenilson.ramos@ufape.edu.br

---

## Português

Pacote de replicação do artigo *"Correctness, Execution Time, and Memory Usage of LLM-Generated Code: A Large-Scale
Empirical Study on LeetCode"* (Ramos e Andrade, JBCS, em revisão). Versão arquivada:
https://zenodo.org/records/18771666

O repositório contém **todo o código e todos os dados** do estudo, da coleta do catálogo do LeetCode até as tabelas
do artigo, para que cada etapa possa ser conferida ou executada de novo.

### O estudo

Pedimos a **11 LLMs abertos e gratuitos** hospedados no Groq Cloud que resolvessem uma amostra estratificada de
**336 questões do LeetCode** (92 Easy, 169 Medium, 75 Hard) em **C++, Java e Python3**, com um único prompt zero-shot
(temperatura 0) e uma tentativa por (questão, linguagem, modelo). Dos 11.088 pedidos, **10.666** produziram código
julgado pelo LeetCode; os outros 422 não tinham código extraível. A aceitação geral é de **51,5%**; as três
linguagens têm aceitação parecida (C++ 50,3%, Java 51,9%, Python3 52,4%), e o modelo e a dificuldade são os fatores
determinantes. Java e C++ são mais rápidos; Python3 usa menos memória.

### Como o repositório está organizado

| Pasta | O que é | Detalhes |
|---|---|---|
| `pipeline/` | O estudo em código, em cinco etapas: coleta do catálogo → seleção da amostra → geração das soluções pelos LLMs → extração do código → submissão ao juiz do LeetCode e montagem da base final. | [`pipeline/README.md`](pipeline/README.md) |
| `data/` | Tudo o que foi coletado e produzido: catálogo e amostra, respostas brutas dos LLMs, registros do juiz, base final. | [`data/README.md`](data/README.md) |
| `validation/` | Verificações de integridade e a auditoria que encontrou e corrigiu os defeitos do pipeline de 2025. | [`validation/README.md`](validation/README.md) |
| `analysis/` | Estatísticas e modelo misto que geram todos os números e tabelas do artigo. | [`analysis/README.md`](analysis/README.md) |
| `results/` | Saídas de `analysis/` (geradas, não editar). | [`results/README.md`](results/README.md) |
| `dashboard/` | Dashboard interativo (Streamlit, inglês/português). | [`dashboard/README.md`](dashboard/README.md) |
| `run.py`, `REPRODUZINDO.md` | Um comando por etapa e o guia passo a passo. | [`REPRODUZINDO.md`](REPRODUZINDO.md) |

### Como reproduzir

Tudo roda por um único script, **`run.py`**, que chama as outras pastas na ordem certa e para no primeiro erro. O
passo a passo completo, com o que deve aparecer depois de cada etapa e o que fazer quando algo falha, está em
**[REPRODUZINDO.md](REPRODUZINDO.md)**.

```bash
pip install -r requirements.txt
python run.py paper        # A. os números do artigo a partir dos dados publicados (~10 min, sem credenciais)
python run.py dashboard
```

Para rodar o **estudo inteiro do zero** (novo catálogo, novas gerações, novos vereditos), aponte `STUDY_DATA_DIR` e
`STUDY_RESULTS_DIR` para uma pasta nova, configure o `config.json` e rode `collect`, `select`, `generate`, `extract`,
`submit`, `results`, `check` e `analysis` — ver [REPRODUZINDO.md, parte B](REPRODUZINDO.md#b-rodar-o-estudo-do-zero).
O que não se reproduz exatamente: o catálogo do LeetCode cresce (use `data/problems/` para manter a amostra — a
seleção é determinística); o Groq descontinuou a maioria dos 11 modelos (são abertos e podem ser servidos em outro
lugar, mas as respostas podem mudar); o juiz pode mudar um pouco com o tempo.

### Correção do pipeline (outubro de 2026)

Na revisão, a auditoria em `validation/` encontrou três defeitos no pipeline de 2025: (1) a busca do rótulo
`solution:` sem diferenciar maiúsculas também casava com `class Solution:`, e o código extraído perdia o cabeçalho
da classe e tudo antes dele; (2) 389 submissões foram julgadas como C++; (3) a questão 650 (`2-keys-keyboard`) foi
julgada como a questão 2. O extrator foi corrigido (`pipeline/lib/extraction.py`), as respostas brutas **não** foram
regeradas, e as 2.560 submissões afetadas foram rejulgadas em 16–18/10/2026, junto com 100 submissões de controle,
que mantiveram o veredito. Um rejulgamento ainda está pendente (`llama-3.1-8b-instant`, Python3, questão 1358).
O repositório contém só a base corrigida; a coluna `fonte` de `data/results.csv` indica se cada veredito foi obtido
em 2025 (código não alterado pela correção) ou no rejulgamento de 2026.

### Credenciais

Nunca versionadas: `config.json` (chave da API do LLM; login do LeetCode para `submit_missing.py`) ou as variáveis
de ambiente `LLM_API_KEY`, `LEETCODE_SESSION`, `LEETCODE_CSRFTOKEN`, `LC_LOGIN_USER`, `LC_LOGIN_PASS`.

### Licença

MIT (ver `LICENSE`). Contato: adenilson.ramos@ufape.edu.br
