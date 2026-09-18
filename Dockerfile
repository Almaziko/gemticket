FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# tzdata нужен, чтобы переменная TZ (см. docker-compose, обычно
# Europe/Moscow) реально применялась — без базы часовых поясов libc
# просто игнорирует TZ и время в контейнере остаётся в UTC.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/db /data/uploads

EXPOSE 5000

CMD ["sh", "-c", "gunicorn --preload --bind 0.0.0.0:${PORT:-5000} --workers 3 wsgi:app"]
