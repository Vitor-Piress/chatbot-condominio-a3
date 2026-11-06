"""API FastAPI.

Atendimento
- POST /chat                   endpoint nativo, independente de interface (canais futuros)
- GET  /v1/models              \\
- POST /v1/chat/completions    / compatíveis com OpenAI, consumidos pelo Open WebUI

Operação e monitoramento (exigem a chave BACKEND_API_KEY)
- GET  /health                 estado do serviço, do banco e da base carregada
- GET  /admin/metricas         métricas agregadas (desfechos, latência, LLM, lacunas da base)
- GET  /admin/decisoes         decisões registradas, com filtros
- POST /admin/reingest         reexecuta a ingestão da base sem reiniciar (RF08)
- GET  /painel                 painel web de monitoramento
"""

import json
import logging
import time
import uuid
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .config import get_settings
from .db import LogDecisoes
from .monitoring import resumir
from .observability import configurar_logging, registrar_decisao, request_id_ctx
from .pipeline.engine import Decisao, MotorChatbot

settings = get_settings()
configurar_logging(settings.log_level, settings.log_format, settings.log_path)
log = logging.getLogger("chatbot.api")

motor = MotorChatbot(settings)
log_decisoes = LogDecisoes(settings.db_url)
info_base: dict = {}
iniciado_em = time.time()

STATIC_DIR = Path(__file__).parent / "static"
MAX_SESSOES = 5000


class Sessoes:
    """Contexto do endpoint nativo: últimas N perguntas por sessão, em memória (LRU)."""

    def __init__(self, turnos: int, maximo: int = MAX_SESSOES):
        self.turnos, self.maximo = turnos, maximo
        self._dados: OrderedDict[str, deque[str]] = OrderedDict()

    def historico(self, sessao: str) -> list[str]:
        return list(self._dados.get(sessao, ()))

    def adicionar(self, sessao: str, mensagem: str) -> None:
        fila = self._dados.pop(sessao, None) or deque(maxlen=self.turnos)
        fila.append(mensagem)
        self._dados[sessao] = fila
        while len(self._dados) > self.maximo:
            self._dados.popitem(last=False)


sessoes = Sessoes(settings.turnos_contexto)


@asynccontextmanager
async def lifespan(_: FastAPI):
    log_decisoes.criar_tabelas()
    info_base.update(motor.carregar())
    log.info(
        "Backend pronto",
        extra={"evento": "inicio", "banco": settings.db_url.split("://")[0], "log_dir": str(settings.log_path), **info_base},
    )
    yield
    log.info("Backend encerrado", extra={"evento": "fim"})


app = FastAPI(title="Chatbot Condomínio — Jardim das Acácias", version="0.2.0", lifespan=lifespan)


# ---------------- middleware: request id + access log ----------------
@app.middleware("http")
async def access_log(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    token = request_id_ctx.set(rid)
    t0 = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = rid
        return response
    except Exception:
        log.exception("Erro não tratado", extra={"evento": "erro", "path": request.url.path})
        raise
    finally:
        if request.url.path != "/health":  # healthcheck do Docker a cada 10 s só gera ruído
            log.info(
                "%s %s %s", request.method, request.url.path, status,
                extra={
                    "evento": "http",
                    "metodo": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duracao_ms": round((time.perf_counter() - t0) * 1000, 2),
                },
            )
        request_id_ctx.reset(token)


def exigir_chave(authorization: str | None = Header(default=None)) -> None:
    if not settings.backend_api_key:
        return  # sem chave configurada (dev local): acesso livre
    if authorization != f"Bearer {settings.backend_api_key}":
        raise HTTPException(status_code=401, detail="Chave inválida")


async def _registrar(d: Decisao, canal: str, sessao: str | None, usuario: str | None) -> dict:
    reg = await run_in_threadpool(
        log_decisoes.registrar, d, canal, sessao, usuario, request_id_ctx.get()
    )
    if not settings.log_mensagens:
        reg = {**reg, "mensagem": "[omitida]", "resposta": "[omitida]"}
    registrar_decisao(reg)
    return reg


# ---------------- básicos / operação ----------------
@app.get("/health")
def health():
    return {
        "status": "ok" if info_base else "carregando",
        "uptime_s": round(time.time() - iniciado_em),
        "banco": "ok" if log_decisoes.ping() else "indisponivel",
        "base": info_base,
    }


@app.post("/admin/reingest", dependencies=[Depends(exigir_chave)])
async def reingest():
    novo = await run_in_threadpool(motor.carregar)
    info_base.clear()
    info_base.update(novo)
    log.info("Base reingerida", extra={"evento": "reingest", **novo})
    return info_base


@app.get("/admin/metricas", dependencies=[Depends(exigir_chave)])
async def metricas(horas: float = Query(24, gt=0, description="janela em horas")):
    registros = await run_in_threadpool(log_decisoes.listar, horas)
    return {"janela_horas": horas, "base": info_base, **resumir(registros)}


@app.get("/admin/decisoes", dependencies=[Depends(exigir_chave)])
async def decisoes(
    horas: float | None = Query(None, gt=0),
    desfecho: str | None = None,
    intencao: str | None = None,
    canal: str | None = None,
    limite: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    return await run_in_threadpool(log_decisoes.listar, horas, desfecho, intencao, canal, limite, offset)


@app.get("/painel", include_in_schema=False)
def painel():
    return FileResponse(STATIC_DIR / "painel.html")


# ---------------- endpoint nativo ----------------
class ChatIn(BaseModel):
    mensagem: str
    sessao_id: str | None = None
    usuario_id: str | None = None


@app.post("/chat", dependencies=[Depends(exigir_chave)])
async def chat(body: ChatIn):
    sessao = body.sessao_id or uuid.uuid4().hex
    decisao = await run_in_threadpool(motor.responder, body.mensagem, sessoes.historico(sessao))
    sessoes.adicionar(sessao, body.mensagem)
    reg = await _registrar(decisao, "api", sessao, body.usuario_id)
    return {"sessao_id": sessao, "decisao_id": reg.get("id"), **decisao.to_dict()}


# ---------------- compatível com OpenAI (Open WebUI) ----------------
class MensagemOAI(BaseModel):
    role: str
    content: Any = ""


class ChatCompletionIn(BaseModel):
    model: str | None = None
    messages: list[MensagemOAI]
    stream: bool = False
    user: str | None = None


def _texto(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # formato multimodal: [{"type": "text", "text": ...}]
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return str(content or "")


@app.get("/v1/models", dependencies=[Depends(exigir_chave)])
def listar_modelos():
    return {
        "object": "list",
        "data": [{"id": settings.modelo_id, "object": "model", "created": 0, "owned_by": "condominio"}],
    }


@app.post("/v1/chat/completions", dependencies=[Depends(exigir_chave)])
async def chat_completions(
    body: ChatCompletionIn,
    # enviados pelo Open WebUI com ENABLE_FORWARD_USER_INFO_HEADERS=true (só o id vai para o log)
    x_openwebui_user_id: str | None = Header(default=None),
    x_openwebui_chat_id: str | None = Header(default=None),
):
    perguntas = [_texto(m.content) for m in body.messages if m.role == "user"]
    if not perguntas:
        raise HTTPException(status_code=400, detail="Nenhuma mensagem do usuário")
    mensagem, historico = perguntas[-1], perguntas[:-1]

    decisao = await run_in_threadpool(motor.responder, mensagem, historico)
    await _registrar(decisao, "openwebui", x_openwebui_chat_id, x_openwebui_user_id or body.user)

    cid, criado, modelo = f"chatcmpl-{uuid.uuid4().hex}", int(time.time()), settings.modelo_id

    if not body.stream:
        return {
            "id": cid,
            "object": "chat.completion",
            "created": criado,
            "model": modelo,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": decisao.resposta},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    def eventos():
        base = {"id": cid, "object": "chat.completion.chunk", "created": criado, "model": modelo}
        partes = [
            {"index": 0, "delta": {"role": "assistant", "content": decisao.resposta}, "finish_reason": None},
            {"index": 0, "delta": {}, "finish_reason": "stop"},
        ]
        for p in partes:
            yield f"data: {json.dumps({**base, 'choices': [p]}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(eventos(), media_type="text/event-stream")
