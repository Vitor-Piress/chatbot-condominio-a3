"""Etapa 5: geração opcional via Groq, usando SOMENTE os trechos recuperados.

Só o prompt com os trechos trafega para a Groq (TLS). Em qualquer falha o
motor volta ao modo extrativo.
"""

import logging
import re
import time
from dataclasses import dataclass

from ..config import Settings
from .retriever import Resultado

log = logging.getLogger(__name__)

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

PROMPT_SISTEMA = """Você é o assistente virtual do Residencial Jardim das Acácias (condomínio fictício).
Responda à pergunta do morador usando APENAS os trechos do regimento fornecidos abaixo.
Regras:
- Não invente regras, valores, horários ou exceções que não estejam nos trechos.
- Se os trechos não respondem à pergunta, responda exatamente: SEM_RESPOSTA
- Cite o artigo usado (ex.: "conforme o Art. 3").
- Responda em português, de forma educada, direta e em no máximo 3 frases.

TRECHOS DO REGIMENTO:
{trechos}"""


@dataclass
class Geracao:
    texto: str | None
    status: str  # ok | sem_resposta | erro
    ms: float
    modelo: str
    tokens_entrada: int | None = None
    tokens_saida: int | None = None


class GeradorGroq:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        if settings.usa_llm:
            from groq import Groq

            self._client = Groq(api_key=settings.groq_api_key, timeout=settings.llm_timeout_s)

    @property
    def ativo(self) -> bool:
        return self._client is not None

    def redigir(self, pergunta: str, resultados: list[Resultado], contexto: list[str]) -> Geracao | None:
        """Texto gerado (ou None em Geracao.texto se o LLM falhou / não achou resposta)."""
        if not self._client:
            return None
        modelo = self.settings.groq_model
        trechos = "\n".join(f"[{r.trecho.referencia}] {r.trecho.texto}" for r in resultados)
        mensagens = [{"role": "system", "content": PROMPT_SISTEMA.format(trechos=trechos)}]
        if contexto:
            mensagens.append(
                {"role": "user", "content": "Perguntas anteriores do morador: " + " | ".join(contexto)}
            )
        mensagens.append({"role": "user", "content": pergunta})

        t0 = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(
                model=modelo, messages=mensagens, temperature=0.0, max_tokens=400
            )
        except Exception as e:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            log.error(
                "Falha na Groq (%s); usando modo extrativo", type(e).__name__,
                extra={"evento": "llm", "llm_status": "erro", "llm_modelo": modelo, "llm_ms": ms, "erro": str(e)},
            )
            return Geracao(None, "erro", ms, modelo)

        ms = round((time.perf_counter() - t0) * 1000, 1)
        texto = _THINK.sub("", resp.choices[0].message.content or "").strip()
        uso = getattr(resp, "usage", None)
        g = Geracao(
            texto=texto if texto and "SEM_RESPOSTA" not in texto else None,
            status="ok" if texto and "SEM_RESPOSTA" not in texto else "sem_resposta",
            ms=ms,
            modelo=modelo,
            tokens_entrada=getattr(uso, "prompt_tokens", None),
            tokens_saida=getattr(uso, "completion_tokens", None),
        )
        log.info(
            "Groq %s em %.0f ms", g.status, ms,
            extra={
                "evento": "llm", "llm_status": g.status, "llm_modelo": modelo, "llm_ms": ms,
                "tokens_entrada": g.tokens_entrada, "tokens_saida": g.tokens_saida,
            },
        )
        return g
