# Dockerfile pro MCP Server Volby 2026 v ČR
FROM python:3.12-slim AS builder

WORKDIR /app

# Instalace buildovacích utilit
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalace Python závislostí
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# Finální lightweight runtime obraz
FROM python:3.12-slim AS runtime

WORKDIR /app

# Instalace curl pro healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Vytvoření neprivilegovaného uživatele
RUN useradd -m -u 1000 appuser

# Zkopírování nainstalovaných balíčků
COPY --from=builder /install /usr/local

# Zkopírování zdrojových kódů
COPY src /app/src
COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md

# Vytvoření datového adresáře a nastavení práv
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8088 \
    HOST=0.0.0.0

EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["python", "-m", "src.server"]
