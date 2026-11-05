"""Etapa 3: classificador de intenção (TF-IDF uni+bigramas + regressão logística)."""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .features import vetorizador_hibrido
from .preprocess import expandir, preprocessar

log = logging.getLogger(__name__)


@dataclass
class Exemplo:
    pergunta: str
    intencao: str


def carregar_exemplos(csv_path: Path) -> list[Exemplo]:
    with csv_path.open(encoding="utf-8") as f:
        return [
            Exemplo(r["pergunta"].strip(), r["intencao"].strip())
            for r in csv.DictReader(f)
            if r.get("pergunta") and r.get("intencao")
        ]


class ClassificadorIntencao:
    def __init__(self, sinonimos: dict[str, str] | None = None, seed: int = 42):
        self.sinonimos = sinonimos or {}
        self.seed = seed
        self.modelo: Pipeline | None = None
        self.acuracia_validacao: float | None = None
        self.relatorio: str = ""

    def _novo_modelo(self) -> Pipeline:
        return Pipeline(
            [
                ("tfidf", vetorizador_hibrido()),
                ("clf", LogisticRegression(max_iter=1000, C=10.0, random_state=self.seed)),
            ]
        )

    def _prep(self, texto: str) -> str:
        return preprocessar(expandir(texto, self.sinonimos))

    def treinar(self, exemplos: list[Exemplo], frac_validacao: float = 0.3) -> None:
        X = [self._prep(e.pergunta) for e in exemplos]
        y = [e.intencao for e in exemplos]

        X_tr, X_val, y_tr, y_val = train_test_split(
            X, y, test_size=frac_validacao, stratify=y, random_state=self.seed
        )
        self.modelo = self._novo_modelo().fit(X_tr, y_tr)
        pred = self.modelo.predict(X_val)
        self.acuracia_validacao = float(accuracy_score(y_val, pred))
        self.relatorio = classification_report(y_val, pred, zero_division=0)
        log.info(
            "Classificador: %d treino / %d validação, acurácia validação = %.2f",
            len(X_tr), len(X_val), self.acuracia_validacao,
        )

    def prever(self, texto: str) -> tuple[str, float]:
        if self.modelo is None:
            raise RuntimeError("Classificador não treinado")
        probs = self.modelo.predict_proba([self._prep(texto)])[0]
        idx = int(probs.argmax())
        return str(self.modelo.classes_[idx]), float(probs[idx])
