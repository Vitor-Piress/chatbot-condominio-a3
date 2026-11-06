"""Ingestão da base de conhecimento (Markdown) em trechos.

Formato esperado dos arquivos em dados/*.md:

    ## Capítulo N: Título
    Art. 1 - texto...
    (linhas seguintes sem "Art." continuam o artigo anterior)

A intenção de cada trecho vem do título do capítulo (ver MAPA_INTENCOES).
Alterar a base e reexecutar a ingestão (POST /admin/reingest ou reiniciar o
backend) atualiza as respostas sem mudar código (RF08).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from .preprocess import normalizar

# palavra-chave no título do capítulo (normalizado) -> intenção
MAPA_INTENCOES = {
    "convivencia": "convivencia",
    "reserva": "reservas",
    "mudanca": "mudancas_obras",
    "obra": "mudancas_obras",
    "garagem": "garagem_servicos",
    "servico": "garagem_servicos",
}

INTENCOES = ["reservas", "convivencia", "mudancas_obras", "garagem_servicos"]

_CAPITULO = re.compile(r"^#{2,3}\s*(cap[ií]tulo.*)$", re.IGNORECASE)
_ARTIGO = re.compile(r"^\s*(art\.?\s*(\d+)[ºo°]?)\s*[-–—:.]?\s*(.*)$", re.IGNORECASE)
_REF_ARTIGO = re.compile(r"art\.?\s*(\d+)", re.IGNORECASE)


@dataclass
class Trecho:
    id: str
    texto: str
    capitulo: str
    intencao: str | None
    artigos: list[str] = field(default_factory=list)
    fonte: str = ""

    @property
    def referencia(self) -> str:
        arts = ", ".join(f"Art. {a}" for a in self.artigos) or "trecho sem artigo"
        return f"{arts} ({self.capitulo})" if self.capitulo else arts


def intencao_do_capitulo(titulo: str) -> str | None:
    t = normalizar(titulo)
    for chave, intencao in MAPA_INTENCOES.items():
        if chave in t:
            return intencao
    return None


def _artigos_por_capitulo(caminho: Path) -> list[tuple[str, list[tuple[str, str]]]]:
    """[(capitulo, [(numero_artigo, texto), ...]), ...]"""
    capitulos: list[tuple[str, list[tuple[str, str]]]] = []
    atual: list[tuple[str, str]] | None = None

    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        if m := _CAPITULO.match(linha):
            atual = []
            capitulos.append((m.group(1).strip(), atual))
            continue
        if linha.startswith("#"):
            continue
        if atual is None:
            continue  # texto antes do primeiro capítulo (título do documento)
        if m := _ARTIGO.match(linha):
            atual.append((m.group(2), f"Art. {m.group(2)} - {m.group(3).strip()}"))
        elif atual:
            num, texto = atual[-1]
            atual[-1] = (num, f"{texto} {linha}")
    return capitulos


def carregar_trechos(
    dados_dir: Path, estrategia: str = "artigo", tamanho: int = 1000, sobreposicao: int = 200
) -> list[Trecho]:
    trechos: list[Trecho] = []
    for arquivo in sorted(dados_dir.glob("*.md")):
        for capitulo, artigos in _artigos_por_capitulo(arquivo):
            intencao = intencao_do_capitulo(capitulo)
            if estrategia == "artigo":
                for num, texto in artigos:
                    trechos.append(
                        Trecho(
                            id=f"{arquivo.stem}:art{num}",
                            texto=texto,
                            capitulo=capitulo,
                            intencao=intencao,
                            artigos=[num],
                            fonte=arquivo.name,
                        )
                    )
            else:
                corpo = "\n".join(t for _, t in artigos)
                passo = max(1, tamanho - sobreposicao)
                for i, ini in enumerate(range(0, max(1, len(corpo)), passo)):
                    pedaco = corpo[ini : ini + tamanho]
                    if not pedaco.strip():
                        continue
                    arts = list(dict.fromkeys(_REF_ARTIGO.findall(pedaco)))
                    if not arts:
                        # pedaço começou no meio de um artigo: herda o último artigo anterior
                        anteriores = _REF_ARTIGO.findall(corpo[:ini])
                        arts = anteriores[-1:] if anteriores else []
                    trechos.append(
                        Trecho(
                            id=f"{arquivo.stem}:{normalizar(capitulo).replace(' ', '_')}:c{i}",
                            texto=pedaco,
                            capitulo=capitulo,
                            intencao=intencao,
                            artigos=arts,
                            fonte=arquivo.name,
                        )
                    )
                    if ini + tamanho >= len(corpo):
                        break
    return trechos
