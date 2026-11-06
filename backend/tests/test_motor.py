"""Testes rápidos do motor (rode com: cd backend && pytest)."""

import pytest

from app.config import Settings
from app.pipeline.engine import Desfecho, MotorChatbot


@pytest.fixture(scope="module")
def motor():
    m = MotorChatbot(Settings(groq_api_key="", database_url=""))
    m.carregar()
    return m


@pytest.mark.parametrize(
    "pergunta,esperado",
    [
        ("tem vazamento de gás no bloco B", Desfecho.EMERGENCIA),
        ("qual o valor do boleto de agosto?", Desfecho.FORA_ESCOPO),
        ("quero falar com a administração", Desfecho.PEDIDO_HUMANO),
    ],
)
def test_regras(motor, pergunta, esperado):
    assert motor.responder(pergunta).desfecho == esperado


@pytest.mark.parametrize(
    "pergunta,artigo",
    [
        ("Qual o horário de silêncio?", "1"),
        ("Quanto custa reservar o salão de festas?", "3"),
        ("Posso fazer mudança no domingo?", "5"),
        ("Quantas vagas de visitante tem?", "6"),
    ],
)
def test_respostas_citam_artigo(motor, pergunta, artigo):
    d = motor.responder(pergunta)
    assert d.desfecho == Desfecho.RESPONDIDO
    assert f"Art. {artigo}" in d.resposta


def test_pergunta_de_acompanhamento_usa_contexto(motor):
    d = motor.responder("E no sábado?", ["Em que horário posso fazer obra?"])
    assert d.desfecho == Desfecho.RESPONDIDO
    assert d.usou_contexto
    assert "Art. 5" in d.resposta


def test_registra_tempo_por_etapa(motor):
    d = motor.responder("Quantas vagas de visitante tem?")
    assert {"regras", "classificacao", "recuperacao"} <= d.etapas_ms.keys()
    assert d.llm_status == "desligado"
