"""Métricas de funcionamento calculadas a partir das decisões registradas.

A mesma função `resumir` é usada por:
- GET /admin/metricas      (lê do banco)
- scripts/analisar_logs.py (lê de logs/decisoes.jsonl, offline)
"""

import statistics
from collections import Counter, defaultdict
from datetime import datetime

from .pipeline.preprocess import normalizar

# desfechos que indicam lacuna na base ou no classificador e merecem revisão
DESFECHOS_LACUNA = {"sem_base", "baixa_confianca"}


def _percentil(valores: list[float], p: float) -> float | None:
    if not valores:
        return None
    v = sorted(valores)
    return round(v[min(len(v) - 1, int(round(p * (len(v) - 1))))], 2)


def _hora(ts) -> str:
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return ts.strftime("%Y-%m-%d %H:00")


def resumir(registros: list[dict], top_lacunas: int = 20) -> dict:
    total = len(registros)
    if total == 0:
        return {"total": 0}

    desfechos = Counter(r["desfecho"] for r in registros)
    respondidos = desfechos.get("respondido", 0)
    tempos = [r["tempo_ms"] for r in registros if r.get("tempo_ms") is not None]

    etapas: dict[str, list[float]] = defaultdict(list)
    for r in registros:
        for nome, ms in (r.get("etapas_ms") or {}).items():
            etapas[nome].append(ms)

    llm = [r for r in registros if r.get("llm_status") and r["llm_status"] != "desligado"]
    llm_ms = [r["llm_ms"] for r in llm if r.get("llm_ms") is not None]

    conf_resp = [r["confianca"] for r in registros if r["desfecho"] == "respondido" and r.get("confianca") is not None]
    top_scores = [r["trechos"][0]["score"] for r in registros if r["desfecho"] == "respondido" and r.get("trechos")]

    lacunas = Counter(
        normalizar(r["mensagem"]) for r in registros if r["desfecho"] in DESFECHOS_LACUNA
    )
    exemplos_lacuna: dict[str, dict] = {}
    for r in registros:
        chave = normalizar(r["mensagem"])
        if chave in lacunas and chave not in exemplos_lacuna:
            exemplos_lacuna[chave] = r

    artigos = Counter(
        r["trechos"][0]["referencia"] for r in registros if r["desfecho"] == "respondido" and r.get("trechos")
    )

    serie: dict[str, Counter] = defaultdict(Counter)
    for r in registros:
        if r.get("criado_em"):
            serie[_hora(r["criado_em"])][r["desfecho"]] += 1

    return {
        "total": total,
        "usuarios_distintos": len({r.get("usuario") for r in registros if r.get("usuario")}),
        "por_desfecho": dict(desfechos.most_common()),
        "por_intencao": dict(Counter(r.get("intencao") or "—" for r in registros).most_common()),
        "por_canal": dict(Counter(r.get("canal") or "—" for r in registros).most_common()),
        "taxa_respondido": round(respondidos / total, 4),
        "taxa_encaminhamento": round((total - respondidos) / total, 4),
        "latencia_ms": {
            "mediana": _percentil(tempos, 0.5),
            "p90": _percentil(tempos, 0.9),
            "p99": _percentil(tempos, 0.99),
            "max": round(max(tempos), 2) if tempos else None,
            "por_etapa_mediana": {k: _percentil(v, 0.5) for k, v in etapas.items()},
        },
        "llm": {
            "chamadas": len(llm),
            "por_status": dict(Counter(r["llm_status"] for r in llm)),
            "latencia_mediana_ms": _percentil(llm_ms, 0.5),
            "latencia_p90_ms": _percentil(llm_ms, 0.9),
        },
        "qualidade": {
            "confianca_media_respondidos": round(statistics.mean(conf_resp), 4) if conf_resp else None,
            "similaridade_mediana_respondidos": _percentil(top_scores, 0.5),
            "respostas_com_contexto": sum(1 for r in registros if r.get("usou_contexto")),
        },
        "artigos_mais_citados": dict(artigos.most_common(10)),
        "lacunas": [
            {
                "mensagem": exemplos_lacuna[k]["mensagem"],
                "vezes": n,
                "desfecho": exemplos_lacuna[k]["desfecho"],
                "intencao": exemplos_lacuna[k].get("intencao"),
                "confianca": exemplos_lacuna[k].get("confianca"),
            }
            for k, n in lacunas.most_common(top_lacunas)
        ],
        "serie_horaria": {h: dict(c) for h, c in sorted(serie.items())},
    }
