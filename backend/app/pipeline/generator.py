"""Etapa 5: geração opcional via Groq, usando SOMENTE os trechos recuperados.

Só o prompt com os trechos trafega para a Groq (TLS). Em qualquer falha o
motor volta ao modo extrativo.
"""

import logging
import re

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

    def redigir(self, pergunta: str, resultados: list[Resultado], contexto: list[str]) -> str | None:
        """Devolve o texto gerado, ou None se o LLM não respondeu / não achou resposta."""
        if not self._client:
            return None
        trechos = "\n".join(f"[{r.trecho.referencia}] {r.trecho.texto}" for r in resultados)
        mensagens = [{"role": "system", "content": PROMPT_SISTEMA.format(trechos=trechos)}]
        if contexto:
            mensagens.append(
                {"role": "user", "content": "Perguntas anteriores do morador: " + " | ".join(contexto)}
            )
        mensagens.append({"role": "user", "content": pergunta})
        try:
            resp = self._client.chat.completions.create(
                model=self.settings.groq_model,
                messages=mensagens,
                temperature=0.0,
                max_tokens=400,
            )
            texto = _THINK.sub("", resp.choices[0].message.content or "").strip()
        except Exception:
            log.exception("Falha na Groq; usando modo extrativo")
            return None
        if not texto or "SEM_RESPOSTA" in texto:
            return None
        return texto
