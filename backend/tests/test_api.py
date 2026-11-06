"""API, log em arquivo e métricas (SQLite e logs em pasta temporária)."""

import importlib
import json

import pytest
from fastapi.testclient import TestClient

H = {"Authorization": "Bearer chave-teste"}


@pytest.fixture(scope="module")
def ambiente(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("api")
    mp = pytest.MonkeyPatch()
    mp.setenv("DATABASE_URL", f"sqlite:///{tmp / 'd.db'}")
    mp.setenv("LOG_DIR", str(tmp / "logs"))
    mp.setenv("BACKEND_API_KEY", "chave-teste")
    mp.setenv("GROQ_API_KEY", "")
    from app import config

    config.get_settings.cache_clear()
    import app.main as main

    main = importlib.reload(main)
    with TestClient(main.app) as c:
        yield c, tmp
    mp.undo()
    config.get_settings.cache_clear()


def test_exige_chave(ambiente):
    c, _ = ambiente
    assert c.post("/chat", json={"mensagem": "oi"}).status_code == 401


def test_openai_stream_e_logs(ambiente):
    c, tmp = ambiente
    r = c.post(
        "/v1/chat/completions",
        json={"stream": True, "messages": [{"role": "user", "content": "Quantas vagas de visitante tem?"}]},
        headers={**H, "X-OpenWebUI-User-Id": "u1", "X-OpenWebUI-Chat-Id": "c1"},
    )
    assert r.status_code == 200 and "Art. 6" in r.text and r.text.rstrip().endswith("[DONE]")
    rid = r.headers["x-request-id"]

    linhas = (tmp / "logs" / "decisoes.jsonl").read_text(encoding="utf-8").splitlines()
    reg = json.loads(linhas[-1])
    assert reg["request_id"] == rid and reg["usuario"] == "u1" and reg["sessao"] == "c1"
    assert reg["desfecho"] == "respondido"
    assert rid in (tmp / "logs" / "app.log").read_text(encoding="utf-8")


def test_metricas(ambiente):
    c, _ = ambiente
    c.post("/chat", json={"mensagem": "tem vazamento de gás"}, headers=H)
    m = c.get("/admin/metricas?horas=1", headers=H).json()
    assert m["total"] >= 2 and "emergencia" in m["por_desfecho"]
    assert c.get("/admin/decisoes?limite=1", headers=H).json()[0]["desfecho"] == "emergencia"
