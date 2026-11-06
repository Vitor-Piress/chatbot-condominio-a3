#!/bin/bash
# Cria o banco do backend (log de decisões) ao lado do banco do Open WebUI.
# Roda só na primeira inicialização do volume pgdata.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE "${POSTGRES_CHATBOT_DB:-chatbot}";
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${POSTGRES_CHATBOT_DB:-chatbot}" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL
