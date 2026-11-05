"""Log de decisões (RF07) em Postgres (Docker) ou SQLite (execução local)."""

import logging
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .pipeline.engine import Decisao

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class RegistroDecisao(Base):
    __tablename__ = "decisoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    canal: Mapped[str] = mapped_column(String(32))
    sessao: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mensagem: Mapped[str] = mapped_column(Text)
    resposta: Mapped[str] = mapped_column(Text)
    desfecho: Mapped[str] = mapped_column(String(32), index=True)
    intencao: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confianca: Mapped[float | None] = mapped_column(Float, nullable=True)
    usou_contexto: Mapped[bool] = mapped_column(Boolean, default=False)
    regra: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trechos: Mapped[list] = mapped_column(JSON, default=list)
    llm_usado: Mapped[bool] = mapped_column(Boolean, default=False)
    tempo_ms: Mapped[float] = mapped_column(Float)


class LogDecisoes:
    def __init__(self, url: str):
        self.engine = create_engine(url, pool_pre_ping=True)

    def criar_tabelas(self) -> None:
        Base.metadata.create_all(self.engine)

    def registrar(self, d: Decisao, canal: str, sessao: str | None = None) -> None:
        try:
            with Session(self.engine) as s:
                s.add(
                    RegistroDecisao(
                        canal=canal,
                        sessao=sessao,
                        mensagem=d.mensagem,
                        resposta=d.resposta,
                        desfecho=d.desfecho.value,
                        intencao=d.intencao,
                        confianca=d.confianca,
                        usou_contexto=d.usou_contexto,
                        regra=d.regra,
                        trechos=d.trechos,
                        llm_usado=d.llm_usado,
                        tempo_ms=d.tempo_ms,
                    )
                )
                s.commit()
        except Exception:
            # o log nunca pode derrubar o atendimento
            log.exception("Falha ao registrar decisão")
