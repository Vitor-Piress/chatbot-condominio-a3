"""Orquestra o fluxo do PRD (seção 3) e devolve a decisão completa para log (RF07)."""

import logging
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from enum import Enum

from ..config import Settings
from . import rules
from .classifier import ClassificadorIntencao, carregar_exemplos
from .generator import GeradorGroq
from .knowledge import carregar_trechos
from .preprocess import carregar_sinonimos
from .retriever import Recuperador, RecuperadorEmbeddings, RecuperadorTfidf, Resultado

log = logging.getLogger(__name__)


class Desfecho(str, Enum):
    RESPONDIDO = "respondido"
    EMERGENCIA = "emergencia"
    FORA_ESCOPO = "fora_escopo"
    BAIXA_CONFIANCA = "baixa_confianca"
    SEM_BASE = "sem_base"
    SANCAO_EXCECAO = "sancao_excecao"
    PEDIDO_HUMANO = "pedido_humano"


RESPOSTA_EMERGENCIA = (
    "⚠️ Isto parece uma emergência. Ligue imediatamente:\n"
    "- **190** Polícia Militar\n"
    "- **192** SAMU\n"
    "- **193** Corpo de Bombeiros\n\n"
    "E avise a portaria do condomínio. {contato}"
)
RESPOSTA_FORA_ESCOPO = (
    "Esse assunto não é tratado por este assistente (cobranças, portões, dados de moradores, "
    "multas e orientação jurídica ficam com a administração). Procure a administração: {contato}"
)
RESPOSTA_SEM_BASE = "Não encontrei essa informação na base; procure a administração. {contato}"
RESPOSTA_BAIXA_CONFIANCA = (
    "Não tenho certeza sobre o que você está perguntando. Posso ajudar com reservas de áreas "
    "comuns, regras de convivência, mudanças e obras, ou garagem e serviços. Pode reformular? "
    "Se preferir, fale com a administração: {contato}"
)
RESPOSTA_SANCAO = (
    "Pedidos de exceção, liberação especial ou decisões sobre multas e sanções são avaliados "
    "pela administração. Encaminhe sua solicitação: {contato}"
)
RESPOSTA_HUMANO = "Claro! Fale com a administração: {contato}"


@dataclass
class Decisao:
    mensagem: str
    resposta: str
    desfecho: Desfecho
    intencao: str | None = None
    confianca: float | None = None
    usou_contexto: bool = False
    regra: str | None = None
    trechos: list[dict] = field(default_factory=list)
    llm_usado: bool = False
    llm_status: str | None = None  # ok | sem_resposta | erro | desligado
    llm_ms: float | None = None
    llm_modelo: str | None = None
    etapas_ms: dict[str, float] = field(default_factory=dict)
    tempo_ms: float = 0.0

    @property
    def encaminhado(self) -> bool:
        return self.desfecho != Desfecho.RESPONDIDO

    def to_dict(self) -> dict:
        d = asdict(self)
        d["desfecho"] = self.desfecho.value
        d["encaminhado"] = self.encaminhado
        return d


class MotorChatbot:
    def __init__(self, settings: Settings):
        self.s = settings
        self.classificador = ClassificadorIntencao()
        self.recuperador: Recuperador = RecuperadorTfidf()
        self.gerador = GeradorGroq(settings)
        self.n_trechos = 0

    def _novo_recuperador(self, sinonimos: dict[str, str]) -> Recuperador:
        if self.s.retriever == "embeddings":
            return RecuperadorEmbeddings(self.s.chroma_dir, sinonimos)
        return RecuperadorTfidf(sinonimos)

    # ---------- ingestão (RF08) ----------
    def carregar(self) -> dict:
        dados = self.s.dados_path
        sinonimos = carregar_sinonimos(dados / "sinonimos.csv")
        exemplos = carregar_exemplos(dados / "perguntas_rotuladas.csv")
        classificador = ClassificadorIntencao(sinonimos)
        classificador.treinar(exemplos)

        trechos = carregar_trechos(
            dados, self.s.chunk_strategy, self.s.chunk_tamanho, self.s.chunk_sobreposicao
        )
        sem_intencao = [t.id for t in trechos if t.intencao is None]
        if sem_intencao:
            log.warning("Trechos sem intenção mapeada (ver MAPA_INTENCOES): %s", sem_intencao)
        recuperador = self._novo_recuperador(sinonimos)
        recuperador.indexar(trechos, textos_extras=[e.pergunta for e in exemplos])

        # troca atômica: requisições em andamento continuam com o modelo anterior
        self.classificador, self.recuperador = classificador, recuperador
        self.n_trechos = len(trechos)

        info = {
            "trechos": len(trechos),
            "estrategia": self.s.chunk_strategy,
            "recuperador": recuperador.nome,
            "sinonimos": len(sinonimos),
            "exemplos_treino": len(exemplos),
            "acuracia_validacao": self.classificador.acuracia_validacao,
            "llm": self.s.groq_model if self.gerador.ativo else None,
        }
        log.info("Base carregada: %s", info)
        return info

    # ---------- fluxo principal ----------
    def responder(self, mensagem: str, historico: list[str] | None = None) -> Decisao:
        inicio = time.perf_counter()
        contexto = (historico or [])[-self.s.turnos_contexto :]
        etapas: dict[str, float] = {}
        d = self._decidir(mensagem.strip(), contexto, etapas)
        d.etapas_ms = etapas
        d.tempo_ms = round((time.perf_counter() - inicio) * 1000, 2)
        return d

    @staticmethod
    @contextmanager
    def _cronometro(etapas: dict[str, float], nome: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            etapas[nome] = round(etapas.get(nome, 0.0) + (time.perf_counter() - t0) * 1000, 2)

    def _fmt(self, modelo: str) -> str:
        return modelo.format(contato=self.s.admin_contato)

    def _decidir(self, msg: str, contexto: list[str], etapas: dict[str, float]) -> Decisao:
        cron = lambda nome: self._cronometro(etapas, nome)  # noqa: E731

        with cron("regras"):
            emergencia = rules.detectar_emergencia(msg)
            humano = None if emergencia else rules.detectar_pedido_humano(msg)
            fora = None if (emergencia or humano) else rules.detectar_fora_escopo(msg)
        # 2. emergência
        if emergencia:
            return Decisao(msg, self._fmt(RESPOSTA_EMERGENCIA), Desfecho.EMERGENCIA, regra=emergencia)
        # pedido explícito de atendimento humano (fluxo do usuário, passo 5)
        if humano:
            return Decisao(msg, self._fmt(RESPOSTA_HUMANO), Desfecho.PEDIDO_HUMANO, regra=humano)
        # encaminhamento 2: fora de escopo por palavra-chave
        if fora:
            return Decisao(msg, self._fmt(RESPOSTA_FORA_ESCOPO), Desfecho.FORA_ESCOPO, regra=fora)

        # 3. classificador (com fallback para o contexto dos últimos turnos — RF02)
        with cron("classificacao"):
            intencao, conf = self.classificador.prever(msg)
            consulta, usou_contexto = msg, False
            if conf < self.s.limiar_classificador and contexto:
                consulta_ctx = " ".join(contexto + [msg])
                intencao_ctx, conf_ctx = self.classificador.prever(consulta_ctx)
                if conf_ctx > conf:
                    intencao, conf, consulta, usou_contexto = intencao_ctx, conf_ctx, consulta_ctx, True

        base = dict(intencao=intencao, confianca=round(conf, 4), usou_contexto=usou_contexto)
        if conf < self.s.limiar_classificador:
            return Decisao(msg, self._fmt(RESPOSTA_BAIXA_CONFIANCA), Desfecho.BAIXA_CONFIANCA, **base)

        # 4. recuperação dentro da intenção
        with cron("recuperacao"):
            resultados = self.recuperador.buscar(consulta, intencao, self.s.top_k)
            if usou_contexto is False and contexto and (
                not resultados or resultados[0].score < self.s.limiar_similaridade
            ):
                # pergunta de acompanhamento ("E no sábado?"): tenta de novo com o contexto
                consulta_ctx = " ".join(contexto + [msg])
                res_ctx = self.recuperador.buscar(consulta_ctx, intencao, self.s.top_k)
                if res_ctx and (not resultados or res_ctx[0].score > resultados[0].score):
                    resultados, consulta, base["usou_contexto"] = res_ctx, consulta_ctx, True

        aprovados = [r for r in resultados if r.score >= self.s.limiar_similaridade]
        base["trechos"] = [self._trecho_log(r) for r in resultados]
        if not aprovados:
            return Decisao(msg, self._fmt(RESPOSTA_SEM_BASE), Desfecho.SEM_BASE, **base)

        # encaminhamento 5: pedido de decisão sobre sanção ou exceção
        if m := rules.detectar_sancao_excecao(msg):
            return Decisao(
                msg, self._fmt(RESPOSTA_SANCAO), Desfecho.SANCAO_EXCECAO, regra=m, **base
            )

        # 5. geração (opcional) ou resposta extrativa — sempre com citação (RF05)
        geracao = None
        if self.gerador.ativo:
            with cron("geracao"):
                geracao = self.gerador.redigir(msg, aprovados, contexto)
        texto = geracao.texto if geracao else None
        llm_usado = texto is not None
        llm = dict(
            llm_status=geracao.status if geracao else "desligado",
            llm_ms=geracao.ms if geracao else None,
            llm_modelo=geracao.modelo if geracao else None,
        )
        if not texto:
            melhor = aprovados[0].trecho
            texto = f"Segundo o Regimento Interno:\n\n> {melhor.texto}"
        citados = aprovados if llm_usado else aprovados[:1]
        refs = "; ".join(dict.fromkeys(r.trecho.referencia for r in citados))
        resposta = f"{texto}\n\n📄 Fonte: {refs}"
        return Decisao(msg, resposta, Desfecho.RESPONDIDO, llm_usado=llm_usado, **llm, **base)

    @staticmethod
    def _trecho_log(r: Resultado) -> dict:
        return {
            "id": r.trecho.id,
            "referencia": r.trecho.referencia,
            "artigos": r.trecho.artigos,
            "score": round(r.score, 4),
        }
