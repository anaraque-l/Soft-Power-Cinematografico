# ADR 0004 — Camada bruta em parquet particionado por data de ingestão

- **Status:** aceita
- **Data:** 2026-07-27

## Contexto

O [ADR 0003](0003-postgres-gerenciado.md) decidiu *onde* o dado analítico vive
(Postgres gerenciado) e que a camada bruta é append-only. Faltava decidir *como*
a ingestão grava, e esta decisão precisa ser tomada antes da primeira linha de
dado entrar — depois, migrar histórico é caro e arriscado.

O v0 errava em dois pontos que são, na prática, o mesmo erro: descartar
informação cedo demais.

1. `if_exists="replace"` a cada execução. Não havia "semana passada".
2. `groupby(pais).agg(join)` na primeira transformação. Cinco países viravam
   cinco linhas de texto concatenado, e o grão de filme deixava de existir
   antes de qualquer análise.

O ISPC tem grão país × ano e depende de detecção de *changepoint* (a pergunta
sobre o Hallyu coreano) — ou seja, é uma série temporal por definição. Sem
histórico versionado, a fase mais importante do projeto fica impossível.

## Decisão

**Parquet particionado no estilo Hive, por data de ingestão:**

```
data/raw/<dataset>/ingested_date=AAAA-MM-DD/part-NNNN.parquet
```

**Três datasets, cada um no seu grão natural**, sem agregação na ingestão:

| dataset | uma linha é... |
|---|---|
| `tmdb_movies` | um filme, num país-alvo, num ano |
| `tmdb_release_dates` | um evento de lançamento (filme × país × tipo) |
| `tmdb_watch_providers` | uma disponibilidade (filme × país × provedor × tipo) |

**Toda linha carrega `ingested_at`** (UTC, ciente de fuso). O que se pode
reconstruir depois não é só o dado, é *o que sabíamos e quando*.

**Nunca sobrescrever, nem dentro do mesmo dia.** Uma segunda execução na mesma
data grava `part-0001.parquet` ao lado de `part-0000.parquet`. Um retry manual
ou um `workflow_dispatch` extra não podem apagar o que já foi coletado.

**Nenhuma resolução de conflito na ingestão.** Coprodução faz o mesmo filme
aparecer na consulta de mais de um país; a camada bruta registra `pais_alvo`
(por qual consulta a linha entrou) e deixa a atribuição para o dbt. Decidir
cedo é decidir sem poder revisar.

## Alternativas consideradas

**Gravar direto no Postgres, sem parquet.** É o destino final do dado, mas
tornaria a ingestão indisponível para quem clona o repositório sem banco, e
acopla a coleta à disponibilidade de um serviço externo. O parquet funciona
offline, é lido pelo DuckDB sem infraestrutura nenhuma, e o carregamento no
Postgres vira uma etapa separada e re-executável na Fase 2.

**Um único dataset desnormalizado.** Mais simples de consultar, mas repetiria
os metadados do filme em cada uma das ~110 linhas de disponibilidade que ele
gera — e, pior, forçaria uma decisão de junção na ingestão. Três grãos
separados preservam a possibilidade de decidir depois.

**JSON bruto, exatamente como a API devolveu.** Máxima fidelidade e o registro
mais defensável do que a fonte disse. Preterido por custo de leitura: o
aninhamento do TMDB (país → lista de eventos) exigiria desaninhar em toda
consulta. O achatamento feito na ingestão é reversível e não perde informação
que o projeto use.

**Particionar por `país` ou por `ano` do filme.** Ambos são atributos do dado,
não da coleta — e mudam de valor conforme o TMDB corrige seus registros.
Particionar pela data de ingestão é o único recorte imutável depois de escrito.

## Consequências

**Positivas.** O histórico acumula automaticamente e é o ativo que não se
recompra. `SELECT * FROM 'data/raw/tmdb_movies/**/*.parquet'` funciona no
DuckDB sem configuração, com `ingested_date` já como coluna. O dbt lê o mesmo
layout. Reprocessar é sempre possível, porque o dado bruto nunca foi
descartado.

**Negativas.** Muitos arquivos pequenos ao longo do tempo — uma coleta semanal
por 5 anos são ~260 partições por dataset. Aceitável nessa ordem de grandeza;
se incomodar, uma compactação periódica resolve sem mudar o contrato de
leitura. E, enquanto o Postgres não estiver provisionado, o cron do GitHub
Actions depende de artefatos de execução para persistir entre rodadas, com a
retenção limitada que isso impõe (90 dias).
