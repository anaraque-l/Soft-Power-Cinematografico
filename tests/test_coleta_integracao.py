"""Teste de integração da coleta.  ⚠️  `[VOCÊ]` — o último a ficar verde.

Este é o teste de aceitação da Fase 1: cliente + modelos + loader trabalhando
juntos, do JSON do TMDB ao parquet em disco, sem rede.

Quando ele passar, a Fase 1 acabou. Enquanto não passar, alguma das peças
`[VOCÊ]` ainda não está de pé.

    pytest tests/test_coleta_integracao.py
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from ingestion.clients.tmdb import TMDBClient
from ingestion.config import TargetCountry
from ingestion.loaders.snapshot import read_snapshots, write_snapshot
from ingestion.pipelines.tmdb_coleta import (
    DATASET_FILMES,
    DATASET_LANCAMENTOS,
    DATASET_PROVEDORES,
    coletar,
)

pytestmark = pytest.mark.pendente

BASE = "https://tmdb.test/3"

BRASIL = TargetCountry(iso="BR", nome="Brasil", regiao="América do Sul")
COREIA = TargetCountry(iso="KR", nome="Coreia do Sul", regiao="Ásia Oriental")


def filme(id_: int, titulo: str) -> dict:
    return {
        "id": id_,
        "title": titulo,
        "original_title": titulo,
        "original_language": "pt",
        "release_date": "2023-05-01",
        "vote_count": 1200,
        "vote_average": 7.4,
        "popularity": 22.5,
        "genre_ids": [18],
        "overview": "",
        "poster_path": "/p.jpg",
        "adult": False,
    }


def lancamentos(id_: int, paises: list[str]) -> dict:
    return {
        "id": id_,
        "results": [
            {
                "iso_3166_1": iso,
                "release_dates": [
                    {
                        "certification": "",
                        "iso_639_1": "",
                        "note": "",
                        "release_date": "2023-05-01T00:00:00.000Z",
                        "type": 3,
                    }
                ],
            }
            for iso in paises
        ],
    }


def provedores(id_: int, paises: list[str]) -> dict:
    return {
        "id": id_,
        "results": {
            iso: {
                "link": f"https://www.themoviedb.org/movie/{id_}/watch?locale={iso}",
                "flatrate": [
                    {
                        "display_priority": 0,
                        "logo_path": "/n.jpg",
                        "provider_id": 8,
                        "provider_name": "Netflix",
                    }
                ],
            }
            for iso in paises
        },
    }


@pytest.fixture
def tmdb_falso():
    """Dois países, um filme cada, com detalhes.

    `assert_all_called=False` porque `--sem-detalhes` deixa rotas de propósito
    sem uso; quem verifica o que foi chamado é cada teste, explicitamente.
    """
    with respx.mock(base_url=BASE, assert_all_called=False) as mock:
        mock.get("/discover/movie", params={"with_origin_country": "BR"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "page": 1,
                    "total_pages": 1,
                    "results": [filme(1, "Bacurau")],
                },
            )
        )
        mock.get("/discover/movie", params={"with_origin_country": "KR"}).mock(
            return_value=httpx.Response(
                200,
                json={
                    "page": 1,
                    "total_pages": 1,
                    "results": [filme(2, "Parasita")],
                },
            )
        )
        mock.get("/movie/1/release_dates").mock(
            return_value=httpx.Response(200, json=lancamentos(1, ["BR", "FR"]))
        )
        mock.get("/movie/2/release_dates").mock(
            return_value=httpx.Response(200, json=lancamentos(2, ["KR", "US", "FR", "BR"]))
        )
        mock.get("/movie/1/watch/providers").mock(
            return_value=httpx.Response(200, json=provedores(1, ["BR"]))
        )
        mock.get("/movie/2/watch/providers").mock(
            return_value=httpx.Response(200, json=provedores(2, ["KR", "US", "BR"]))
        )
        yield mock


async def _coletar(**kwargs):
    async with TMDBClient("chave", base_url=BASE, max_rps=0) as tmdb:
        return await coletar(tmdb, [BRASIL, COREIA], [2023], **kwargs)


class TestColeta:
    async def test_coleta_os_tres_datasets(self, tmdb_falso):
        resultado = await _coletar()

        assert len(resultado.filmes) == 2
        assert len(resultado.lancamentos) == 6, "2 mercados do filme 1 + 4 do filme 2"
        assert len(resultado.provedores) == 4, "1 do filme 1 + 3 do filme 2"

    async def test_registra_o_pais_alvo_da_consulta(self, tmdb_falso):
        """Coprodução faz o mesmo filme aparecer por mais de um país.

        A camada bruta precisa saber por qual consulta cada linha entrou;
        resolver a atribuição é decisão de modelagem, no dbt.
        """
        resultado = await _coletar()
        assert {linha["pais_alvo"] for linha in resultado.filmes} == {"BR", "KR"}
        assert all(linha["ano_alvo"] == 2023 for linha in resultado.filmes)

    async def test_sem_detalhes_pula_as_chamadas_extras(self, tmdb_falso):
        resultado = await _coletar(com_detalhes=False)

        assert len(resultado.filmes) == 2
        assert resultado.lancamentos == []
        assert resultado.provedores == []

    async def test_detalhe_indisponivel_nao_derruba_a_coleta(self, tmdb_falso):
        """Catálogo incompleto é rotina; falhar a rodada inteira por isso, não."""
        tmdb_falso.get("/movie/2/watch/providers").mock(return_value=httpx.Response(404))

        resultado = await _coletar()

        assert len(resultado.filmes) == 2
        assert len(resultado.lancamentos) == 6


class TestPontaAPonta:
    async def test_do_json_ao_parquet(self, tmdb_falso, tmp_path: Path):
        """O caminho completo da Fase 1, com o grão intacto na outra ponta."""
        resultado = await _coletar()

        for dataset, linhas in resultado.datasets.items():
            write_snapshot(linhas, dataset=dataset, base_dir=tmp_path)

        assert len(read_snapshots(DATASET_FILMES, base_dir=tmp_path)) == 2
        assert len(read_snapshots(DATASET_LANCAMENTOS, base_dir=tmp_path)) == 6
        assert len(read_snapshots(DATASET_PROVEDORES, base_dir=tmp_path)) == 4

    async def test_o_parquet_sai_carimbado(self, tmdb_falso, tmp_path: Path):
        resultado = await _coletar()
        write_snapshot(resultado.filmes, dataset=DATASET_FILMES, base_dir=tmp_path)

        df = read_snapshots(DATASET_FILMES, base_dir=tmp_path)
        assert "ingested_at" in df.columns
        assert "ingested_date" in df.columns
