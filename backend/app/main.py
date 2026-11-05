"""API FastAPI.

- POST /chat                   endpoint nativo, independente de interface (canais futuros)
- GET  /v1/models              \
- POST /v1/chat/completions    / compatíveis com OpenAI, consumidos pelo Open WebUI
- POST /admin/reingest         reexecuta a ingestão da base sem reiniciar (RF08)
"""

import json
import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import get_settings
from .db import LogDecisoes
from .pipeline.engine import MotorChatbot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("chatbot")

settings = get_settings()
motor = MotorChatbot(settings)
log_decisoes = LogDecisoes(settings.db_url)
info_base: dict = {}

# contexto do endpoint nativo: últimas N perguntas por sessão (em memória)
sessoes: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=settings.turnos_contexto))


@asynccontextmanager
async def lifespan(_: FastAPI):
    log_decisoes.criar_tabelas()
    info_base.update(motor.carregar())
    yield


app = FastAPI(title="Chatbot Condomínio — Jardim das Acácias", version="0.1.0", lifespan=lifespan)


def exigir_chave(authorization: str | None = Header(default=None)) -> None:
    if not settings.backend_api_key:
        return  # sem chave configurada (dev local): acesso livre
    if authorization != f"Bearer {settings.backend_api_key}":
        raise HTTPException(status_code=401, detail="Chave inválida")


# ---------------- básicos ----------------
@app.get("/health")
def health():
    return {"status": "ok", "base": info_base}


@app.post("/admin/reingest", dependencies=[Depends(exigir_chave)])
async def reingest():
    info_base.clear()
    info_base.update(await run_in_threadpool(motor.carregar))
    return info_base


# ---------------- endpoint nativo ----------------
class ChatIn(BaseModel):
    mensagem: str
    sessao_id: str | None = None


@app.post("/chat", dependencies=[Depends(exigir_chave)])
async def chat(body: ChatIn):
    sessao = body.sessao_id or str(uuid.uuid4())
    historico = list(sessoes[sessao])
    decisao = await run_in_threadpool(motor.responder, body.mensagem, historico)
    sessoes[sessao].append(body.mensagem)
    await run_in_threadpool(log_decisoes.registrar, decisao, "api", sessao)
    return {"sessao_id": sessao, **decisao.to_dict()}


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
async def chat_completions(body: ChatCompletionIn):
    perguntas = [_texto(m.content) for m in body.messages if m.role == "user"]
    if not perguntas:
        raise HTTPException(status_code=400, detail="Nenhuma mensagem do usuário")
    mensagem, historico = perguntas[-1], perguntas[:-1]

    decisao = await run_in_threadpool(motor.responder, mensagem, historico)
    await run_in_threadpool(log_decisoes.registrar, decisao, "openwebui", body.user)

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
