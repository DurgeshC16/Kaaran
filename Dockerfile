# Kaaran demo server (web + WhatsApp webhook). Synthetic demo data is generated on first start.
# Build:  docker build -t kaaran .
# Run:    docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... -e SARVAM_API_KEY=... kaaran
# Secrets come from the host's environment (never baked into the image). Real data (data/real/) is never copied.
FROM python:3.11-slim

# Chromium renders the one-page PDF; Noto fonts shape Devanagari (Marathi) correctly.
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium fonts-noto-core fonts-noto-ui-core \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY llm_cache ./llm_cache
COPY .env.example ./.env.example
RUN pip install --no-cache-dir -e .

ENV KAARAN_HOST=0.0.0.0 \
    PORT=8000 \
    KAARAN_BROWSER=/usr/bin/chromium \
    KAARAN_BROWSER_NO_SANDBOX=1 \
    KAARAN_LLM_MODE=replay \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "kaaran.api"]
