"""Etapa 4: recuperação por similaridade do cosseno sobre TF-IDF.

A alternativa com embeddings (all-MiniLM-L6-v2 + ChromaDB) deve implementar a
mesma interface `buscar` para a comparação de hit@3.
"""

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .knowledge import Trecho
from .preprocess import preprocessar


@dataclass
class Resultado:
    trecho: Trecho
    score: float


class RecuperadorTfidf:
    def __init__(self):
        self.trechos: list[Trecho] = []
        self.vetorizador: TfidfVectorizer | None = None
        self.matriz = None

    def indexar(self, trechos: list[Trecho], textos_extras: list[str] | None = None) -> None:
        """Indexa os trechos. `textos_extras` (ex.: perguntas de treino) só ampliam o vocabulário."""
        self.trechos = trechos
        corpus = [preprocessar(t.texto) for t in trechos]
        self.vetorizador = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self.vetorizador.fit(corpus + [preprocessar(t) for t in (textos_extras or [])])
        self.matriz = self.vetorizador.transform(corpus)

    def buscar(self, consulta: str, intencao: str | None = None, k: int = 3) -> list[Resultado]:
        if self.vetorizador is None or not self.trechos:
            return []
        q = self.vetorizador.transform([preprocessar(consulta)])
        scores = cosine_similarity(q, self.matriz)[0]
        candidatos = [
            Resultado(t, float(s))
            for t, s in zip(self.trechos, scores)
            if intencao is None or t.intencao == intencao
        ]
        candidatos.sort(key=lambda r: r.score, reverse=True)
        return candidatos[:k]
