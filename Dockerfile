# Kaaran demo server (web + WhatsApp webhook). Runs locally, on any Docker host, and on Hugging Face Spaces (docs/DEPLOY.md).
# Build:  docker build -t kaaran .
# Run:    docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... -e SARVAM_API_KEY=... kaaran
# Secrets come from the host's environment (never baked into the image). Real data (data/real/) is never copied.
FROM python:3.11-slim

# Chromium renders the one-page PDF; Noto fonts shape Devanagari (Marathi) correctly.
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium fonts-noto-core fonts-noto-ui-core \
 && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces run the container as uid 1000: the app folder must be writable (generated data, PDFs, voice cache).
RUN useradd -m -u 1000 user
WORKDIR /app
COPY --chown=user pyproject.toml README.md ./
COPY --chown=user src ./src
COPY --chown=user llm_cache ./llm_cache
COPY --chown=user .env.example ./.env.example
COPY --chown=user published ./published
RUN pip install --no-cache-dir -e . && chown -R user /app
USER user
ENV HOME=/home/user \
    KAARAN_HOST=0.0.0.0 \
    PORT=8000 \
    KAARAN_BROWSER=/usr/bin/chromium \
    KAARAN_BROWSER_NO_SANDBOX=1 \
    KAARAN_LLM_MODE=replay \
    PYTHONUNBUFFERED=1

# SYNTHETIC demo districts, generated at build time (deterministic, no LLM) so the first visitor does not wait.
RUN python -m kaaran.synth3 --seed 42 --out data/synthetic/block_demo \
 && python -m kaaran.synth3 --seed 7 --names fictional --out data/synthetic/block_demo_fictional \
 && python -m kaaran.synth --seed 42 --out data/synthetic/demo \
 && python -m kaaran.synth --seed 7 --names fictional --out data/synthetic/demo_fictional

# Briefs and one-page PDFs of the main demo dataset, made now so a small (0.1 CPU) host serves them instantly.
RUN python -m kaaran.warm --dataset blocks

EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '8000'))"
CMD ["python", "-m", "kaaran.api"]
