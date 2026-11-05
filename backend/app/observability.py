"""Logging estruturado: stdout + arquivos para análise posterior.

Saídas:
- stdout                 texto legível (LOG_FORMAT=texto) ou JSON (LOG_FORMAT=json)
- logs/app.log           todos os eventos em JSON (uma linha por evento), com rotação
- logs/decisoes.jsonl    uma linha por resposta do bot com a decisão completa (RF07),
                         pensada para análise offline (scripts/analisar_logs.py, pandas, jq)

Todo evento carrega o `request_id` da requisição HTTP que o originou.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

# atributos padrão de LogRecord que não devem ir como "extra" no JSON
_PADRAO = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime", "request_id"}

LOGGER_DECISOES = "chatbot.decisoes"
LOGGER_DECISOES_ARQUIVO = "chatbot.decisoes_arquivo"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        dados = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
        }
        dados.update({k: v for k, v in vars(record).items() if k not in _PADRAO})
        if record.exc_info:
            dados["exc"] = self.formatException(record.exc_info)
        return json.dumps(dados, ensure_ascii=False, default=str)


class TextoFormatter(logging.Formatter):
    def __init__(self):
        super().__init__("%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s", "%H:%M:%S")


def configurar_logging(nivel: str = "INFO", formato: str = "texto", log_dir: Path | None = None) -> None:
    filtro = RequestIdFilter()
    raiz = logging.getLogger()
    raiz.handlers.clear()
    raiz.setLevel(nivel.upper())

    stdout = logging.StreamHandler(sys.stdout)
    stdout.setFormatter(JsonFormatter() if formato == "json" else TextoFormatter())
    stdout.addFilter(filtro)
    raiz.addHandler(stdout)

    # decisoes.jsonl: logger dedicado, sem propagação, só a linha JSON da decisão
    arq = logging.getLogger(LOGGER_DECISOES_ARQUIVO)
    arq.handlers.clear()
    arq.setLevel(logging.INFO)
    arq.propagate = False

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        app_file = RotatingFileHandler(log_dir / "app.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8")
        app_file.setFormatter(JsonFormatter())
        app_file.addFilter(filtro)
        raiz.addHandler(app_file)

        dec_file = RotatingFileHandler(log_dir / "decisoes.jsonl", maxBytes=50_000_000, backupCount=10, encoding="utf-8")
        dec_file.setFormatter(logging.Formatter("%(message)s"))
        arq.addHandler(dec_file)

    # uvicorn passa a usar nossos handlers; o access log é substituído pelo middleware
    for nome in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(nome)
        lg.handlers.clear()
        lg.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    for ruidoso in ("httpx", "httpcore", "sentence_transformers", "chromadb"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)


def registrar_decisao(registro: dict) -> None:
    """Escreve a decisão completa em decisoes.jsonl e um resumo no stdout/app.log."""
    logging.getLogger(LOGGER_DECISOES_ARQUIVO).info(json.dumps(registro, ensure_ascii=False, default=str))
    top = registro["trechos"][0]["score"] if registro.get("trechos") else "-"
    logging.getLogger(LOGGER_DECISOES).info(
        f"{registro['desfecho']} intencao={registro.get('intencao')} conf={registro.get('confianca')} "
        f"top={top} llm={registro.get('llm_usado')} {registro.get('tempo_ms')}ms",
        extra={
            "evento": "decisao",
            "decisao_id": registro.get("id"),
            "canal": registro.get("canal"),
            "desfecho": registro["desfecho"],
            "intencao": registro.get("intencao"),
            "confianca": registro.get("confianca"),
            "tempo_ms": registro.get("tempo_ms"),
            "llm_usado": registro.get("llm_usado"),
        },
    )
