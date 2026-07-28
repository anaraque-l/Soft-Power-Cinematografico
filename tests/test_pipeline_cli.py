"""Testes da interface de linha de comando da coleta.

Argumento mal interpretado é a forma mais barata de corromper um dataset:
`--anos 2019-2023` virar `[2019]` só apareceria semanas depois, quando a série
estivesse com buracos.
"""

from __future__ import annotations

import argparse

import pytest

from ingestion.pipelines.tmdb_coleta import (
    _parse_anos,
    _selecionar_paises,
    construir_parser,
)


class TestParseAnos:
    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("2023", [2023]),
            ("2019-2023", [2019, 2020, 2021, 2022, 2023]),
            ("2019,2021,2023", [2019, 2021, 2023]),
            ("2019-2020,2023", [2019, 2020, 2023]),
            (" 2019 , 2020 ", [2019, 2020]),
            ("2020,2020", [2020]),
        ],
    )
    def test_formatos_aceitos(self, texto, esperado):
        assert _parse_anos(texto) == esperado

    def test_intervalo_invertido_falha(self):
        with pytest.raises(argparse.ArgumentTypeError, match="invertido"):
            _parse_anos("2023-2019")

    def test_texto_nao_numerico_falha(self):
        with pytest.raises(ValueError):
            _parse_anos("ano passado")


class TestSelecionarPaises:
    def test_sem_filtro_devolve_todos(self):
        assert len(_selecionar_paises(None)) >= 30

    def test_filtra_e_preserva_a_ordem_pedida(self):
        paises = _selecionar_paises("KR,br,FR")
        assert [p.iso for p in paises] == ["KR", "BR", "FR"]

    def test_pais_fora_do_escopo_falha_com_instrucao(self):
        """O escopo do estudo é versionado em countries.yml, não improvisado na CLI."""
        with pytest.raises(SystemExit, match=r"countries\.yml"):
            _selecionar_paises("BR,ZZ")


class TestParser:
    def test_anos_e_obrigatorio(self):
        with pytest.raises(SystemExit):
            construir_parser().parse_args([])

    def test_padroes(self):
        args = construir_parser().parse_args(["--anos", "2023"])
        assert args.anos == [2023]
        assert args.paises is None
        assert args.max_paginas == 3
        assert args.sem_detalhes is False
        assert args.dry_run is False

    def test_corte_vertical_do_plano(self):
        """Cinco países, um ano — a recomendação da Seção 6 do PLANO."""
        args = construir_parser().parse_args(
            ["--anos", "2023", "--paises", "BR,KR,FR,US,NG", "--max-paginas", "1"]
        )
        assert args.anos == [2023]
        assert args.max_paginas == 1
        assert [p.iso for p in _selecionar_paises(args.paises)] == [
            "BR",
            "KR",
            "FR",
            "US",
            "NG",
        ]
