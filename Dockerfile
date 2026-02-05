FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY polymarket_bot/ ./polymarket_bot/

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "polymarket_bot.bot"]
CMD ["--help"]
