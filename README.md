# 🏢 Chatbot RAG - Gestão de Condomínios (POC)

Repositório oficial do Projeto Integrador (Avaliação A3) da disciplina de Inteligência Artificial.

Este projeto é uma Prova de Conceito (POC) de um assistente virtual inteligente projetado para sanar dúvidas repetitivas de moradores de um condomínio fictício (Residencial Jardim das Acácias). O chatbot utiliza a arquitetura **RAG (Retrieval-Augmented Generation)** para garantir que as respostas sejam baseadas **exclusivamente** nos documentos oficiais do condomínio (Regimento Interno e Convenção), eliminando alucinações e invenções por parte da Inteligência Artificial.

## 🎯 Objetivos e Escopo

O bot é treinado para classificar intenções e buscar o contexto exato na base de dados antes de formular a resposta. Ele cobre 4 áreas principais:

- **Reservas de áreas comuns** (Salão de festas, quiosques, horários).
- **Regras de convivência** (Lei do silêncio, regras para pets, uso da piscina).
- **Mudanças e obras** (Agendamentos, horários permitidos).
- **Garagem e serviços** (Vagas de visitantes, coleta de lixo).

**Mecanismos de Segurança (Fallback):**
Mensagens fora de escopo (ex: cobranças de boletos), sinais de emergência (ex: vazamento de gás) ou regras não encontradas no banco de dados não são respondidas pela IA, sendo automaticamente encaminhadas com os contatos da administração local.

## 🛠️ Arquitetura e Tecnologias

O projeto foi estruturado em um monorepo, separando as responsabilidades de interface, motor de IA e base de conhecimento.

- **Backend / Motor de IA:** Python 3.11, FastAPI, scikit-learn (TF-IDF + regressão logística para intenção; similaridade do cosseno para recuperação).
- **Banco:** PostgreSQL (imagem com `pgvector`), usado pelo Open WebUI e pelo log de decisões do backend. Sem Docker, o backend usa SQLite.
- **Geração (LLM, opcional):** Groq API. Sem chave, o bot devolve o trecho citado (modo extrativo).
- **Frontend:** Open WebUI, que enxerga o backend como um "modelo" compatível com OpenAI.

Fluxo: emergência (regex) → pedido de atendimento → fora de escopo (palavras-chave) → classificador de intenção → recuperação dentro da intenção → sanção/exceção → Groq ou trecho citado. Toda decisão é registrada na tabela `decisoes`.

## 📂 Estrutura do Repositório

```text
chatbot-condominio-a3/
│
├── backend/
│   ├── app/
│   │   ├── main.py            # Rotas FastAPI (/chat, /v1/chat/completions, /admin/reingest)
│   │   ├── config.py          # Configuração lida do .env
│   │   ├── db.py              # Log de decisões (RF07)
│   │   └── pipeline/          # preprocess, rules, classifier, knowledge, retriever, generator, engine
│   ├── scripts/               # Utilitários (listar modelos da Groq etc.)
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── dados/
│   ├── regimento.md           # Base de conhecimento (## Capítulo / Art. N)
│   └── perguntas_rotuladas.csv
├── docker/postgres/           # Script que cria o banco do backend
├── .env.example               # Modelo de configuração (copie para .env)
└── docker-compose.yml         # db + backend + Open WebUI
```

## 🚀 Como rodar

### Com Docker (recomendado)

```bash
cp .env.example .env
# edite o .env: troque senhas/segredos (openssl rand -hex 32) e, se quiser LLM, preencha GROQ_API_KEY
docker compose up -d --build
```

- Open WebUI: http://localhost:3000. **O primeiro usuário cadastrado vira administrador.** Os próximos ficam como "pendente" até o admin aprovar em *Painel de administração → Usuários* (RF09).
- Backend: http://localhost:8000/docs
- A primeira subida do Open WebUI demora alguns minutos.

No chat, escolha o modelo `assistente-acacias`.

### Sem Docker (Python 3.11)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Sem `DATABASE_URL` no `.env`, o log vai para `backend/decisoes.db` (SQLite).

### Exemplos de chamada

```bash
curl -s localhost:8000/chat -H "Authorization: Bearer $BACKEND_API_KEY" \
  -H "Content-Type: application/json" -d '{"mensagem": "Qual o horário de silêncio?"}'

# depois de alterar dados/*.md ou o CSV (RF08):
curl -s -X POST localhost:8000/admin/reingest -H "Authorization: Bearer $BACKEND_API_KEY"
```

### Configuração principal (.env)

| Variável | Para que serve |
| --- | --- |
| `CHUNK_STRATEGY` | `artigo` ou `caracteres` (1000 com 200 de sobreposição) |
| `LIMIAR_CLASSIFICADOR` | Confiança mínima da intenção; abaixo disso, pede reformulação |
| `LIMIAR_SIMILARIDADE` | Similaridade mínima do trecho; abaixo disso, encaminha |
| `GROQ_API_KEY` / `GROQ_MODEL` | Liga a geração. Liste os modelos com `python backend/scripts/ver_modelos.py` |
| `ADMIN_CONTATO` | Contato exibido nos encaminhamentos |

### Consultar o log de decisões

```bash
docker compose exec db psql -U condominio -d chatbot \
  -c "select criado_em, mensagem, desfecho, intencao, confianca, tempo_ms from decisoes order by id desc limit 20;"
```

