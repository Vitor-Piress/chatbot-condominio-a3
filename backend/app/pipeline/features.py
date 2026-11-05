"""Vetorização TF-IDF compartilhada por classificador e recuperador.

Combina:
- palavras (unigramas e bigramas), como pede o PRD;
- n-gramas de caracteres (3 a 5, dentro de cada palavra), que aproximam
  plural/flexão ("obra" ~ "obras", "mudanca" ~ "mudancas") e toleram erros de
  digitação, um dos vieses listados na seção 4 do PRD.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion


def vetorizador_hibrido() -> FeatureUnion:
    return FeatureUnion(
        [
            ("palavras", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
            ("caracteres", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)),
        ]
    )
