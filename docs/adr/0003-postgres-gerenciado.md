# ADR 0003 — Postgres gerenciado, e dado fora do controle de versão

- **Status:** aceita
- **Data:** 2026-07-21

## Contexto

O v0 usava SQLite com o arquivo `soft_power.db` (36 KB, binário) commitado no
repositório, junto de três CSVs derivados do próprio pipeline.

Isso cria quatro problemas:

1. **Binário em git não tem diff útil.** Cada execução do pipeline gerava um blob
   novo, inflando o repositório sem informação legível de mudança.
2. **Confunde código com artefato.** Os CSVs eram *saída* do pipeline versionados
   como se fossem *entrada*, tornando ambíguo o que é fonte da verdade.
3. **SQLite não é acessível pela aplicação web.** Um arquivo local não serve uma
   aplicação Next.js hospedada na Vercel.
4. **Sem histórico.** Combinado com `if_exists='replace'`, cada rodada apagava o
   estado anterior.

## Decisão

**Postgres gerenciado no Supabase** como banco analítico e operacional.

**Nenhum dado no controle de versão.** `data/`, `*.db`, `*.parquet` e `*.sqlite`
entram no `.gitignore`. O repositório contém código, configuração e documentação —
nada mais.

**Camada bruta append-only.** Todo snapshot grava com `ingested_at`, sem sobrescrever.
O histórico é o ativo mais valioso do projeto: é o que permite série temporal e o que
não pode ser reconstruído retroativamente se for perdido.

## Alternativas consideradas

**Neon.** Tecnicamente atraente pelo branching de banco (uma branch de dados por PR,
ótimo de demonstrar). Preterido por ora porque já existe conta e credencial no
Supabase, e o Supabase oferece storage de objetos para os pôsteres no mesmo lugar.
Reavaliar se o branching virar necessidade real.

**DuckDB + parquet versionado.** Rejeitado como banco principal pelos mesmos motivos
do SQLite (não serve a aplicação web). DuckDB permanece no projeto, mas como
ferramenta de **exploração local** sobre os parquets — que é onde ele é excelente.

**Manter SQLite, sem commitar o arquivo.** Resolveria os problemas 1 e 2, não os 3 e 4.

## Consequências

**Positivas.** Repositório limpo e leve. A aplicação web tem uma fonte de dados real.
Séries temporais tornam-se possíveis. A separação código/dado fica explícita.

**Negativas.** Passa a existir uma dependência externa com credenciais: quem clonar o
repositório não roda o pipeline completo sem uma `TMDB_API_KEY` e um `DATABASE_URL`
próprios. Mitigação: `.env.example` documentado e, a partir da Fase 2, um conjunto
pequeno de dados de exemplo (*fixtures*) que permite rodar os testes sem rede nem
banco.
