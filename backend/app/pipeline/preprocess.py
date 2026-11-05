"""Etapa 1 do fluxo: minúsculas, sem acentos e sem stopwords em português."""

import re
import unicodedata

# Lista enxuta e sem acentos. Palavras como "nao", "pode" e "posso" são mantidas
# de propósito porque mudam o sentido da pergunta.
STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "por", "pelo", "pela", "pelos", "pelas", "para",
    "pra", "pro", "com", "sem", "ao", "aos", "e", "ou", "que", "se", "me", "te", "eu",
    "voce", "ele", "ela", "nos", "eles", "elas", "meu", "minha", "meus", "minhas",
    "seu", "sua", "seus", "suas", "isso", "isto", "esse", "essa", "este", "esta",
    "aquele", "aquela", "la", "aqui", "ai", "entao", "tambem", "ja", "so", "muito",
    "mais", "bem", "ser", "estar", "ter", "tem", "ha", "foi", "era", "sao", "esta",
    "estou", "vou", "vai", "gostaria", "saber", "queria", "favor", "ola", "oi",
    "obrigado", "obrigada", "qual", "quais", "como",
}

_NAO_ALFANUM = re.compile(r"[^a-z0-9\s]")
_ESPACOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e sem pontuação. Não remove stopwords."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = _NAO_ALFANUM.sub(" ", texto)
    return _ESPACOS.sub(" ", texto).strip()


def preprocessar(texto: str) -> str:
    """Texto pronto para TF-IDF."""
    return " ".join(t for t in normalizar(texto).split() if t not in STOPWORDS)
