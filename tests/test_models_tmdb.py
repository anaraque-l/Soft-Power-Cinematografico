"""Testes dos modelos do TMDB.  ⚠️  `[VOCÊ]` — escritos, falhando, esperando.

Como usar este arquivo:

1. `pytest tests/test_models_tmdb.py` — tudo vermelho, e é para estar.
2. Implemente `ingestion/models/tmdb.py` até ficar verde.
3. Não altere os testes. Se um deles parecer errado, essa conversa vale mais
   que o teste — mas comece assumindo que ele está certo.

Estes testes estão marcados como `pendente`: o CI os ignora, para que o badge
do README não fique vermelho por trabalho que ainda não começou. Rodando
localmente, eles aparecem — é a sua lista de tarefas.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ingestion.models.tmdb import (
    Movie,
    MovieReleases,
    MovieWatchProviders,
    ReleaseDate,
    WatchProvider,
)

pytestmark = pytest.mark.pendente


# --- payloads de referência (recortes reais da API) ----------------------

FILME_BRUTO = {
    "adult": False,
    "backdrop_path": "/spuVgTQzOSRhc7iA6xrPYbLCJUw.jpg",
    "genre_ids": [16, 35, 10751],
    "id": 508965,
    "original_language": "en",
    "original_title": "Klaus",
    "overview": "Um carteiro preguiçoso é enviado para o norte gelado.",
    "popularity": 45.712,
    "poster_path": "/q2fdvS3E5JuHVoP3l3zHVFbCa8V.jpg",
    "release_date": "2019-11-08",
    "title": "Klaus",
    "video": False,
    "vote_average": 8.2,
    "vote_count": 3612,
}

LANCAMENTOS_BRUTOS = {
    "id": 508965,
    "results": [
        {
            "iso_3166_1": "BR",
            "release_dates": [
                {
                    "certification": "L",
                    "iso_639_1": "",
                    "note": "",
                    "release_date": "2019-11-15T00:00:00.000Z",
                    "type": 4,
                }
            ],
        },
        {
            "iso_3166_1": "US",
            "release_dates": [
                {
                    "certification": "PG",
                    "iso_639_1": "",
                    "note": "Limitado",
                    "release_date": "2019-11-08T00:00:00.000Z",
                    "type": 2,
                },
                {
                    "certification": "PG",
                    "iso_639_1": "",
                    "note": "",
                    "release_date": "2019-11-15T00:00:00.000Z",
                    "type": 4,
                },
            ],
        },
        # País listado sem nenhum evento: acontece, e não pode virar linha.
        {"iso_3166_1": "JP", "release_dates": []},
    ],
}

PROVEDORES_BRUTOS = {
    "id": 508965,
    "results": {
        "BR": {
            "link": "https://www.themoviedb.org/movie/508965/watch?locale=BR",
            "flatrate": [
                {
                    "display_priority": 0,
                    "logo_path": "/x.jpg",
                    "provider_id": 8,
                    "provider_name": "Netflix",
                }
            ],
        },
        "US": {
            "link": "https://www.themoviedb.org/movie/508965/watch?locale=US",
            "flatrate": [
                {
                    "display_priority": 0,
                    "logo_path": "/x.jpg",
                    "provider_id": 8,
                    "provider_name": "Netflix",
                }
            ],
            "rent": [
                {
                    "display_priority": 3,
                    "logo_path": "/y.jpg",
                    "provider_id": 2,
                    "provider_name": "Apple TV",
                }
            ],
        },
        # Só aluguel: o filme está à venda, mas não está em nenhum catálogo.
        "PT": {
            "link": "https://www.themoviedb.org/movie/508965/watch?locale=PT",
            "rent": [
                {
                    "display_priority": 3,
                    "logo_path": "/y.jpg",
                    "provider_id": 2,
                    "provider_name": "Apple TV",
                }
            ],
        },
    },
}


class TestMovie:
    def test_valida_o_payload_do_discover(self):
        filme = Movie.model_validate(FILME_BRUTO)

        assert filme.id == 508965
        assert filme.title == "Klaus"
        assert filme.original_language == "en"
        assert filme.release_date == date(2019, 11, 8)
        assert filme.vote_count == 3612
        assert filme.vote_average == pytest.approx(8.2)
        assert filme.genre_ids == [16, 35, 10751]
        assert filme.adult is False

    def test_data_vazia_vira_none(self):
        """O TMDB manda `""` quando não sabe a data — e `""` não é uma data.

        Sem tratar isso, a validação quebra em produção no primeiro filme sem
        data de lançamento confirmada. Com `None`, o dbt decide o que fazer.
        """
        filme = Movie.model_validate({**FILME_BRUTO, "release_date": ""})
        assert filme.release_date is None

    def test_ignora_campos_que_nao_usamos(self):
        """`backdrop_path` e `video` vêm no payload e não nos interessam."""
        filme = Movie.model_validate(FILME_BRUTO)
        assert not hasattr(filme, "backdrop_path")

    def test_campo_obrigatorio_ausente_falha(self):
        """É este o ponto do pydantic: falhar alto, na fronteira, com o nome do campo."""
        sem_id = {k: v for k, v in FILME_BRUTO.items() if k != "id"}
        with pytest.raises(ValidationError, match="id"):
            Movie.model_validate(sem_id)

    def test_tipo_incompativel_falha(self):
        with pytest.raises(ValidationError):
            Movie.model_validate({**FILME_BRUTO, "vote_count": "muitos"})

    def test_ano_deriva_da_data(self):
        assert Movie.model_validate(FILME_BRUTO).ano == 2019

    def test_ano_e_none_sem_data(self):
        assert Movie.model_validate({**FILME_BRUTO, "release_date": ""}).ano is None

    def test_campos_opcionais_tem_padrao(self):
        minimo = {
            "id": 1,
            "title": "X",
            "original_title": "X",
            "original_language": "pt",
            "vote_count": 0,
            "vote_average": 0.0,
            "popularity": 0.0,
        }
        filme = Movie.model_validate(minimo)
        assert filme.genre_ids == []
        assert filme.overview == ""
        assert filme.poster_path is None
        assert filme.release_date is None


class TestReleaseDate:
    def test_normaliza_iso_para_maiusculo(self):
        evento = ReleaseDate.model_validate(
            {"iso_3166_1": "br", "release_date": "2019-11-15T00:00:00.000Z", "type": 4}
        )
        assert evento.iso_3166_1 == "BR"

    def test_interpreta_o_timestamp_iso(self):
        evento = ReleaseDate.model_validate(
            {"iso_3166_1": "BR", "release_date": "2019-11-15T00:00:00.000Z", "type": 4}
        )
        assert evento.release_date.year == 2019
        assert evento.release_date.month == 11
        assert evento.release_date.day == 15

    def test_certification_tem_padrao_vazio(self):
        evento = ReleaseDate.model_validate(
            {"iso_3166_1": "BR", "release_date": "2019-11-15T00:00:00.000Z", "type": 4}
        )
        assert evento.certification == ""


class TestMovieReleases:
    def test_achata_o_aninhamento_por_pais(self):
        releases = MovieReleases.from_payload(LANCAMENTOS_BRUTOS)

        assert releases.movie_id == 508965
        assert len(releases.lancamentos) == 3, "1 evento no BR + 2 nos EUA"

    def test_pais_sem_eventos_nao_vira_linha(self):
        releases = MovieReleases.from_payload(LANCAMENTOS_BRUTOS)
        assert "JP" not in {ev.iso_3166_1 for ev in releases.lancamentos}

    def test_cada_evento_carrega_o_pais(self):
        releases = MovieReleases.from_payload(LANCAMENTOS_BRUTOS)
        por_pais = sorted(ev.iso_3166_1 for ev in releases.lancamentos)
        assert por_pais == ["BR", "US", "US"]

    def test_mercados_sao_paises_distintos(self):
        releases = MovieReleases.from_payload(LANCAMENTOS_BRUTOS)
        assert releases.mercados == {"BR", "US"}
        assert releases.n_mercados == 2

    def test_sem_resultados_nao_quebra(self):
        releases = MovieReleases.from_payload({"id": 1, "results": []})
        assert releases.lancamentos == []
        assert releases.n_mercados == 0

    def test_to_rows_preserva_o_grao(self):
        """O pecado original do v0 era agregar aqui. Uma linha por evento."""
        linhas = MovieReleases.from_payload(LANCAMENTOS_BRUTOS).to_rows()
        assert len(linhas) == 3

    def test_to_rows_tem_as_colunas_do_contrato(self):
        linha = MovieReleases.from_payload(LANCAMENTOS_BRUTOS).to_rows()[0]
        assert set(linha) == {
            "movie_id",
            "iso_3166_1",
            "release_date",
            "type",
            "certification",
        }
        assert linha["movie_id"] == 508965


class TestWatchProvider:
    def test_normaliza_iso_para_maiusculo(self):
        disp = WatchProvider.model_validate(
            {
                "iso_3166_1": "br",
                "provider_id": 8,
                "provider_name": "Netflix",
                "tipo": "flatrate",
            }
        )
        assert disp.iso_3166_1 == "BR"


class TestMovieWatchProviders:
    def test_achata_o_dicionario_por_pais(self):
        provedores = MovieWatchProviders.from_payload(PROVEDORES_BRUTOS)

        assert provedores.movie_id == 508965
        assert len(provedores.disponibilidades) == 4, "BR:1 + US:2 + PT:1"

    def test_ignora_a_chave_link(self):
        """`link` é a URL da página do TMDB, não um provedor."""
        provedores = MovieWatchProviders.from_payload(PROVEDORES_BRUTOS)
        assert "link" not in {d.tipo for d in provedores.disponibilidades}

    def test_registra_o_tipo_de_disponibilidade(self):
        provedores = MovieWatchProviders.from_payload(PROVEDORES_BRUTOS)
        tipos = sorted(d.tipo for d in provedores.disponibilidades)
        assert tipos == ["flatrate", "flatrate", "rent", "rent"]

    def test_mercados_streaming_exclui_aluguel_e_compra(self):
        """Estar em catálogo de assinatura e estar à venda são fatos diferentes.

        Portugal só tem aluguel neste payload — não conta como alcance de
        streaming, e a dimensão *Alcance* depende dessa distinção.
        """
        provedores = MovieWatchProviders.from_payload(PROVEDORES_BRUTOS)
        assert provedores.mercados_streaming == {"BR", "US"}

    def test_sem_resultados_nao_quebra(self):
        provedores = MovieWatchProviders.from_payload({"id": 1, "results": {}})
        assert provedores.disponibilidades == []
        assert provedores.mercados_streaming == set()

    def test_to_rows_preserva_o_grao(self):
        linhas = MovieWatchProviders.from_payload(PROVEDORES_BRUTOS).to_rows()
        assert len(linhas) == 4

    def test_to_rows_tem_as_colunas_do_contrato(self):
        linha = MovieWatchProviders.from_payload(PROVEDORES_BRUTOS).to_rows()[0]
        assert set(linha) == {
            "movie_id",
            "iso_3166_1",
            "provider_id",
            "provider_name",
            "tipo",
        }
        assert linha["movie_id"] == 508965
