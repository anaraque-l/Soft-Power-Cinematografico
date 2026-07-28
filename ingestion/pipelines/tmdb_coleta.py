"""Coleta do TMDB: país × ano → snapshots brutos datados.

Executável:

    python -m ingestion.pipelines.tmdb_coleta --anos 2019-2023
    python -m ingestion.pipelines.tmdb_coleta --anos 2023 --paises BR,KR,FR --dry-run

Três datasets saem daqui, cada um no seu grão — e o grão é o produto:

| dataset                  | uma linha é...                                  |
|--------------------------|-------------------------------------------------|
| `tmdb_movies`            | um filme, num país-alvo, num ano                |
| `tmdb_release_dates`     | um evento de lançamento (filme × país × tipo)   |
| `tmdb_watch_providers`   | uma disponibilidade (filme × país × provedor)   |

O corte vertical recomendado pelo plano (Seção 6) é rodar primeiro com
`--paises BR,KR,FR,US,NG --anos 2023`: cinco países, um ano. Serve para
descobrir cedo os problemas de integração, que são sempre os caros.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Coroutine, Sequence
from typing import Any

from ingestion.clients import TMDBClient, TMDBPermanentError
from ingestion.config import TargetCountry, get_settings, load_countries
from ingestion.loaders import write_snapshot
from ingestion.logging_config import configurar_logging, get_logger
from ingestion.models import Movie, MovieReleases, MovieWatchProviders

# Nome fixo, e não `__name__`: rodado com `python -m`, `__name__` vira
# `__main__` e o log passaria a mentir sobre a origem da mensagem.
log = get_logger("pipelines.tmdb_coleta")

DATASET_FILMES = "tmdb_movies"
DATASET_LANCAMENTOS = "tmdb_release_dates"
DATASET_PROVEDORES = "tmdb_watch_providers"

# Quantas chamadas de detalhe (release_dates / watch_providers) ficam em voo ao
# mesmo tempo. O throttle do cliente já impõe o teto de requisições por segundo;
# isto aqui limita o consumo de memória e o tamanho do rastro no log.
CONCORRENCIA_PADRAO = 8


class ResultadoColeta:
    """Os três datasets de uma execução, ainda em memória."""

    def __init__(self) -> None:
        self.filmes: list[dict[str, Any]] = []
        self.lancamentos: list[dict[str, Any]] = []
        self.provedores: list[dict[str, Any]] = []

    @property
    def datasets(self) -> dict[str, list[dict[str, Any]]]:
        return {
            DATASET_FILMES: self.filmes,
            DATASET_LANCAMENTOS: self.lancamentos,
            DATASET_PROVEDORES: self.provedores,
        }

    def resumo(self) -> str:
        return " · ".join(f"{nome}: {len(linhas)}" for nome, linhas in self.datasets.items())


async def _opcional(
    corrotina: Coroutine[Any, Any, dict[str, Any]],
    filme_id: int,
    o_que: str,
) -> dict[str, Any] | None:
    """Executa uma chamada de detalhe tolerando ausência do recurso.

    Catálogo incompleto é rotina no TMDB e não é motivo para perder a rodada.
    Falha de rede, essa sim, propaga: já passou pelo retry do cliente, e
    engolir aqui esconderia um problema real atrás de um dataset menor.
    """
    try:
        return await corrotina
    except TMDBPermanentError as erro:
        log.warning("%s indisponível para o filme %s: %s", o_que, filme_id, erro)
        return None


async def _coletar_detalhes(
    tmdb: TMDBClient,
    filme_id: int,
    resultado: ResultadoColeta,
    semaforo: asyncio.Semaphore,
) -> None:
    """Busca lançamentos e provedores de um filme e acumula as linhas.

    As duas chamadas são independentes de propósito: um filme pode ter datas
    de lançamento registradas e nenhum provedor de streaming. Tratá-las em
    bloco faria a ausência de uma apagar o dado da outra.
    """
    async with semaforo:
        lancamentos, provedores = await asyncio.gather(
            _opcional(tmdb.datas_de_lancamento(filme_id), filme_id, "release_dates"),
            _opcional(tmdb.provedores(filme_id), filme_id, "watch/providers"),
        )

    if lancamentos is not None:
        resultado.lancamentos.extend(MovieReleases.from_payload(lancamentos).to_rows())
    if provedores is not None:
        resultado.provedores.extend(MovieWatchProviders.from_payload(provedores).to_rows())


async def coletar(
    tmdb: TMDBClient,
    paises: Sequence[TargetCountry],
    anos: Sequence[int],
    *,
    max_paginas: int = 3,
    com_detalhes: bool = True,
    concorrencia: int = CONCORRENCIA_PADRAO,
) -> ResultadoColeta:
    """Percorre país × ano e devolve os três datasets em memória.

    Guarda-se o `pais_alvo` da consulta em cada linha de filme, e não só o
    país de origem que o TMDB reporta: coprodução faz um mesmo filme aparecer
    para mais de um país, e a camada bruta precisa registrar por qual consulta
    cada linha entrou. Resolver a atribuição é decisão de modelagem — dbt.
    """
    resultado = ResultadoColeta()
    semaforo = asyncio.Semaphore(concorrencia)

    for pais in paises:
        for ano in anos:
            ids_do_ano: list[int] = []

            async for bruto in tmdb.descobrir_filmes(pais.iso, ano, max_paginas=max_paginas):
                filme = Movie.model_validate(bruto)
                linha = filme.model_dump()
                linha["pais_alvo"] = pais.iso
                linha["ano_alvo"] = ano
                resultado.filmes.append(linha)
                ids_do_ano.append(filme.id)

            log.info("%s/%s: %d filmes", pais.iso, ano, len(ids_do_ano))

            if com_detalhes and ids_do_ano:
                await asyncio.gather(
                    *(
                        _coletar_detalhes(tmdb, filme_id, resultado, semaforo)
                        for filme_id in ids_do_ano
                    )
                )

    return resultado


def _parse_anos(texto: str) -> list[int]:
    """Aceita `2023`, `2019-2023` e `2019,2021,2023`."""
    anos: list[int] = []
    for parte in texto.split(","):
        parte = parte.strip()
        if "-" in parte:
            inicio, fim = (int(x) for x in parte.split("-", 1))
            if fim < inicio:
                raise argparse.ArgumentTypeError(f"intervalo invertido: {parte!r}")
            anos.extend(range(inicio, fim + 1))
        else:
            anos.append(int(parte))
    return sorted(set(anos))


def _selecionar_paises(filtro: str | None) -> list[TargetCountry]:
    todos = load_countries()
    if not filtro:
        return todos

    pedidos = [iso.strip().upper() for iso in filtro.split(",") if iso.strip()]
    por_iso = {p.iso: p for p in todos}
    desconhecidos = [iso for iso in pedidos if iso not in por_iso]
    if desconhecidos:
        raise SystemExit(
            f"países fora de ingestion/countries.yml: {desconhecidos}. "
            "Adicione-os lá antes de coletar — o escopo do estudo é versionado."
        )
    return [por_iso[iso] for iso in pedidos]


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ingestion.pipelines.tmdb_coleta",
        description="Coleta filmes do TMDB por país e ano, gravando snapshots datados.",
    )
    parser.add_argument(
        "--anos",
        type=_parse_anos,
        required=True,
        help="ano, intervalo ou lista: 2023 | 2019-2023 | 2019,2021,2023",
    )
    parser.add_argument(
        "--paises",
        help="ISOs separados por vírgula (padrão: todos os de countries.yml)",
    )
    parser.add_argument(
        "--max-paginas",
        type=int,
        default=3,
        help="páginas de 20 filmes por país/ano (padrão: 3, ou seja, top 60)",
    )
    parser.add_argument(
        "--sem-detalhes",
        action="store_true",
        help="pula release_dates e watch/providers (coleta muito mais rápida)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="coleta e resume, mas não grava nada em disco",
    )
    return parser


async def _executar(args: argparse.Namespace) -> int:
    settings = get_settings()
    paises = _selecionar_paises(args.paises)

    log.info(
        "coleta TMDB: %d país(es) × %d ano(s), até %d páginas cada%s",
        len(paises),
        len(args.anos),
        args.max_paginas,
        " (sem detalhes)" if args.sem_detalhes else "",
    )

    async with TMDBClient(settings.require_tmdb_key()) as tmdb:
        resultado = await coletar(
            tmdb,
            paises,
            args.anos,
            max_paginas=args.max_paginas,
            com_detalhes=not args.sem_detalhes,
        )

    log.info("coletado — %s", resultado.resumo())

    if args.dry_run:
        log.info("--dry-run: nada gravado")
        return 0

    for dataset, linhas in resultado.datasets.items():
        if not linhas:
            log.warning("dataset %s veio vazio; nada a gravar", dataset)
            continue
        caminho = write_snapshot(linhas, dataset=dataset)
        log.info("gravado %s (%d linhas) em %s", dataset, len(linhas), caminho)

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    configurar_logging()
    args = construir_parser().parse_args(argv)
    try:
        return asyncio.run(_executar(args))
    except KeyboardInterrupt:  # pragma: no cover - interação humana
        log.warning("interrompido pelo usuário")
        return 130


if __name__ == "__main__":  # pragma: no cover - ponto de entrada
    sys.exit(main())
