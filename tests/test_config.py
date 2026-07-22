"""Testes da configuração e da lista de países-alvo.

Estes testes protegem o escopo do estudo: se alguém quebrar o `countries.yml`
(ISO inválido, país duplicado, continente inteiro sumindo), o CI acusa antes
de o pipeline rodar e gravar dado errado.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from ingestion.config import Settings, TargetCountry, load_countries


class TestTargetCountry:
    def test_normaliza_iso_para_maiusculo(self):
        pais = TargetCountry(iso="br", nome="Brasil", regiao="América do Sul")
        assert pais.iso == "BR"

    @pytest.mark.parametrize("iso_invalido", ["BRA", "B", "", "B1", "12"])
    def test_rejeita_iso_fora_do_padrao_alfa2(self, iso_invalido):
        with pytest.raises(ValidationError):
            TargetCountry(iso=iso_invalido, nome="X", regiao="Y")


class TestLoadCountries:
    def test_carrega_a_lista_do_projeto(self):
        paises = load_countries()
        assert len(paises) >= 30, "escopo do estudo encolheu inesperadamente"
        assert all(isinstance(p, TargetCountry) for p in paises)

    def test_nao_ha_iso_duplicado(self):
        isos = [p.iso for p in load_countries()]
        assert len(isos) == len(set(isos))

    def test_cobre_todos_os_continentes(self):
        """Viés de cobertura é o risco número um deste projeto.

        Se a lista perder África ou Oceania, o índice vira um ranking
        de Europa + EUA + Ásia Oriental sem que ninguém perceba.
        """
        regioes = {p.regiao for p in load_countries()}
        for esperada in ["África Subsaariana", "Oceania", "América do Sul", "Oriente Médio"]:
            assert any(esperada in r for r in regioes), f"nenhum país em {esperada}"

    def test_falha_em_pais_duplicado(self, tmp_path: Path):
        arquivo = tmp_path / "duplicado.yml"
        arquivo.write_text(
            "- {iso: BR, nome: Brasil, regiao: A}\n- {iso: BR, nome: Brasil, regiao: A}\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="duplicados"):
            load_countries(arquivo)


class TestSettings:
    def test_erro_acionavel_quando_falta_a_chave_do_tmdb(self):
        settings = Settings(_env_file=None, tmdb_api_key="")
        with pytest.raises(RuntimeError, match="TMDB_API_KEY"):
            settings.require_tmdb_key()

    def test_devolve_a_chave_quando_configurada(self):
        settings = Settings(_env_file=None, tmdb_api_key="chave-de-teste")
        assert settings.require_tmdb_key() == "chave-de-teste"
