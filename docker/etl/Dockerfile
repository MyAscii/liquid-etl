# liquid-etl parser image. Build context is the repo root.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the package (with the Postgres extra) so `python -m liquidetl.pipeline` works.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[postgres]"

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "liquidetl.pipeline"]
