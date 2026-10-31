FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml requirements.txt requirements-dev.txt ./
COPY edge ./edge
COPY server ./server
COPY shared ./shared
COPY scripts ./scripts
RUN python -m pip install --no-cache-dir -e ".[server,vision]"

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]

