# ADR 0001 — Arquitetura poliglota: Python nos dados, TypeScript na entrega

- **Status:** aceita
- **Data:** 2026-07-21

## Contexto

O v0 era inteiramente Python (Streamlit). A motivação inicial da reconstrução era
"sair do Streamlit e fazer em Node/JavaScript". A tentação natural era reescrever
tudo em JavaScript, inclusive a camada de dados.

Dois objetivos do projeto estão em tensão:
1. Demonstrar competência em ciência de dados e engenharia de dados.
2. Demonstrar competência em arquitetura e frontend moderno.

## Decisão

O projeto é poliglota, com fronteira explícita:

- **Python** — ingestão, modelagem (dbt) e análise. Termina no Postgres.
- **TypeScript / Next.js** — aplicação e API. Começa no Postgres.
- **Postgres** é o contrato entre as duas metades. Nenhuma lógica de negócio
  atravessa essa fronteira.

## Alternativas consideradas

**Tudo em JavaScript.** Rejeitada. Eliminaria justamente a evidência de ciência de
dados que o projeto existe para produzir. O ecossistema analítico em JS (Danfo.js,
por exemplo) é imaturo comparado a pandas/dbt, e dbt não tem equivalente em Node.
Seria mais trabalho por menos demonstração.

**Tudo em Python (Streamlit ou Dash).** Rejeitada. Simples, mas impede demonstrar
arquitetura de sistema, tipagem estática e frontend — e limita o controle sobre a
interface, que é parte do produto aqui.

**Python + FastAPI, sem Next.js.** Rejeitada por ora. Seria mais um serviço para
deployar sem ganho imediato: as consultas da aplicação são leituras de tabelas já
materializadas, que os Route Handlers do Next resolvem. Reconsiderar se surgir
necessidade de cálculo sob demanda (ex.: recalcular o índice com pesos escolhidos
pelo usuário) — nesse caso, FastAPI entra como serviço de análise.

## Consequências

**Positivas.** Cada linguagem faz o que faz melhor. A fronteira é defensável e
explicável numa conversa técnica. Permite evoluir as duas metades em ritmos
independentes.

**Negativas.** Dois ambientes de desenvolvimento (venv e node_modules), dois
conjuntos de ferramentas de lint e teste, e dois pipelines de CI. Custo aceito
conscientemente: é o mesmo custo que a maioria das empresas de dados paga.

**Risco.** Duplicação de lógica na fronteira (ex.: formatação de nomes de país nos
dois lados). Mitigação: tudo que for regra de negócio fica no dbt; o TypeScript só
lê e apresenta.
