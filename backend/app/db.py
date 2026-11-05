"""Log de decisões (RF07) em Postgres (Docker) ou SQLite (execução local)."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .pipeline.engine import Decisao

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class RegistroDecisao(Base):
    __tablename__ = "decisoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    canal: Mapped[str] = mapped_column(String(32))
    usuario: Mapped[str | None] = mapped_column(String(128), nullable=True)
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
    llm_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    llm_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_modelo: Mapped[str | None] = mapped_column(String(128), nullable=True)
    etapas_ms: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tempo_ms: Mapped[float] = mapped_column(Float)

    def to_dict(self) -> dict:
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        d["criado_em"] = self.criado_em.isoformat() if self.criado_em else None
        return d


class LogDecisoes:
    def __init__(self, url: str):
        self.engine = create_engine(url, pool_pre_ping=True)

    def criar_tabelas(self) -> None:
        Base.metadata.create_all(self.engine)
        self._adicionar_colunas_novas()

    def _adicionar_colunas_novas(self) -> None:
        """Migração mínima: adiciona colunas que surgiram depois da criação da tabela."""
        existentes = {c["name"] for c in inspect(self.engine).get_columns(RegistroDecisao.__tablename__)}
        faltando = [c for c in RegistroDecisao.__table__.columns if c.name not in existentes]
        if not faltando:
            return
        with self.engine.begin() as conn:
            for col in faltando:
                tipo = col.type.compile(dialect=self.engine.dialect)
                conn.execute(text(f'ALTER TABLE {RegistroDecisao.__tablename__} ADD COLUMN "{col.name}" {tipo}'))
                log.info("Coluna adicionada em decisoes: %s %s", col.name, tipo)

    def registrar(
        self,
        d: Decisao,
        canal: str,
        sessao: str | None = None,
        usuario: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Grava no banco e devolve o registro (com id) para o log em arquivo."""
        reg = RegistroDecisao(
            request_id=request_id,
            canal=canal,
            usuario=usuario,
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
            llm_status=d.llm_status,
            llm_ms=d.llm_ms,
            llm_modelo=d.llm_modelo,
            etapas_ms=d.etapas_ms,
            tempo_ms=d.tempo_ms,
            criado_em=datetime.now(timezone.utc),
        )
        try:
            with Session(self.engine, expire_on_commit=False) as s:
                s.add(reg)
                s.commit()
        except Exception:
            # o banco nunca pode derrubar o atendimento; o arquivo jsonl continua registrando
            log.exception("Falha ao gravar decisão no banco")
        return reg.to_dict()

    def listar(
        self,
        horas: float | None = None,
        desfecho: str | None = None,
        intencao: str | None = None,
        canal: str | None = None,
        limite: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        q = select(RegistroDecisao).order_by(RegistroDecisao.id.desc())
        if horas:
            q = q.where(RegistroDecisao.criado_em >= datetime.now(timezone.utc) - timedelta(hours=horas))
        if desfecho:
            q = q.where(RegistroDecisao.desfecho == desfecho)
        if intencao:
            q = q.where(RegistroDecisao.intencao == intencao)
        if canal:
            q = q.where(RegistroDecisao.canal == canal)
        if limite:
            q = q.limit(limite).offset(offset)
        with Session(self.engine) as s:
            return [r.to_dict() for r in s.scalars(q)]

    def ping(self) -> bool:
        try:
            with self.engine.connect() as c:
                c.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
