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
│   │   ├── db.py              # Log de decisões no banco (RF07)
│   │   ├── observability.py   # Logs estruturados: stdout + logs/app.log + logs/decisoes.jsonl
│   │   ├── monitoring.py      # Métricas agregadas (API e análise offline)
│   │   ├── static/painel.html # Painel de monitoramento (/painel)
│   │   └── pipeline/          # preprocess, rules, features, classifier, knowledge, retriever, generator, engine
│   ├── scripts/
│   │   ├── avaliar.py         # Roda os 24 casos de teste e calcula as métricas do PRD
│   │   ├── analisar_logs.py   # Resume/exporta logs/decisoes.jsonl
│   │   └── ver_modelos.py     # Lista os modelos liberados na Groq
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── dados/
│   ├── regimento.md           # Base de conhecimento (## Capítulo / Art. N)
│   ├── perguntas_rotuladas.csv # 80 perguntas (20 por intenção) para treino/validação
│   ├── sinonimos.csv          # Expansão de consulta (ex.: barulho -> silêncio sossego)
│   └── casos_teste.csv        # 24 casos de teste (seção 6 do PRD), nunca usados no treino
├── docker/postgres/           # Script que cria o banco do backend
├── logs/                      # Gerado em execução (fora do Git)
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
| `RETRIEVER` | `tfidf` (padrão) ou `embeddings` (requer `INSTALL_EMBEDDINGS=true` no build) |
| `LOG_LEVEL` / `LOG_FORMAT` | Nível de log e formato do stdout (`texto` ou `json`) |
| `LOG_DIR` | Pasta dos arquivos de log (vazio desliga) |
| `LOG_MENSAGENS` | `false` omite o texto das perguntas/respostas nos arquivos |

## 📊 Logs e monitoramento

Cada mensagem gera uma **decisão** com intenção, confiança, trechos e scores, desfecho, uso do LLM e tempo de cada etapa. Ela é registrada em três lugares:

| Onde | Formato | Para quê |
| --- | --- | --- |
| stdout (`docker compose logs -f backend`) | texto legível ou JSON (`LOG_FORMAT`) | Acompanhar em tempo real |
| `logs/app.log` | JSON por linha, com rotação (10 MB × 5) | Todos os eventos: HTTP, decisões, chamadas à Groq, erros |
| `logs/decisoes.jsonl` | Uma decisão completa por linha (50 MB × 10) | Análise posterior (script, pandas, jq) |
| Tabela `decisoes` no Postgres | SQL | Painel e endpoints de métricas |

Toda requisição recebe um `request_id` (devolvido no header `X-Request-ID`), presente em todas as linhas de log dela. Do Open WebUI, o backend recebe e registra apenas os **ids** do usuário e do chat, nunca nome ou e-mail.

**Painel:** http://localhost:8000/painel (informe a `BACKEND_API_KEY`). Mostra volume por hora, desfechos, intenções, latência por etapa, artigos mais citados, as **lacunas** (perguntas sem base ou com baixa confiança, candidatas a novos artigos/sinônimos/treino) e as últimas decisões.

**Endpoints** (com `Authorization: Bearer $BACKEND_API_KEY`):

```bash
curl -s "localhost:8000/admin/metricas?horas=24" -H "Authorization: Bearer $BACKEND_API_KEY"
curl -s "localhost:8000/admin/decisoes?desfecho=sem_base&limite=20" -H "Authorization: Bearer $BACKEND_API_KEY"
```

**Análise offline dos arquivos:**

```bash
cd backend
python -m scripts.analisar_logs --arquivo ../logs/decisoes.jsonl --horas 168 --csv decisoes.csv
# ou com jq: perguntas que ficaram sem base
jq -r 'select(.desfecho=="sem_base") | .mensagem' ../logs/decisoes.jsonl | sort | uniq -c | sort -rn
```

## 🧪 Avaliação (seção 6 do PRD)

```bash
cd backend
python -m scripts.avaliar                 # 24 casos com a configuração atual
python -m scripts.avaliar --comparar      # TF-IDF x embeddings, artigo x 1000/200 caracteres
python -m scripts.avaliar --llm           # com a Groq (precisa de GROQ_API_KEY)
pytest                                    # testes automatizados

# dentro do Docker (a pasta dados é somente leitura no contêiner):
docker compose exec backend python -m scripts.avaliar --saida /app/logs/avaliacao
```

Os resultados caso a caso (planilha) e as métricas (JSON) vão para `dados/resultados/`.

### Consultar o log de decisões

```bash
docker compose exec db psql -U condominio -d chatbot \
  -c "select criado_em, mensagem, desfecho, intencao, confianca, tempo_ms from decisoes order by id desc limit 20;"
```

