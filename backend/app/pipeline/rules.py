"""Regras determinísticas (regex) de encaminhamento.

Todas operam sobre o texto normalizado (minúsculo e sem acento).
"""

import re

from .preprocess import normalizar

EMERGENCIA = re.compile(
    r"\b("
    r"vazamento de gas|cheiro de gas|vazando gas|gas vazando|"
    r"incendio|fogo|fumaca|pegando fogo|explosao|"
    r"socorro|emergencia|"
    r"ameaca|ameacando|assalto|arma|invasao|invasor|briga|agressao|violencia|"
    r"infarto|desmaio|desmaiou|inconsciente|nao respira|ambulancia|samu|"
    r"ferido|sangrando|afogando|afogamento|choque eletrico|elevador preso|preso no elevador"
    r")\b"
)

FORA_ESCOPO = re.compile(
    r"\b("
    r"boleto|boletos|segunda via|2 via|2a via|cobranca|debito|inadimplen\w*|"
    r"pagar o condominio|valor do condominio|taxa condominial|"
    r"abrir o portao|abre o portao|abrir portao|liberar entrada|"
    r"cpf|rg|telefone do morador|quem mora|dados do morador|dados pessoais|"
    r"aplicar multa|me multar|multar o vizinho|advogado|processo judicial|processar|justica|juridic\w*|"
    r"whatsapp|telegram"
    r")\b"
)

SANCAO_EXCECAO = re.compile(
    r"\b("
    r"excecao|abrir uma excecao|liberacao especial|autorizacao especial|"
    r"cancelar (a |minha )?multa|contestar (a |minha )?multa|recorrer d[ae] multa|"
    r"perdoar|isentar|isencao|punicao|sancao"
    r")\b"
)

PEDIDO_HUMANO = re.compile(
    r"\b("
    r"falar com (a |o )?(administracao|sindico|sindica|atendente|humano|pessoa)|"
    r"encaminhar (para|pra) (a )?administracao|quero um atendente|atendimento humano"
    r")\b"
)


def _match(regex: re.Pattern, texto: str) -> str | None:
    m = regex.search(normalizar(texto))
    return m.group(0) if m else None


def detectar_emergencia(texto: str) -> str | None:
    return _match(EMERGENCIA, texto)


def detectar_fora_escopo(texto: str) -> str | None:
    return _match(FORA_ESCOPO, texto)


def detectar_sancao_excecao(texto: str) -> str | None:
    return _match(SANCAO_EXCECAO, texto)


def detectar_pedido_humano(texto: str) -> str | None:
    return _match(PEDIDO_HUMANO, texto)
