# Fase 4 — dry-run do pipeline corrigido (Revisor A, ponto A1)

Gerado por `validation/check_extraction.py` (Python 3.10.12). **Nada foi submetido.** Regras E1–E5, W1, S1 e S2 no cabeçalho do script.

## 1. O que mudaria

| Linguagem | Submissões | A ressubmeter | código mudou | linguagem errada | questão errada |
|---|---|---|---|---|---|
| C++ | 3522 | 300 | 290 | 0 | 11 |
| Java | 3536 | 437 | 418 | 9 | 11 |
| Python3 | 3608 | 1823 | 1568 | 380 | 11 |
| TODAS | 10666 | 2560 | 2276 | 389 | 33 |

### Por veredito original (Python3)

| Veredito | n | a ressubmeter | aderente (antigo) | aderente (corrigido) |
|---|---|---|---|---|
| Accepted | 1171 | 210 | 1171 | 1171 |
| Compile Error | 380 | 380 | 277 | 364 |
| Wrong Answer | 693 | 77 | 693 | 691 |
| Runtime Error | 1259 | 1133 | 113 | 1014 |
| Time Limit Exceeded | 76 | 11 | 76 | 76 |
| Memory Limit Exceeded | 7 | 3 | 7 | 7 |
| Timeout | 22 | 9 | 14 | 22 |

## 2. Confirmação mecânica das sugestões da triagem (não aceitas)

Um caso sugerido como A é **confirmado mecanicamente** quando o motivo é linguagem/questão errada, ou quando o código produzido pelo pipeline corrigido é aderente ao driver (Python: parseia e tem a classe/métodos/aridade do starter; C++/Java: cabeçalho), sem gerar código novo.

| Linguagem | Sugestão | n | corrigido aderente / motivo mecânico | % | a ressubmeter |
|---|---|---|---|---|---|
| C++ | A | 50 | 27 | 54.0% | 27 |
| C++ | B | 12 | 0 | 0.0% | 6 |
| C++ | C | 1699 | 1699 | 100.0% | 147 |
| C++ | indefinido | 43 | 0 | 0.0% | 20 |
| Java | A | 73 | 57 | 78.1% | 57 |
| Java | B | 18 | 0 | 0.0% | 6 |
| Java | C | 1763 | 1763 | 100.0% | 282 |
| Java | indefinido | 17 | 0 | 0.0% | 0 |
| Python3 | A | 1300 | 1294 | 99.5% | 1300 |
| Python3 | B | 265 | 24 | 9.1% | 231 |
| Python3 | C | 872 | 872 | 100.0% | 82 |

Para B e C, a coluna mostra quantos ficariam aderentes com o pipeline corrigido: em B espera-se pouco (a falha é do modelo); valores altos em B indicam regra da triagem a revisar.

## 3. Respostas nunca submetidas (422)

Informativo: com o extrator corrigido, quantas das 422 respostas classificadas como `invalid` na geração teriam código aderente. Submetê-las muda o denominador do artigo; é decisão dos autores.

| Linguagem | não submetidas | aderentes com o extrator corrigido |
|---|---|---|
| C++ | 174 | 9 |
| Java | 160 | 18 |
| Python3 | 88 | 0 |

## 4. Para a ressubmissão (Fase 4 propriamente dita — exige confirmação)

- `codigo_corrigido.jsonl` tem o código exato a enviar para cada linha com `ressubmeter=sim`.
- Mesma conta, mesmas linguagens, registro de data; checar a versão do Python no LeetCode.
- Ressubmeter também os casos cujo código mudou sem ser A (ex.: imports preservados), para que todo o conjunto passe pelo mesmo pipeline.
