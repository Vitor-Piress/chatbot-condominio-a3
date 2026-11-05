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

## 🚀 Como rodar: passo a passo

### 1. Pré-requisitos

- **Docker** com Compose v2 (`docker compose version`). No Windows, use o **WSL 2** com Docker Desktop (integração com a distro ativada em *Settings → Resources → WSL integration*) ou o Docker Engine instalado dentro da distro.
- **Git**.
- Opcional: **Python 3.11** para rodar sem Docker, avaliar e testar.
- Opcional: uma chave gratuita da **Groq** (https://console.groq.com) para a geração com LLM. Sem ela, o bot responde citando o trecho do regimento.

> ⚠️ **No WSL, clone o repositório dentro do sistema de arquivos Linux** (ex.: `~/projetos`), e não em `/mnt/c/...`. Fica muito mais rápido, e o script de inicialização do banco não corre o risco de virar CRLF.

### 2. Clonar e entrar na branch

```bash
git clone https://github.com/Vitor-Piress/chatbot-condominio-a3.git
cd chatbot-condominio-a3
git checkout feat/poc
```

### 3. Criar o `.env`

```bash
cp .env.example .env
```

Troque **pelo menos** estes valores (gere segredos com `openssl rand -hex 32`):

| Variável | O que colocar |
| --- | --- |
| `POSTGRES_PASSWORD` | uma senha qualquer |
| `BACKEND_API_KEY` | segredo compartilhado entre Open WebUI e backend; também é a senha do painel |
| `WEBUI_SECRET_KEY` | outro segredo |
| `GROQ_API_KEY` | opcional; deixe vazio para o modo sem LLM |

Atalho que já gera tudo:

```bash
sed -i -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 16)/" \
       -e "s/^BACKEND_API_KEY=.*/BACKEND_API_KEY=$(openssl rand -hex 32)/" \
       -e "s/^WEBUI_SECRET_KEY=.*/WEBUI_SECRET_KEY=$(openssl rand -hex 32)/" .env
```

> Defina as senhas **antes** da primeira subida. O Postgres e o Open WebUI gravam a configuração no primeiro start (ver *Problemas comuns*).

### 4. Subir os contêineres

```bash
docker compose up -d --build
docker compose ps            # db, backend e openwebui devem ficar "healthy"/"running"
docker compose logs -f backend
```

A **primeira subida do Open WebUI leva alguns minutos**, porque ele baixa modelos internos. Acompanhe com `docker compose logs -f openwebui`.

### 5. Conferir o backend

```bash
curl -s localhost:8000/health
# {"status":"ok","banco":"ok","base":{"trechos":7,"exemplos_treino":80,"acuracia_validacao":0.96,...}}
```

A documentação interativa da API fica em http://localhost:8000/docs.

### 6. Configurar o Open WebUI

1. Abra http://localhost:3000 e **crie a primeira conta**. Ela vira administradora.
2. No seletor de modelos do chat, escolha **`assistente-acacias`**.
3. Novos moradores que se cadastrarem ficam como **pendentes**. O admin aprova em *Painel de administração → Usuários* (RF09).

### 7. Testar no chat

| Pergunta | Esperado |
| --- | --- |
| Qual o horário de silêncio? | Responde citando o Art. 1 |
| Quanto custa reservar o salão? | Art. 3 |
| Em que horário posso fazer obra? → *E no sábado?* | Art. 5; a segunda usa o contexto da primeira |
| até que horas pode fazer barulho | Art. 1 (reformulação via sinônimos) |
| qual o valor do boleto de agosto? | Encaminha: fora de escopo |
| tem vazamento de gás no bloco B | Resposta fixa de emergência (190/192/193) |
| qual a cor do prédio? | Pede para reformular (baixa confiança) |

### 8. Acompanhar o funcionamento

- Painel: http://localhost:8000/painel (cole a `BACKEND_API_KEY`).
- Logs ao vivo: `docker compose logs -f backend`.
- Arquivos: `logs/app.log` e `logs/decisoes.jsonl` (ver *Logs e monitoramento*).

### 9. Parar, reiniciar e zerar

```bash
docker compose down          # para, mas mantém banco e contas
docker compose up -d         # sobe de novo
docker compose down -v       # ⚠️ apaga TUDO: banco, contas do Open WebUI e decisões
```

### Sem Docker (Python 3.11)

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Sem `DATABASE_URL` no `.env`, o log vai para `backend/decisoes.db` (SQLite) e os arquivos para `backend/logs/`. Nesse modo não há Open WebUI: use `/docs`, `curl` ou o painel.

### Problemas comuns

| Sintoma | Causa e solução |
| --- | --- |
| `port is already allocated` | Porta 3000, 8000 ou 5432 em uso. Mude `OPENWEBUI_PORT`, `BACKEND_PORT` ou `POSTGRES_PORT` no `.env`. |
| Backend reinicia com erro de conexão ou `database "chatbot" does not exist` | O volume do banco foi criado antes (ou com outra senha), e o script de `docker/postgres/` só roda na primeira vez. Rode `docker compose down -v` e suba de novo. |
| `/docker-entrypoint-initdb.d/...sh: bad interpreter` | O script ficou com CRLF (clone feito no Windows). Rode `git config core.autocrlf input`, clone de novo dentro do WSL e faça `docker compose down -v`. |
| Modelo `assistente-acacias` não aparece no Open WebUI | O Open WebUI guarda a conexão no banco no primeiro start, então mudar `BACKEND_API_KEY` depois não tem efeito. Corrija em *Painel de administração → Configurações → Conexões* (URL `http://backend:8000/v1` e a chave) ou zere com `down -v`. |
| Respostas sempre no modo extrativo, mesmo com `GROQ_API_KEY` | Veja `docker compose logs backend \| grep -i groq`. O modelo de `GROQ_MODEL` pode não estar liberado: liste com `docker compose exec backend python scripts/ver_modelos.py`. |
| Painel diz "Chave inválida" | Use exatamente o valor de `BACKEND_API_KEY` do `.env`. |
| Sem permissão para apagar `logs/` | Os arquivos são criados pelo contêiner como root: `sudo rm -rf logs`. |

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

## ⚠️ Pontos de atenção

- **Limiares calibrados com os casos de teste.** `LIMIAR_CLASSIFICADOR=0.45` e `LIMIAR_SIMILARIDADE=0.08` foram escolhidos olhando os scores, inclusive dos 24 casos de teste. O PRD pede calibrar no conjunto de **validação**. Recalibrar antes da entrega (ver *O que falta fazer*).
- **Hit@3 ainda não discrimina.** Cada intenção tem no máximo 2 artigos, então o artigo certo sempre fica entre os 3 primeiros. A métrica só passa a dizer algo quando a base crescer.
- **Falha conhecida:** "Posso fazer churrasco na sexta?" é respondida com o Art. 5 (obras), porque "sexta" casa com "segunda a sexta-feira". É uma boa candidata para a análise de falhas.
- **Piscina em capítulo diferente do PRD.** O Art. 4 (piscina) está no capítulo de Reservas, mas o PRD trata "piscina à noite" como convivência. A busca acontece só dentro da intenção, por isso as perguntas de piscina estão rotuladas como `reservas`. A equipe precisa decidir e alinhar regimento e CSV.
- **Modelo da Groq não confirmado.** O padrão é `qwen/qwen3.8-27b`. Confira se está disponível com `scripts/ver_modelos.py` e registre nome e data de uso (requisito do PRD). Modelos com raciocínio podem devolver `<think>…</think>`, que o backend remove.
- **Modo LLM e embeddings não testados de ponta a ponta.** Os dois estão implementados, mas só o modo extrativo com TF-IDF foi validado com os testes automatizados.
- **Open WebUI na tag `main`.** Para a apresentação, fixe uma versão em `OPENWEBUI_TAG` para evitar surpresas de atualização.
- **Contexto do endpoint `/chat` fica em memória.** Ele se perde ao reiniciar o backend. No Open WebUI isso não acontece, porque o histórico vem a cada mensagem.
- **Privacidade nos logs.** Os arquivos guardam o texto das perguntas. Com dados reais, use `LOG_MENSAGENS=false`. Do Open WebUI só são registrados ids, nunca nome ou e-mail.
- **Migração de banco mínima.** O backend só adiciona colunas novas na tabela `decisoes`. Mudanças maiores exigem `docker compose down -v` ou uma ferramenta como Alembic.

## ✅ O que falta fazer

**Dados e base de conhecimento**
- [ ] Decidir onde fica a piscina (convivência ou reservas) e alinhar `regimento.md` e `perguntas_rotuladas.csv`
- [ ] Ampliar o regimento com mais artigos por capítulo (opcional: um arquivo `.md` por capítulo, como no PRD; a ingestão já lê todos os `dados/*.md`)
- [ ] Revisar `perguntas_rotuladas.csv` e trocar a origem `simulada` por perguntas da equipe quando houver
- [ ] Criar um conjunto de validação com o artigo esperado e recalibrar os limiares nele (não no de teste)
- [ ] Versionar a base com a tag `dados-v1` e registrar a data das alterações

**Técnica e experimentos (seção 6)**
- [ ] Rodar TF-IDF x embeddings: `INSTALL_EMBEDDINGS=true` no `.env`, `docker compose build backend` e `python -m scripts.avaliar --comparar`
- [ ] Rodar com LLM x sem LLM (`--llm`) e verificar alucinação manualmente, resposta por resposta
- [ ] Desenhar o fluxograma das 6 etapas com as saídas de encaminhamento

**Testes e avaliação**
- [ ] Gerar a planilha final dos 24 casos (`dados/resultados/*.csv`) e anexar ao relatório
- [ ] Escrever a análise das 3 falhas, com causa (sugestões: churrasco/"sexta", pergunta com gíria, limiar)
- [ ] Medir o tempo de resposta no ambiente da demo (mediana e p90 no painel ou no `avaliar.py`)

**Interface e demonstração**
- [ ] Fixar a versão do Open WebUI e personalizar nome e mensagem inicial
- [ ] Cadastrar usuários de teste e demonstrar a aprovação (RF09)
- [ ] Escrever o roteiro da demonstração e gravar o vídeo de backup

**Documentação**
- [ ] Citar a política de retenção de dados da Groq (documentação vigente) e o modelo usado, com data
- [ ] Preencher a tabela de papéis da equipe e a declaração de uso de IA generativa (PRD, seções 7 e 9)
- [ ] Relatório final e apresentação

