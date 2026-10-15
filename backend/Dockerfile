# Personal Teacher Assistant API / worker image.
# Build context: ./backend   (secrets are NEVER copied in; they come from env at runtime)

############################
# Stage 1: build wheels/venv
############################
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt ./
# gunicorn is the production process manager; installed here so the image works
# even if requirements.txt does not pin it.
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install "gunicorn>=22" "uvicorn[standard]>=0.30"

############################
# Stage 2: runtime
############################
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000 \
    WEB_CONCURRENCY=2

# ffmpeg: slide+audio -> MP4 rendering; Noto fonts: English + Tamil slide text + emoji scenes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-noto-core \
        fonts-noto-ui-core \
        fonts-noto-color-emoji \
        libfribidi0 \
        libraqm0 \
        libpq5 \
        tini \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --create-home --home-dir /home/app app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app . .
COPY --chown=app:app docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh \
    && mkdir -p /app/media \
    && chown -R app:app /app/media

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=4).status == 200 else 1)"

ENTRYPOINT ["tini", "--", "docker-entrypoint.sh"]
CMD ["sh", "-c", "exec gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY} --access-logfile - --timeout 120"]
