"""Configuração tipada do pipeline.

Duas responsabilidades:
1. `Settings` — lê credenciais e opções do ambiente (`.env`), validando na partida.
2. `load_countries()` — carrega a lista de países-alvo de `countries.yml`.

O ponto de ter isso tipado: se faltar a `TMDB_API_KEY`, o pipeline falha na
primeira linha com uma mensagem clara — e não trinta segundos depois, com um
401 críptico no meio de um loop.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz do repositório, resolvida a partir deste arquivo (não do diretório atual):
# assim os caminhos funcionam independente de onde você rodou o comando.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
COUNTRIES_FILE = Path(__file__).resolve().parent / "countries.yml"


class Settings(BaseSettings):
    """Configuração lida do ambiente e do arquivo `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tmdb_api_key: str = ""
    database_url: str = ""
    supabase_url: str = ""
    supabase_key: str = ""

    data_dir: Path = Path("data")
    log_level: str = "INFO"

    @property
    def raw_dir(self) -> Path:
        """Camada bronze: snapshots brutos, append-only, particionados por data."""
        return PROJECT_ROOT / self.data_dir / "raw"

    def require_tmdb_key(self) -> str:
        """Devolve a chave do TMDB ou falha com instrução acionável."""
        if not self.tmdb_api_key:
            raise RuntimeError(
                "TMDB_API_KEY não configurada. "
                "Copie `.env.example` para `.env` e preencha a chave "
                "(gratuita em https://www.themoviedb.org/settings/api)."
            )
        return self.tmdb_api_key


class TargetCountry(BaseModel):
    """Um país-alvo do estudo.

    O código ISO é a chave de junção com todas as outras fontes
    (TMDB, Wikidata, World Bank, UNESCO). Por isso é validado aqui.
    """

    iso: str = Field(description="Código ISO 3166-1 alfa-2, maiúsculo (ex.: 'BR')")
    nome: str = Field(description="Nome do país em português")
    regiao: str = Field(description="Macrorregião, para agrupamento nas análises")

    @field_validator("iso")
    @classmethod
    def iso_deve_ter_dois_caracteres(cls, v: str) -> str:
        if len(v) != 2 or not v.isalpha():
            raise ValueError(f"ISO 3166-1 alfa-2 inválido: {v!r} (esperado 2 letras)")
        return v.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Configuração única do processo (lida uma vez, reutilizada depois)."""
    return Settings()


def load_countries(path: Path | None = None) -> list[TargetCountry]:
    """Carrega e valida a lista de países-alvo.

    Levanta `ValueError` se houver ISO duplicado — um país repetido duplicaria
    silenciosamente todos os filmes dele na contagem.
    """
    arquivo = path or COUNTRIES_FILE
    dados = yaml.safe_load(arquivo.read_text(encoding="utf-8"))

    paises = [TargetCountry(**item) for item in dados]

    isos = [p.iso for p in paises]
    duplicados = {iso for iso in isos if isos.count(iso) > 1}
    if duplicados:
        raise ValueError(f"Países duplicados em {arquivo.name}: {sorted(duplicados)}")

    return paises
