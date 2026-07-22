# ADR 0002 — Reconstruir o v0 em vez de refatorar

- **Status:** aceita
- **Data:** 2026-07-21

## Contexto

O v0 (tag [`v0-streamlit`](../../../tree/v0-streamlit)) tinha ~200 linhas de Python
distribuídas em três arquivos: extração do TMDB, geração de análises por LLM e uma
interface Streamlit. Funcionava de ponta a ponta.

O diagnóstico apontou oito problemas. Três são estruturais, não incrementais:

1. **A métrica não media o fenômeno.** O índice era `popularity.mean()` dos cinco
   filmes mais populares por país. `popularity` é um score interno de engajamento do
   TMDB (visitas, buscas na semana), não normalizado por população nem por tamanho de
   mercado, e enviesado para a base de usuários da plataforma — majoritariamente
   anglófona. Não é uma aproximação ruim de soft power; é outra coisa.

2. **O grão do dado era destruído na primeira transformação.**
   `groupby(['pais']).agg({'titulo': ' | '.join, 'sinopse': ' '.join})` colapsava
   cinco filmes numa linha de texto concatenado. Sem filme, ano ou gênero, nenhuma
   pergunta analítica sobrevive.

3. **O histórico era apagado a cada execução.** `to_sql(..., if_exists='replace')`
   sobrescrevia a tabela inteira, tornando série temporal impossível por construção —
   e séries temporais são metade das perguntas interessantes do projeto.

## Decisão

Reconstruir sobre fundação nova, preservando o v0 numa tag anotada.

**Preservado:** a tese do projeto, a lista de países-semente, o conceito do globo
interativo e a análise cromática de pôsteres por K-Means (vinda do projeto paralelo
`cinelens`, absorvido aqui como feature).

**Descartado:** todo o código de pipeline e interface.

## Nota: remoção do bypass de segurança do LLM

O `motor_ia.py` do v0 desabilitava os quatro filtros de segurança do Gemini
(`HarmBlockThreshold.BLOCK_NONE`) e envolvia as sinopses numa tag `<FICCAO>` para
contornar bloqueios do modelo. Isso foi removido integralmente, e a decisão é
registrada aqui em vez de apagada silenciosamente.

A causa raiz era arquitetural: o LLM estava sendo usado como **fonte** do dado
analítico. Texto gerado por modelo não é evidência, e sinopses de filmes de crime e
guerra naturalmente acionavam filtros. A solução correta não era desligar os filtros —
era parar de pedir ao modelo que produzisse a análise.

A partir da Fase 6, o LLM volta como **camada de leitura**: RAG sobre a metodologia
documentada e sobre valores já calculados, com citação obrigatória da fonte e
guardrails ativos.

## Consequências

**Positivas.** A fundação suporta as perguntas que o projeto quer responder. O
contraste v0 → v1 é material honesto de portfólio: diagnosticar e corrigir o próprio
erro demonstra mais do que nunca ter errado.

**Negativas.** Semanas de trabalho para voltar à paridade funcional com algo que já
rodava. Custo aceito: o v0 rodava, mas respondia à pergunta errada.
