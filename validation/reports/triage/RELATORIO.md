# Relatório da triagem (Fase 2, Revisor A, ponto A1)

Gerado por `validation/triage.py` (Python 3.10.12). Todos os números abaixo saem do script; semente de amostragem 20261012.

A triagem apenas SUGERE a categoria; a classificação A/B/C final é dos autores (Fase 3).

## 1. Reconciliação

- Linhas em `gen_all.jsonl`: 11088; em `sub_all.jsonl`: 10666.
- Junção (modelo com `/`→`_`, linguagem, id): 10666/10666 (100%).
- Linhas em `triagem_submissoes.csv`: 10666 (esperado 10666): OK.

### Veredito × linguagem vs. manuscrito

| Linguagem | Accepted | CE | WA | RE | TLE | MLE | Timeout | Total | Confere? |
|---|---|---|---|---|---|---|---|---|---|
| C++ | 1718 | 413 | 1099 | 160 | 118 | 11 | 3 | 3522 | SIM |
| Java | 1665 | 500 | 1094 | 142 | 126 | 8 | 1 | 3536 | SIM |
| Python3 | 1171 | 380 | 693 | 1259 | 76 | 7 | 22 | 3608 | SIM |

Resultado: **todas as células batem exatamente com o manuscrito**.

## 2. Números de sanidade (análise exploratória prévia × este script)

| Item | Esperado | Obtido | Comentário |
|---|---|---|---|
| Python3 julgadas como C++ (lang_pretty) | 380 | 380 | F10 |
| Java julgadas como C++ | 9 | 9 | F10 |
| Python RE: SyntaxError | 740 | 740 |  |
| Python RE: IndentationError | 34 | 34 |  |
| Python RE: NameError | 301 | 301 |  |
| Python com cabeçalho da classe perdido (F9: classe esperada na resposta bruta e ausente em `code`) | ~799 | 831 | F9 usa a classe esperada (inclui classes de design); só classe Solution: 799 |
| Python envelopadas pelo wrapper (`'class Solution' not in code`, mesmo teste do pipeline) | 1416 | 1416 |  |
| Âncora gemma2-9b-it / Python3 / 2586 → sugestão A | A | code='solution:'; submetido='class Solution:\n    solution:\n'; erro=SyntaxError; sugestão=A (regra 2); recon_validada=sim | OK |

## 3. Sugestão automática

### 3.1 Entre as submissões NÃO aceitas, por linguagem

| Linguagem | Não aceitas | A | B | C | indefinido |
|---|---|---|---|---|---|
| C++ | 1804 | 50 | 12 | 1699 | 43 |
| Java | 1871 | 73 | 18 | 1763 | 17 |
| Python3 | 2437 | 1300 | 265 | 872 | 0 |
| TODAS | 6112 | 1423 | 295 | 4334 | 60 |

### 3.2 Por linguagem × veredito (não aceitas)

| Linguagem | Veredito | n | A | B | C | indefinido |
|---|---|---|---|---|---|---|
| C++ | Compile Error | 413 | 50 | 12 | 308 | 43 |
| C++ | Wrong Answer | 1099 | 0 | 0 | 1099 | 0 |
| C++ | Runtime Error | 160 | 0 | 0 | 160 | 0 |
| C++ | Time Limit Exceeded | 118 | 0 | 0 | 118 | 0 |
| C++ | Memory Limit Exceeded | 11 | 0 | 0 | 11 | 0 |
| C++ | Timeout | 3 | 0 | 0 | 3 | 0 |
| Java | Compile Error | 500 | 73 | 18 | 392 | 17 |
| Java | Wrong Answer | 1094 | 0 | 0 | 1094 | 0 |
| Java | Runtime Error | 142 | 0 | 0 | 142 | 0 |
| Java | Time Limit Exceeded | 126 | 0 | 0 | 126 | 0 |
| Java | Memory Limit Exceeded | 8 | 0 | 0 | 8 | 0 |
| Java | Timeout | 1 | 0 | 0 | 1 | 0 |
| Python3 | Compile Error | 380 | 380 | 0 | 0 | 0 |
| Python3 | Wrong Answer | 693 | 0 | 17 | 676 | 0 |
| Python3 | Runtime Error | 1259 | 912 | 246 | 101 | 0 |
| Python3 | Time Limit Exceeded | 76 | 0 | 2 | 74 | 0 |
| Python3 | Memory Limit Exceeded | 7 | 0 | 0 | 7 | 0 |
| Python3 | Timeout | 22 | 8 | 0 | 14 | 0 |

### 3.3 Regra de CRITERIOS.md que decidiu (não aceitas)

| Linguagem | R1 (A) | R1b (A) | R2 (A) | R3 (A) | R4 (B) | R5 (B) | R6 (C) | R7 (indef.) |
|---|---|---|---|---|---|---|---|---|
| C++ | 0 | 11 | 39 | 0 | 12 | 0 | 1699 | 43 |
| Java | 9 | 11 | 53 | 0 | 18 | 0 | 1763 | 17 |
| Python3 | 380 | 10 | 910 | 0 | 265 | 0 | 872 | 0 |

### 3.4 Python3, Runtime Error: sugestão × tipo de exceção

| Exceção | n | A | B | C | indefinido |
|---|---|---|---|---|---|
| SyntaxError | 740 | 597 | 142 | 1 | 0 |
| NameError | 301 | 292 | 7 | 2 | 0 |
| TypeError | 103 | 0 | 71 | 32 | 0 |
| IndentationError | 34 | 14 | 20 | 0 | 0 |
| IndexError | 30 | 0 | 0 | 30 | 0 |
| AttributeError | 22 | 9 | 6 | 7 | 0 |
| ValueError | 17 | 0 | 0 | 17 | 0 |
| ZeroDivisionError | 4 | 0 | 0 | 4 | 0 |
| UnboundLocalError | 4 | 0 | 0 | 4 | 0 |
| KeyError | 3 | 0 | 0 | 3 | 0 |
| RecursionError | 1 | 0 | 0 | 1 | 0 |

Simetria: Compile Error em C++/Java = 413 + 500; Runtime Error em Python3 = 1259 (os 380 Compile Error de Python3 são todos de submissões julgadas como C++).

### 3.5 Python3: Runtime Error + Compile Error vs. C++/Java (CE + RE somados), por sugestão

| Linguagem | CE+RE | A | B | C | indefinido |
|---|---|---|---|---|---|
| C++ | 573 | 50 | 12 | 468 | 43 |
| Java | 642 | 73 | 18 | 534 | 17 |
| Python3 | 1639 | 1292 | 246 | 101 | 0 |

## 4. Reconstrução do código submetido

Validação = linha `N` do erro, com a linha ecoada na mensagem, bate com a linha `N` do código reconstruído (espaços colapsados). Só há validação quando a mensagem ecoa a linha e `N` cai dentro do código reconstruído (frames do driver são ignorados); `sem_info` não entra na taxa.

| linguagem | script | estrato | n_total | n_aceitas_sem_erro_para_validar | sim | nao | sem_info | taxa_validacao_entre_com_info |
|---|---|---|---|---|---|---|---|---|
| (todas) | (ambos) | todas | 10666 | 4554 | 2087 | 0 | 4025 | 1.0000 |
| C++ | (ambos) | todas | 3522 | 1718 | 370 | 0 | 1434 | 1.0000 |
| C++ | submit_missing | todas | 11 | 6 | 3 | 0 | 2 | 1.0000 |
| C++ | submit_problems | todas | 3511 | 1712 | 367 | 0 | 1432 | 1.0000 |
| Java | (ambos) | todas | 3536 | 1665 | 436 | 0 | 1435 | 1.0000 |
| Java | submit_missing | todas | 10 | 0 | 9 | 0 | 1 | 1.0000 |
| Java | submit_problems | todas | 3526 | 1665 | 427 | 0 | 1434 | 1.0000 |
| Python3 | (ambos) | todas | 3608 | 1171 | 1281 | 0 | 1156 | 1.0000 |
| Python3 | submit_missing | todas | 492 | 18 | 406 | 0 | 68 | 1.0000 |
| Python3 | submit_problems | todas | 3116 | 1153 | 875 | 0 | 1088 | 1.0000 |

Por estrato de incerteza (F15):

| linguagem | script | estrato | n_total | n_aceitas_sem_erro_para_validar | sim | nao | sem_info | taxa_validacao_entre_com_info |
|---|---|---|---|---|---|---|---|---|
| C++ | submit_missing | recon_incerta=nao | 11 | 6 | 3 | 0 | 2 | 1.0000 |
| C++ | submit_problems | recon_incerta=nao | 2045 | 850 | 212 | 0 | 983 | 1.0000 |
| C++ | submit_problems | recon_incerta=sim | 1466 | 862 | 155 | 0 | 449 | 1.0000 |
| Java | submit_missing | recon_incerta=nao | 10 | 0 | 9 | 0 | 1 | 1.0000 |
| Java | submit_problems | recon_incerta=nao | 2048 | 782 | 265 | 0 | 1001 | 1.0000 |
| Java | submit_problems | recon_incerta=sim | 1478 | 883 | 162 | 0 | 433 | 1.0000 |
| Python3 | submit_missing | recon_incerta=nao | 492 | 18 | 406 | 0 | 68 | 1.0000 |
| Python3 | submit_problems | recon_incerta=nao | 1790 | 571 | 547 | 0 | 672 | 1.0000 |
| Python3 | submit_problems | recon_incerta=sim | 1326 | 582 | 328 | 0 | 416 | 1.0000 |

Divergências de validação (`nao`) por linguagem: C++=0, Java=0, Python3=0.

## 5. Amostra para a Fase 3

- `amostra_fase3.csv`: 860 Runtime Errors de Python obrigatórios (F1>1, F2 falso, F4=sim ou F7=sim) + 100 amostrados dos 399 demais (estratificação proporcional ao nº de RE de cada modelo entre os demais; alvo total 100).

## 6. Ambiguidades, decisões conservadoras e limitações

- **Candidatos do bruto**: blocos cercados (regex do extrator, cercas de 3+ crases ou til), cerca final aberta e nunca fechada (resposta truncada), e o trecho após o rótulo `solution:` somente quando não contém cerca. O rótulo é buscado no INÍCIO de linha, diferente do regex do extrator (`(?i)solution\s*:`), que casa também com `class Solution:` e é a causa do cabeçalho perdido. `<think>…</think>` é removido (também `<think>` sem fechamento e `</think>` órfão).
- **F1** conta as cercas pareadas na resposta bruta INTEIRA (inclui eventuais blocos dentro de `<think>`, que é o que o extrator enxerga).
- **Aderência tolerante (F14)** é cumulativa (estrito OU tolerante) e, como em CRITERIOS.md, só está definida para Python: só funções/imports/docstring no nível do módulo, métodos esperados com `self`, e após envolver na classe esperada o candidato fica aderente. **Em C++/Java a tolerância não está definida** (não há `self` nem wrapper): resposta com todos os cabeçalhos esperados mas SEM a classe recebe `ader_bruto_tolerante=so_metodos` e sugestão `indefinido` (regra 7) em vez de A (a regra 2 a faria A, mas o pipeline não envelopa C++/Java, então a ausência da classe é do modelo). Ocorrências (não aceitas): C++=43, Java=17. **F16 coincide com `ader_bruto_tolerante=sim`** (definição do enunciado), portanto é redundante com F14.
- **Construtor implícito**: CRITERIOS.md exige que TODOS os métodos do starter existam, incluindo `__init__`/construtor. Seguido à letra. Uma classe de design sem construtor de 0 parâmetros é aceita pelo driver (construtor implícito), então esse critério pode produzir B espúrio. Casos B (regra 4, não aceitos) que passariam a ter bruto aderente se o construtor implícito de 0 parâmetros fosse aceito: C++=1, Java=1, Python3=0 (não alterados na sugestão; coluna não exportada, número apenas informativo).
- **C++/Java** são verificados só por regex de cabeçalho (nome + contagem de parâmetros no nível superior, `<>` e `()` respeitados, parâmetros com valor padrão opcionais); a definição deve ser seguida de `{` (ou `const`/`override`/`throws`/lista de inicialização), de modo que protótipos terminados em `;` não contam. Não verifica retorno, tipos nem se o método está dentro da classe.
- **Aderência em Python** usa a última definição da classe/método; `@staticmethod` não desconta `self`; parâmetros extras sem padrão tornam o método não aderente.
- **F3 (stmts_modulo)**: conta instruções de módulo que não sejam classe, função, import, docstring, `pass`, ou atribuição sem chamada. `if __name__…`, `print`, chamadas soltas, `for`, `with` e atribuições com chamada (`sol = Solution()`) contam. Como o wrapper indenta tudo dentro de `class Solution:`, o F3 só dispara quando o modelo já trouxe a classe.
- **F4 (erro_fora_classe)** usa o PRIMEIRO frame do traceback (o mais interno; o LeetCode lista o mais interno primeiro). `driver` = a linha do frame excede o tamanho do código reconstruído (código do driver do LeetCode, anexado depois), contabilizado à parte e NÃO como `sim` (358 casos). Só é calculado para Runtime Error de Python julgado em Python. Se a classe esperada não existe no código submetido, a linha é considerada fora dela.
- **Validação da reconstrução**: exige eco da linha na mensagem; Runtime Error de C++ (sanitizers) e Java (`at line N`) não ecoam a linha e ficam `sem_info`; Accepted não tem erro e fica `sem_info`. Para Python julgado como C++ usa-se o eco no formato `N | texto` do clang.
- **F15 (recon_incerta)**: submissões anteriores a 2025-09-17 20:34 UTC, a submissão de 2025-10-09 e as sem código reconstruível (0). O instante do commit foi tomado de CRITERIOS.md; não há `.git` no espelho para conferir.
- **Código lido do cache atual**: a reconstrução usa `code`/`resposta` de `gen_all.jsonl`, i.e. o JSON como está hoje; `reavaliado_em` (2025-08-17) é anterior a todas as submissões, mas edições posteriores não são rastreáveis. A validação por linha é a evidência independente (seção 4).
- **F2/F3/F14 dependem do `ast` do interpretador usado** (esta execução: Python 3.10.12). Gramática de versões mais novas (por exemplo f-strings aninhadas, PEP 701, aceitas em 3.12+) pode não parsear em 3.10 e inflar `nao_parseavel`; o LeetCode usa outra versão. Comparar F2=nao entre interpretadores antes de fechar números.
- **F13 (think_ou_prosa)**: `think` = a resposta bruta contém `<think>`/`</think>` (modelos de raciocínio; não é erro por si só); `code_em_think` = o campo `code` é um trecho do bloco de raciocínio; `prosa` = heurística (linha ≥20 caracteres, ≥5 palavras, sem símbolos de código, fora de comentários/docstrings), sujeita a falsos positivos e negativos.
- **F7**: conjunto fixo de classes fornecidas pelo LeetCode (ArrayReader, BinaryMatrix, Employee, ImmutableListNode, Interval, ListNode, Master, MountainArray, NestedInteger, Node, Plane, Point, Quad, Reader, Relation, Robot, Sea, TreeNode, VersionControl). Redefinir em Python normalmente é inofensivo; em C++/Java costuma causar erro de compilação.
- **F10**: 26 submissões não trazem `lang_pretty` (Timeouts) → `sem_info`, NÃO tratadas como F10. Submissões Accepted com F10=sim: 0.
- **Regra 5 e casos mistos**: a regra 5 exige que as instruções soltas do submetido já constem do melhor candidato bruto (aderente, com menos instruções de módulo). Quando o submetido tem instruções soltas e erro fora da classe mas elas NÃO estavam no melhor candidato (o extrator as acrescentou), o caso é misto e foi para `indefinido` (regra 7) em vez da regra 6 (C), conforme a introdução de CRITERIOS.md. Ocorrências: 0. Total de `indefinido` entre as não aceitas: 60.
- **Regra 4** é aplicada à letra: bruto não aderente → B, mesmo quando o extrator piorou o resultado. WA/TLE/MLE sugeridos B: 19; destes o submetido era aderente em 19 (indício de falso negativo da checagem de aderência, ou de extração que 'consertou' a resposta); vale revisão manual.
- **Amostra da Fase 3**: ~100 amostrados NO TOTAL (não por modelo), com alocação proporcional ao tamanho de cada modelo entre os demais RE de Python (maior resto), semente 20261012. Se a intenção era ~100 POR modelo, ajustar `total_alvo` em `amostra_fase3`.
- **Destaque em `resumo_por_questao.csv`**: limiar `>=5` modelos com Python falhando e C++ e Java passando no mesmo modelo é escolha operacional (cerca de metade dos 11 modelos), não vem de CRITERIOS.md.
- **F17 (questao_errada_juiz)**, adicionada na revisão da sessão principal: o `resolve_question` do pipeline lê um slug que começa com `<dígitos>-` como frontend id; em `2-keys-keyboard` (questão 650) o question_id enviado foi o da questão 2 e o driver chamou `addTwoNumbers`. As 33 submissões da questão 650 (3 linguagens) foram julgadas em outra questão; regra 1b → A. Única questão da amostra com slug iniciado por dígito.
- **Dificuldade** vem de `sample.csv`; **eh_design** = classe esperada do starter Python diferente de `Solution`; **F11** só para Python.

## 7. Tempo

Execução do script até esta linha: 18.5 s (meta < 180 s).
