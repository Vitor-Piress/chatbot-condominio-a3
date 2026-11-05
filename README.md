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

- **Backend / Motor de IA:** Python 3.11, FastAPI, Scikit-learn (TF-IDF para classificação).
- **Recuperação de Contexto (RAG):** Supabase com extensão `pgvector` para busca por similaridade (Embeddings).
- **Geração (LLM):** Integração com Groq API (nuvem) / Ollama (local) para redação das respostas.
- **Frontend:** [React com Vite / Open WebUI] para a interface de conversação.

## 📂 Estrutura do Repositório

```text
chatbot-condominio-a3/
│
├── backend/               # Motor de IA, RAG, rotas FastAPI e requirements.txt
├── frontend/              # Interface de chat interativa
├── dados/                 # Base de conhecimento (Markdown) e datasets de teste (CSV)
│
├── .gitignore             # Arquivos ignorados e variáveis de ambiente (.env)
└── docker-compose.yml     # Orquestração dos containers (Opcional)
```
