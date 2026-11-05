from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Lê .env tanto rodando de backend/ quanto da raiz do repositório
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    database_url: str = ""
    backend_api_key: str = ""
    dados_dir: Path = BACKEND_DIR.parent / "dados"

    chunk_strategy: Literal["artigo", "caracteres"] = "artigo"
    chunk_tamanho: int = 1000
    chunk_sobreposicao: int = 200

    limiar_classificador: float = 0.35
    limiar_similaridade: float = 0.10
    top_k: int = 3
    turnos_contexto: int = 3

    admin_contato: str = "Administração: (11) 0000-0000 · Portaria: ramal 9"

    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.8-27b"
    llm_habilitado: bool = True
    llm_timeout_s: float = 15.0

    modelo_id: str = "assistente-acacias"

    @property
    def dados_path(self) -> Path:
        p = Path(self.dados_dir)
        return p if p.is_absolute() else (BACKEND_DIR / p).resolve()

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{BACKEND_DIR / 'decisoes.db'}"

    @property
    def usa_llm(self) -> bool:
        return self.llm_habilitado and bool(self.groq_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
