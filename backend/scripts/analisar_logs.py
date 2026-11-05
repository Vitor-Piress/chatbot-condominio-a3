"""Análise offline de logs/decisoes.jsonl (inclui arquivos rotacionados .1, .2, ...).

Uso (de dentro de backend/):
    python -m scripts.analisar_logs                         # resumo de tudo
    python -m scripts.analisar_logs --horas 24              # só as últimas 24 h
    python -m scripts.analisar_logs --csv decisoes.csv      # exporta para planilha
    python -m scripts.analisar_logs --json resumo.json      # salva o resumo completo
    python -m scripts.analisar_logs --arquivo ../logs/decisoes.jsonl   # logs do Docker
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.monitoring import resumir  # noqa: E402


def ler_registros(arquivo: Path) -> list[dict]:
    arquivos = sorted(arquivo.parent.glob(arquivo.name + ".*"), reverse=True) + [arquivo]
    registros = []
    for a in arquivos:
        if not a.exists():
            continue
        with a.open(encoding="utf-8") as f:
            for n, linha in enumerate(f, 1):
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    registros.append(json.loads(linha))
                except json.JSONDecodeError:
                    print(f"[aviso] linha inválida em {a.name}:{n}", file=sys.stderr)
    return registros


def filtrar_horas(registros: list[dict], horas: float) -> list[dict]:
    limite = datetime.now(timezone.utc) - timedelta(hours=horas)
    saida = []
    for r in registros:
        ts = r.get("criado_em")
        if not ts:
            continue
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt >= limite:
            saida.append(r)
    return saida


def main() -> None:
    s = get_settings()
    padrao = (s.log_path or Path("logs")) / "decisoes.jsonl"
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arquivo", type=Path, default=padrao)
    ap.add_argument("--horas", type=float)
    ap.add_argument("--csv", type=Path, help="exporta as decisões (achatadas) para CSV")
    ap.add_argument("--json", type=Path, help="salva o resumo completo em JSON")
    a = ap.parse_args()

    registros = ler_registros(a.arquivo)
    if a.horas:
        registros = filtrar_horas(registros, a.horas)
    if not registros:
        print(f"Nenhuma decisão encontrada em {a.arquivo}")
        return

    r = resumir(registros)
    lat, llm, q = r["latencia_ms"], r["llm"], r["qualidade"]
    print(f"Decisões: {r['total']}  ·  usuários distintos: {r['usuarios_distintos']}")
    print(f"Respondidas: {r['taxa_respondido']:.0%}  ·  encaminhadas: {r['taxa_encaminhamento']:.0%}")
    print("\nDesfechos:")
    for k, v in r["por_desfecho"].items():
        print(f"  {k:18} {v:6}  {v / r['total']:.0%}")
    print("\nIntenções:")
    for k, v in r["por_intencao"].items():
        print(f"  {k:18} {v:6}")
    print(f"\nLatência (ms): mediana {lat['mediana']} · p90 {lat['p90']} · p99 {lat['p99']} · máx {lat['max']}")
    print(f"  por etapa (mediana): {lat['por_etapa_mediana']}")
    print(f"LLM: {llm['chamadas']} chamadas {llm['por_status']} · mediana {llm['latencia_mediana_ms']} ms")
    print(f"Qualidade: confiança média {q['confianca_media_respondidos']} · "
          f"similaridade mediana {q['similaridade_mediana_respondidos']} · "
          f"com contexto {q['respostas_com_contexto']}")
    if r["lacunas"]:
        print("\nLacunas mais frequentes (revisar base / sinônimos / treino):")
        for l in r["lacunas"]:
            print(f"  {l['vezes']:3}x [{l['desfecho']}] {l['mensagem']}")

    if a.json:
        a.json.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nResumo salvo em {a.json}")
    if a.csv:
        campos = ["id", "criado_em", "request_id", "canal", "usuario", "sessao", "mensagem", "desfecho",
                  "intencao", "confianca", "usou_contexto", "regra", "trecho_top", "score_top",
                  "llm_usado", "llm_status", "llm_ms", "tempo_ms", "resposta"]
        with a.csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
            w.writeheader()
            for reg in registros:
                top = (reg.get("trechos") or [{}])[0]
                w.writerow({**reg, "trecho_top": top.get("referencia"), "score_top": top.get("score")})
        print(f"CSV salvo em {a.csv}")


if __name__ == "__main__":
    main()
