from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
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

    retriever: Literal["tfidf", "embeddings"] = "tfidf"
    chroma_dir: Path = BACKEND_DIR / "chroma_db"

    chunk_strategy: Literal["artigo", "caracteres"] = "artigo"
    chunk_tamanho: int = 1000
    chunk_sobreposicao: int = 200

    limiar_classificador: float = 0.45
    limiar_similaridade: float = 0.08
    top_k: int = 3
    turnos_contexto: int = 3

    admin_contato: str = "Administração: (11) 0000-0000 · Portaria: ramal 9"

    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.8-27b"
    llm_habilitado: bool = True
    llm_timeout_s: float = 15.0

    modelo_id: str = "assistente-acacias"

    # observabilidade
    log_level: str = "INFO"
    log_format: Literal["texto", "json"] = "texto"  # formato do stdout; arquivos são sempre JSON
    log_dir: Path | None = BACKEND_DIR / "logs"  # vazio desliga os arquivos
    # grava o texto das mensagens nos logs (desligue se for usar dados reais)
    log_mensagens: bool = True

    @field_validator("log_dir", mode="before")
    @classmethod
    def _log_dir_vazio(cls, v):
        return None if v in ("", None) else v

    @property
    def log_path(self) -> Path | None:
        if self.log_dir is None:
            return None
        p = Path(self.log_dir)
        return p if p.is_absolute() else (BACKEND_DIR / p).resolve()

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
