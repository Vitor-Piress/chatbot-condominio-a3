FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements-embeddings.txt ./
RUN pip install -r requirements.txt

# docker compose build --build-arg INSTALL_EMBEDDINGS=true  (ou INSTALL_EMBEDDINGS=true no .env)
ARG INSTALL_EMBEDDINGS=false
RUN if [ "$INSTALL_EMBEDDINGS" = "true" ]; then \
      pip install -r requirements-embeddings.txt --extra-index-url https://download.pytorch.org/whl/cpu; \
    fi

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
