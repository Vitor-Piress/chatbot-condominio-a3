"""Avaliação da POC com os casos de teste (PRD, seção 6).

Uso (de dentro de backend/):
    python -m scripts.avaliar                       # configuração do .env
    python -m scripts.avaliar --chunk caracteres
    python -m scripts.avaliar --retriever embeddings
    python -m scripts.avaliar --comparar            # TF-IDF x embeddings, artigo x caracteres
    python -m scripts.avaliar --llm                 # liga a Groq (se houver chave)

Gera, em dados/resultados/:
    <timestamp>_<config>.csv   resultado caso a caso (planilha de testes)
    <timestamp>_<config>.json  métricas agregadas
"""

import argparse
import csv
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

from sklearn.metrics import classification_report, confusion_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.pipeline.engine import Desfecho, MotorChatbot  # noqa: E402
from app.pipeline.knowledge import INTENCOES  # noqa: E402


def p90(valores: list[float]) -> float:
    if not valores:
        return 0.0
    v = sorted(valores)
    return v[min(len(v) - 1, int(round(0.9 * (len(v) - 1))))]


def avaliar(casos: list[dict], retriever: str, chunk: str, llm: bool, saida: Path) -> dict:
    s = get_settings().model_copy(update={"retriever": retriever, "chunk_strategy": chunk})
    if not llm:
        s = s.model_copy(update={"llm_habilitado": False})
    motor = MotorChatbot(s)
    info = motor.carregar()
    nome = f"{retriever}_{chunk}{'_llm' if motor.gerador.ativo else ''}"

    linhas, tempos = [], []
    y_true, y_pred = [], []
    for c in casos:
        contexto = [x for x in (c.get("contexto") or "").split("|") if x.strip()]
        d = motor.responder(c["pergunta"], contexto)
        tempos.append(d.tempo_ms)

        esperados = [x for x in c["desfecho_esperado"].split("|") if x]
        artigo = c["artigo_esperado"].strip()
        recuperados = [a for t in d.trechos for a in t.get("artigos", [])]
        hit3 = (artigo in recuperados) if artigo else None
        cita_artigo = (f"Art. {artigo}" in d.resposta) if artigo else None

        if d.desfecho.value not in esperados:
            resultado = "Erro"
        elif d.desfecho == Desfecho.RESPONDIDO and artigo and not cita_artigo:
            resultado = "Parcial"  # respondeu, mas com o artigo errado
        else:
            resultado = "Acerto"

        if c["intencao_esperada"]:
            y_true.append(c["intencao_esperada"])
            y_pred.append(d.intencao or "nenhuma")

        linhas.append(
            {
                "id": c["id"],
                "pergunta": c["pergunta"],
                "categoria": c["categoria"],
                "intencao_esperada": c["intencao_esperada"],
                "intencao_obtida": d.intencao or "",
                "confianca": d.confianca if d.confianca is not None else "",
                "artigo_esperado": artigo,
                "artigos_recuperados": " ".join(recuperados),
                "hit@3": "" if hit3 is None else int(hit3),
                "desfecho_esperado": c["desfecho_esperado"],
                "desfecho_obtido": d.desfecho.value,
                "llm_usado": int(d.llm_usado),
                "tempo_ms": d.tempo_ms,
                "resultado": resultado,
                "resposta_obtida": d.resposta.replace("\n", " "),
            }
        )

    def taxa(filtro, cond) -> float | None:
        sel = [l for l in linhas if filtro(l)]
        return round(sum(1 for l in sel if cond(l)) / len(sel), 4) if sel else None

    respondiveis = lambda l: l["artigo_esperado"] != ""  # noqa: E731
    metricas = {
        "config": nome,
        "base": info,
        "casos": len(linhas),
        "acuracia_intencao": taxa(lambda l: l["intencao_esperada"], lambda l: l["intencao_esperada"] == l["intencao_obtida"]),
        "hit@3": taxa(respondiveis, lambda l: l["hit@3"] == 1),
        "taxa_acerto_resposta": taxa(respondiveis, lambda l: l["resultado"] == "Acerto"),
        "encaminhamento_emergencia": taxa(lambda l: l["categoria"] == "emergencia", lambda l: l["desfecho_obtido"] == "emergencia"),
        "encaminhamento_fora_escopo": taxa(lambda l: l["categoria"] == "fora_escopo", lambda l: l["desfecho_obtido"] != "respondido"),
        "ambiguas_sem_resposta_inventada": taxa(lambda l: l["categoria"] == "ambigua", lambda l: l["desfecho_obtido"] != "respondido"),
        "acertos_totais": taxa(lambda l: True, lambda l: l["resultado"] == "Acerto"),
        "tempo_ms_mediana": round(statistics.median(tempos), 2) if tempos else None,
        "tempo_ms_p90": round(p90(tempos), 2),
        "erros": [l["id"] for l in linhas if l["resultado"] != "Acerto"],
    }
    if y_true:
        rotulos = INTENCOES
        metricas["matriz_confusao"] = {
            "rotulos": rotulos,
            "matriz": confusion_matrix(y_true, y_pred, labels=rotulos).tolist(),
        }
        metricas["relatorio_intencao"] = classification_report(
            y_true, y_pred, labels=rotulos, zero_division=0, output_dict=True
        )

    saida.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    with (saida / f"{carimbo}_{nome}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    (saida / f"{carimbo}_{nome}.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== {nome} ===")
    for k in ("acuracia_intencao", "hit@3", "taxa_acerto_resposta", "encaminhamento_emergencia",
              "encaminhamento_fora_escopo", "ambiguas_sem_resposta_inventada", "acertos_totais",
              "tempo_ms_mediana", "tempo_ms_p90"):
        print(f"  {k:34} {metricas[k]}")
    if metricas["erros"]:
        print("  casos com Erro/Parcial:")
        for l in linhas:
            if l["resultado"] != "Acerto":
                print(f"    {l['id']} [{l['resultado']}] {l['pergunta']!r} -> {l['desfecho_obtido']}"
                      f" (intenção {l['intencao_obtida'] or '-'} {l['confianca']}, artigos {l['artigos_recuperados'] or '-'})")
    return metricas


def main() -> None:
    s = get_settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--casos", type=Path, default=s.dados_path / "casos_teste.csv")
    ap.add_argument("--saida", type=Path, default=s.dados_path / "resultados")
    ap.add_argument("--retriever", choices=["tfidf", "embeddings"], default=s.retriever)
    ap.add_argument("--chunk", choices=["artigo", "caracteres"], default=s.chunk_strategy)
    ap.add_argument("--llm", action="store_true", help="usa a Groq se GROQ_API_KEY estiver definida")
    ap.add_argument("--comparar", action="store_true", help="roda os experimentos comparativos")
    a = ap.parse_args()

    with a.casos.open(encoding="utf-8") as f:
        casos = list(csv.DictReader(f))

    if not a.comparar:
        avaliar(casos, a.retriever, a.chunk, a.llm, a.saida)
        return

    resumo = []
    for retriever in ("tfidf", "embeddings"):
        for chunk in ("artigo", "caracteres"):
            try:
                resumo.append(avaliar(casos, retriever, chunk, a.llm, a.saida))
            except RuntimeError as e:
                print(f"\n[pulado] {retriever}/{chunk}: {e}")
    print("\n=== Comparativo ===")
    print(f"  {'config':28} {'hit@3':>7} {'acerto':>7} {'intenção':>9} {'p90 ms':>8}")
    for m in resumo:
        print(f"  {m['config']:28} {m['hit@3']!s:>7} {m['taxa_acerto_resposta']!s:>7} "
              f"{m['acuracia_intencao']!s:>9} {m['tempo_ms_p90']!s:>8}")


if __name__ == "__main__":
    main()
