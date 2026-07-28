# 🎬 Soft Power Cinematográfico

[![CI](https://github.com/anaraque-l/Soft-Power-Cinematografico/actions/workflows/ci.yml/badge.svg)](https://github.com/anaraque-l/Soft-Power-Cinematografico/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**O cinema é um instrumento mensurável de poder brando?**

Este projeto constrói um índice autoral — o **ISPC (Índice de Soft Power Cinematográfico)** —
para responder quais países convertem produção cinematográfica em influência cultural
global, e quais produzem muito sem exportar quase nada.

> 🚧 **Status: em reconstrução ativa (Fase 1 de 7).**
> O protótipo original está preservado na tag [`v0-streamlit`](../../tree/v0-streamlit).
> As decisões de arquitetura estão registradas nos [ADRs](docs/adr/).

---

## Por que reconstruir

A primeira versão deste projeto (Streamlit + SQLite) tinha um defeito que nenhuma
melhoria de interface resolveria: **ela não media soft power**. A métrica era o campo
`popularity` da API do TMDB — um score interno de engajamento na plataforma, não
normalizado e enviesado para o público anglófono. Na prática, o "termômetro cultural"
do Brasil media quantos cliques filmes brasileiros receberam no TMDB naquela semana.

Havia ainda um problema estrutural: a primeira transformação agregava os cinco filmes
de cada país em uma única linha de texto concatenado, destruindo o grão do dado. Depois
disso, nenhuma pergunta interessante era mais respondível.

A reconstrução mantém a tese e troca a fundação. O diagnóstico completo do v0 e o
racional de reconstruir em vez de refatorar estão no
[ADR 0002](docs/adr/0002-reconstrucao-do-v0.md).

## O índice

O ISPC tem grão **país × ano** e compõe cinco dimensões, cada uma normalizada em
percentil dentro do ano:

| Dimensão | O que captura | Fonte |
|---|---|---|
| **Alcance** | Em quantos mercados a obra efetivamente chega | TMDB (lançamentos e streaming por país) |
| **Penetração externa** | Se a audiência é doméstica ou global | TMDB + World Bank (população) |
| **Prestígio** | Reconhecimento institucional (Cannes, Berlinale, Veneza, Oscar) | Wikidata (SPARQL) |
| **Capacidade** | Volume de produção anual | UNESCO Institute for Statistics |
| **Persistência** | Cânone duradouro vs. sucesso passageiro | Séries históricas próprias |

O índice vem acompanhado de **análise de sensibilidade dos pesos** (o ranking é estável
quando os pesos mudam?) e de **validação externa** por correlação de Spearman contra o
*Brand Finance Global Soft Power Index*.

As limitações conhecidas — viés anglocêntrico do TMDB, opacidade dos dados chineses,
gosto curatorial europeu embutido na dimensão de prestígio — são documentadas em
`docs/LIMITACOES.md` (Fase 3). **Um índice sem limitações declaradas não é um índice,
é um chute com decimais.**

## Arquitetura

```
INGESTÃO (Python)        →  TMDB · Wikidata · UNESCO · World Bank
  httpx + pydantic + tenacity → parquet datado + Postgres (camada bruta)
        ↓
MODELAGEM (dbt + SQL)    →  bronze (append-only) → silver → gold
        ↓                    com testes de contrato e lineage
ANÁLISE (Python/marimo)  →  cálculo do ISPC, sensibilidade, validação
        ↓
POSTGRES (Supabase)
        ↓
APLICAÇÃO (Next.js + TypeScript)  →  globo WebGL, comparador, metodologia

ORQUESTRAÇÃO: GitHub Actions (cron semanal)
```

O projeto é poliglota **de propósito**: Python na camada de dados, TypeScript na entrega.
O racional dessa fronteira está no [ADR 0001](docs/adr/0001-arquitetura-poliglota.md), e
a escolha do banco no [ADR 0003](docs/adr/0003-postgres-gerenciado.md).

## Como rodar

Requer Python 3.11+.

```bash
git clone https://github.com/anaraque-l/Soft-Power-Cinematografico.git
cd Soft-Power-Cinematografico

python -m venv .venv
source .venv/Scripts/activate      # Windows (Git Bash)
# .venv\Scripts\Activate.ps1       # Windows (PowerShell)
# source .venv/bin/activate        # Linux / macOS

pip install -e ".[dev]"
pytest
```

```bash
ruff check .        # lint
ruff format .       # formatação
pytest --cov=ingestion
```

### Rodar a ingestão

Copie `.env.example` para `.env` e preencha a `TMDB_API_KEY` — a chave é gratuita e sai
em minutos em [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api).
Tanto a chave v3 quanto o *read access token* v4 funcionam.

```bash
# corte vertical: 5 países, 1 ano, top 20 filmes de cada
python -m ingestion.pipelines.tmdb_coleta \
    --anos 2023 --paises BR,KR,FR,US,NG --max-paginas 1

python -m ingestion.pipelines.tmdb_coleta --anos 2019-2023   # escopo completo
python -m ingestion.pipelines.tmdb_coleta --anos 2023 --dry-run
```

Cada execução grava uma partição nova em `data/raw/<dataset>/ingested_date=AAAA-MM-DD/`
— **nunca** sobrescreve a anterior. É o que torna o ISPC uma série temporal, e é
exatamente o que o v0 destruía a cada rodada com `if_exists="replace"`.

Três datasets saem daí, cada um no seu grão:

| dataset | uma linha é... |
|---|---|
| `tmdb_movies` | um filme, num país-alvo, num ano |
| `tmdb_release_dates` | um evento de lançamento (filme × país × tipo) |
| `tmdb_watch_providers` | uma disponibilidade (filme × país × provedor) |

O racional do formato e do particionamento está no
[ADR 0004](docs/adr/0004-camada-bruta-em-parquet-particionado.md).

### Testes marcados como `pendente`

Parte do código é desenvolvida com os testes escritos antes da implementação. Esses
testes ficam marcados como `pendente` — rodam localmente (são a lista de tarefas) e o
CI os desmarca com `-m "not pendente"`, para não pintar de vermelho o que ainda não
começou.

```bash
pytest                      # tudo, inclusive o que falta implementar
pytest -m "not pendente"    # o que o CI mede
```

## Escopo

35 países, cobrindo todos os continentes — potências cinematográficas consolidadas e
países com produção relevante mas baixa projeção externa. O contraste entre os dois
grupos é justamente o que o índice quer medir. A lista está em
[`ingestion/countries.yml`](ingestion/countries.yml) e é validada no CI.

## Roadmap

| Fase | Entrega | Status |
|---|---|---|
| 0 | Fundação: estrutura, tipagem, testes, CI | ✅ concluída |
| 1 | Ingestão preservando o grão de filme, com histórico datado | 🔨 em andamento |
| 2 | Modelagem dbt: bronze → silver → gold, com testes de contrato | ⏳ |
| 3 | **O índice**: metodologia, sensibilidade, validação externa | ⏳ |
| 4 | Enriquecimento: prêmios (Wikidata), UNESCO, análise cromática | ⏳ |
| 5 | Aplicação Next.js + deploy | ⏳ |
| 6 | Camada de leitura por LLM, com citação de fonte | ⏳ |
| 7 | Vitrine: ADRs, documentação, post técnico | ⏳ |

## Licença

[MIT](LICENSE)
