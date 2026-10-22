# Critérios da triagem — Revisor A, ponto A1 (Fase 2)

Este documento fixa as regras ANTES de rodar a triagem. A triagem só sugere uma categoria. A classificação
final A/B/C é feita pelos autores (Adenilson e Rodrigo) na Fase 3, e o kappa de Cohen é calculado sobre ela.

## Categorias

| Cat. | Definição operacional |
|---|---|
| A — Artefato do pipeline | A resposta bruta contém um programa aderente ao driver do LeetCode, e o código submetido deixou de ser aderente ou passou a falhar por algo introduzido pela extração, pelo wrapper ou pela submissão. Também é A: submissão julgada em outra linguagem. |
| B — Descumprimento de formato | Nenhum candidato da resposta bruta é aderente ao driver: classe/método/aridade errados, só raciocínio, texto ou rótulo dentro do próprio bloco de código, testes ou entrada (input) que quebram a execução. |
| C — Erro genuíno | O código submetido é parseável e aderente, e falha com exceção de execução (IndexError, TypeError interno, RecursionError, …), Wrong Answer, TLE ou MLE. |

Casos mistos (por exemplo, o modelo responde fora do formato e o extrator piora o resultado) ficam com sugestão `indefinido` e vão para a revisão manual.

## Aderência ao driver (F14), por questão

O esperado sai do starter da própria questão (`datasets/leetcode/sample.csv`, coluna `starter_code`):

- classe esperada = primeira classe declarada no starter (Solution ou classe de design);
- métodos esperados = todos os métodos do starter (incluindo `__init__` / construtor nas questões de design);
- aridade = número de parâmetros posicionais, sem contar `self`.

Um programa é aderente quando:

- declara a classe esperada;
- cada método esperado existe dentro dela;
- cada um desses métodos aceita a aridade do starter.

Tolerâncias:

- nomes de parâmetros e anotações de tipo podem diferir, porque o LeetCode chama por posição;
- métodos, funções e classes auxiliares a mais são permitidos;
- parâmetros extras com valor padrão são permitidos.

Em C++/Java, a verificação é por cabeçalho (nome do método e contagem de parâmetros no nível superior), sem compilar.

A aderência é avaliada em três estágios:

1. `bruto`: melhor candidato da resposta bruta. Os candidatos são todos os blocos cercados e o trecho após o rótulo `solution:`, com `<think>…</think>` removido. Há dois níveis:
   - estrito: o candidato já tem a classe;
   - tolerante: são só métodos com `self` que, envolvidos na classe esperada, ficariam aderentes.
2. `extraido`: o campo `code`.
3. `submetido`: o código reconstruído como foi enviado.

## Reconstrução do código submetido

- Script por data (`ts_epoch`, UTC): antes de 2025-10-13 → `submit_problems.py`; a partir de 2025-10-13 → `submit_missing.py`.
- Reconstrução incerta (F15): submissões anteriores a 2025-09-17 20:34 UTC (commit 6cbda464) e a linha de 2025-10-09.
- Validação: quando o erro traz `Line N` e ecoa a linha ofensiva, comparar com a linha N reconstruída.

## Sugestão automática (ordem de precedência)

1. F10 (julgada em outra linguagem) → A
1b. F17 (julgada em outra questão: slug iniciado por `<dígitos>-` lido como frontend id pelo `resolve_question`; caso da questão 650 `2-keys-keyboard`, julgada como a questão 2) → A. Regra adicionada depois da 1ª execução, ao se encontrar o bug.
2. Bruto aderente (estrito ou tolerante) e submetido não aderente ou não parseável → A
3. F9 (cabeçalho da classe perdido na extração) com bruto aderente → A
4. Bruto não aderente em todos os candidatos → B
5. Submetido com instruções no nível do módulo (F3) e linha do erro fora da classe (F4), quando essas instruções já estavam no melhor candidato bruto → B (testes/print/input deixados pelo modelo)
6. Submetido parseável, aderente e veredito não Accepted → C (em C++/Java, Compile Error em código aderente também conta como C)
7. Demais → indefinido
