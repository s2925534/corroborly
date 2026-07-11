# ResearchBoss local API image.
#
# Single-user tool: session state (researchboss/api/auth.py) is an in-memory
# dict, not shared across processes. Do not add `--workers N` (N>1) to the
# CMD below or scale this service to more than one replica -- login sessions
# would randomly fail depending on which worker/replica handled a given
# request, since only the process that issued a session token knows it is
# valid. Exactly one process, one container.

FROM python:3.11-slim

# tesseract/poppler back the optional --ocr conversion fallback (see
# docs/PACKAGING.md). Included here because a shared deployment is a
# reasonable place to make that opt-in feature actually usable -- unlike a
# packaged desktop binary, which cannot bundle these external CLI tools at
# all and must rely on whatever the end user has installed locally.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY researchboss ./researchboss
RUN pip install --no-cache-dir .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["python", "-m", "uvicorn", "researchboss.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
