FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

RUN pip install --no-cache-dir -e "."
RUN playwright install chromium --with-deps

CMD ["python", "-m", "recipe.bot.main"]
