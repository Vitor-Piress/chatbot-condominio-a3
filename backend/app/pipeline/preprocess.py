"""Etapa 1 do fluxo: minúsculas, sem acentos e sem stopwords em português."""

import csv
import re
import unicodedata
from pathlib import Path

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
    # domínio: aparecem em quase todo artigo e não distinguem regras
    "condominio", "condominios", "predio", "residencial", "morador", "moradores",
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


def carregar_sinonimos(csv_path: Path) -> dict[str, str]:
    """dados/sinonimos.csv (termo,expansao) -> {termo_normalizado: expansao_normalizada}."""
    if not csv_path.exists():
        return {}
    with csv_path.open(encoding="utf-8") as f:
        return {
            normalizar(r["termo"]): normalizar(r["expansao"])
            for r in csv.DictReader(f)
            if r.get("termo") and r.get("expansao")
        }


def expandir(texto: str, sinonimos: dict[str, str]) -> str:
    """Acrescenta à consulta os termos do vocabulário do regimento (expansão de consulta)."""
    if not sinonimos:
        return texto
    extras = [sinonimos[t] for t in normalizar(texto).split() if t in sinonimos]
    return f"{texto} {' '.join(extras)}" if extras else texto
