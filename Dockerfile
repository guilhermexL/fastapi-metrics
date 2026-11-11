# syntax=docker/dockerfile:1

############################
# Stage 1: builder
############################
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instala dependências em um virtualenv isolado, que será copiado para a imagem final
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

############################
# Stage 2: runtime
############################
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Usuário/grupo sem privilégios, sem home e sem shell de login
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

# Copia apenas o venv pronto (sem pip cache, sem ferramentas de build)
COPY --from=builder /opt/venv /opt/venv

# Código pertence ao root e é somente leitura para o usuário da aplicação
COPY app/ ./app/

USER 10001:10001

EXPOSE 8000

# python:slim não tem curl; usa urllib da stdlib
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

# Forma exec: uvicorn é PID 1 e recebe SIGTERM corretamente
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
