# Data

*Resumo em português no fim da página. Step-by-step reproduction guide: [REPRODUCING.md](../REPRODUCING.md) / [REPRODUZINDO.md](../REPRODUZINDO.md).*

Everything the study collected or produced, in the order of the pipeline. Raw records are never edited by hand:
each file is written by the script named below (see `pipeline/README.md`).

| Path | Written by | Content |
|---|---|---|
| `problems/` | step 1, step 2 | LeetCode catalogue and the 336-problem sample |
| `generations/<model>/<language>/<id>.json` | step 3, step 4 | raw response of each LLM to each problem |
| `submissions/<model>__<language>.ndjson` | step 5 | judge record of each submission (2025) |
| `rejudging_2026/` | step 5b (`rejudge.py --export`) | re-judging after the October 2026 pipeline fix |
| `results.csv` | `build_results.py` | **final dataset analysed in the paper** |
| `.cache/` | several | local caches, progress files and logs; not versioned |

## `problems/`

- `questions/<id>_<slug>.json`: one LeetCode problem: `id` (frontend id), `slug`, `url`, `titulo`, `enunciado`
  (statement as text), `temas` (topics), `tema_principal`, `dificuldade` (Fácil/Média/Difícil), `has_image`,
  `stats` (global LeetCode statistics, incl. `totalSubmissionRaw` and `acRate`), `starter_code` (cpp/java/python3),
  `code_snippets`, `hints`, `example_testcases`, `top_solutions` and other community data.
- `easy.json`, `medium.json`, `hard.json`, `public_problems*.json`: the same records grouped; `report.json`: counts.
- `sample.csv`: the 336 problems of the study (92 Easy, 169 Medium, 75 Hard) with `id, slug, url, titulo,
  enunciado, temas, dificuldade, tema_principal, has_image, starter_code, stats`.

## `generations/<model>/<language>/<id>.json`

11 models × 3 languages × 336 problems = 11,088 files (model folder = model id with `/` replaced by `_`).

| Field | Meaning |
|---|---|
| `id`, `modelo`, `linguagem`, `timestamp` | problem, model, language, generation time |
| `resposta` | raw text returned by the model (never modified) |
| `status` | `ok` or `erro` (API failure) |
| `categoria`, `motivo` | `correct` / `plausible` / `invalid` and reason (step 3). `invalid` = no code found; not submitted |
| `code` | code sent to LeetCode, produced from `resposta` by the corrected extractor (step 4) |

## `submissions/<model>__<language>.ndjson`

One JSON line per submission judged in 2025 (10,666). Main fields: `modelo`, `linguagem`, `id_questao`, `slug`,
`status` (verdict), `aceito`, `tempo_ms`, `memoria_mb` (accepted only), `compilou`, `testes_passados`,
`total_testes`, `submission_id`, `lang_pretty` (language reported by the judge), `erro_compilacao`, `erro_runtime`,
`ultimo_caso_teste`, `saida_esperada`, `sua_saida`, `categoria_declarada` (= generation category),
`categoria_calculada` (implied by the verdict), `ts_epoch`.

## `rejudging_2026/`

- `rejudged.ndjson`: 2,559 submissions re-judged on 16–18 October 2026 with the code of the corrected pipeline
  (same fields as above plus `motivos`, `data_utc`, `via` = `script` or `navegador`).
- `control.ndjson`: 100 unchanged submissions re-judged as a control of judge drift (all kept their verdict).

## `results.csv` (final dataset)

One row per judged submission (10,666), built by `pipeline/5_submit/build_results.py`.

| Column | Meaning |
|---|---|
| `modelo`, `linguagem`, `slug`, `id_questao` | model folder, language, problem slug and frontend id |
| `status`, `aceito` | verdict and whether it was accepted |
| `tempo_ms`, `memoria_mb` | runtime and peak memory reported by the judge (accepted only) |
| `submission_id` | LeetCode submission id |
| `categoria_declarada`, `categoria_calculada`, `categoria_ok` | generation category, category implied by the verdict, agreement |
| `data_julgamento` | date of the verdict |
| `fonte` | `2025` (code unchanged by the pipeline fix, verdict of 2025) or `2026` (re-judged after the fix); `judge` in a run without re-judging |

---

## Resumo em português

`problems/` guarda o catálogo do LeetCode e a amostra de 336 questões; `generations/` guarda a resposta bruta de cada
LLM (campo `resposta`, nunca alterado) e o código enviado ao juiz (`code`, gerado pelo extrator corrigido);
`submissions/` tem os registros do juiz de 2025; `rejudging_2026/` o rejulgamento após a correção do pipeline;
`results.csv` é a base final do artigo, uma linha por submissão julgada (a coluna `fonte` diz se o veredito é de 2025
ou do rejulgamento de 2026).
