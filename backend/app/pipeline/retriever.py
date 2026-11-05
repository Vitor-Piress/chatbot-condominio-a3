"""Etapa 4: recuperação por similaridade do cosseno.

Duas implementações com a mesma interface, para o experimento de hit@3:
- RecuperadorTfidf (padrão): TF-IDF de palavras + caracteres.
- RecuperadorEmbeddings (opcional): all-MiniLM-L6-v2 + ChromaDB.
  Requer `pip install -r requirements-embeddings.txt`.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sklearn.metrics.pairwise import cosine_similarity

from .features import vetorizador_hibrido
from .knowledge import Trecho
from .preprocess import expandir, preprocessar

log = logging.getLogger(__name__)


@dataclass
class Resultado:
    trecho: Trecho
    score: float


class Recuperador(Protocol):
    nome: str

    def indexar(self, trechos: list[Trecho], textos_extras: list[str] | None = None) -> None: ...

    def buscar(self, consulta: str, intencao: str | None = None, k: int = 3) -> list[Resultado]: ...


class RecuperadorTfidf:
    nome = "tfidf"

    def __init__(self, sinonimos: dict[str, str] | None = None):
        self.sinonimos = sinonimos or {}
        self.trechos: list[Trecho] = []
        self.vetorizador = None
        self.matriz = None

    def indexar(self, trechos: list[Trecho], textos_extras: list[str] | None = None) -> None:
        """Indexa os trechos. `textos_extras` (ex.: perguntas de treino) só ampliam o vocabulário."""
        self.trechos = trechos
        # o título do capítulo entra no índice: acrescenta o vocabulário do tema ao artigo
        corpus = [preprocessar(f"{t.capitulo} {t.texto}") for t in trechos]
        self.vetorizador = vetorizador_hibrido()
        self.vetorizador.fit(corpus + [preprocessar(t) for t in (textos_extras or [])])
        self.matriz = self.vetorizador.transform(corpus)

    def buscar(self, consulta: str, intencao: str | None = None, k: int = 3) -> list[Resultado]:
        if self.vetorizador is None or not self.trechos:
            return []
        q = self.vetorizador.transform([preprocessar(expandir(consulta, self.sinonimos))])
        scores = cosine_similarity(q, self.matriz)[0]
        candidatos = [
            Resultado(t, float(s))
            for t, s in zip(self.trechos, scores)
            if intencao is None or t.intencao == intencao
        ]
        candidatos.sort(key=lambda r: r.score, reverse=True)
        return candidatos[:k]


class RecuperadorEmbeddings:
    """Alternativa da seção 3 do PRD. Os vetores ficam persistidos em chroma_db/."""

    nome = "embeddings"
    MODELO = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, persist_dir: Path, sinonimos: dict[str, str] | None = None):
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "RETRIEVER=embeddings requer: pip install -r requirements-embeddings.txt"
            ) from e
        self.sinonimos = sinonimos or {}
        self.modelo = SentenceTransformer(self.MODELO)
        self.cliente = chromadb.PersistentClient(path=str(persist_dir))
        self.colecao = None
        self.por_id: dict[str, Trecho] = {}

    def _emb(self, textos: list[str]) -> list[list[float]]:
        return self.modelo.encode(textos, normalize_embeddings=True).tolist()

    def indexar(self, trechos: list[Trecho], textos_extras: list[str] | None = None) -> None:
        # recria a coleção a cada ingestão para refletir a base atual (RF08)
        try:
            self.cliente.delete_collection("regimento")
        except Exception:
            pass
        self.colecao = self.cliente.create_collection("regimento", metadata={"hnsw:space": "cosine"})
        self.por_id = {t.id: t for t in trechos}
        if trechos:
            self.colecao.add(
                ids=[t.id for t in trechos],
                documents=[t.texto for t in trechos],
                embeddings=self._emb([t.texto for t in trechos]),
                metadatas=[{"intencao": t.intencao or ""} for t in trechos],
            )

    def buscar(self, consulta: str, intencao: str | None = None, k: int = 3) -> list[Resultado]:
        if self.colecao is None or not self.por_id:
            return []
        n = min(k, sum(1 for t in self.por_id.values() if intencao is None or t.intencao == intencao))
        if n == 0:
            return []
        r = self.colecao.query(
            query_embeddings=self._emb([expandir(consulta, self.sinonimos)]),
            n_results=n,
            where={"intencao": intencao} if intencao else None,
        )
        # distância cosseno do Chroma = 1 - similaridade
        return [
            Resultado(self.por_id[i], 1.0 - float(d))
            for i, d in zip(r["ids"][0], r["distances"][0])
        ]
