# Validação das regras automáticas por classificação cega

**Classificador: modelo de linguagem sem acesso ao mapa, às flags e às sugestões (não é validação humana).** Na tabela, "humano" deve ser lido como "classificador".

Gerado por `validation/blind_validation/score.py`. Linhas classificadas: 100 de 100 ('?' conta como discordância).

| Estrato | n | humano = regra | % | IC 95% (Wilson) |
|---|---|---|---|---|
| A_confirmado_mecanicamente | 20 | 20 | 100.0% | 83.9% a 100.0% |
| A_nao_confirmado | 20 | 20 | 100.0% | 83.9% a 100.0% |
| B | 25 | 9 | 36.0% | 20.2% a 55.5% |
| C_formato_sensivel | 25 | 19 | 76.0% | 56.6% a 88.5% |
| TOTAL (sem indefinido) | 90 | 68 | 75.6% | 65.8% a 83.3% |

## Regra × humano

- n=90; concordância observada=0.756; esperada=0.328; **kappa=0.636** (IC 95% 0.520 a 0.752)

| Regra \ Humano | A | B | C | ? | total |
|---|---|---|---|---|---|
| A | 40 | 0 | 0 | 0 | 40 |
| B | 4 | 9 | 2 | 10 | 25 |
| C | 0 | 6 | 19 | 0 | 25 |
| ? | 0 | 0 | 0 | 0 | 0 |

## Distribuição humana por estrato

- A_confirmado_mecanicamente: A=20
- A_nao_confirmado: A=20
- B: ?=10, A=4, B=9, C=2
- C_formato_sensivel: B=6, C=19
- indefinido: B=10
