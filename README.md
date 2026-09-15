# GemTicket

Тикет-трекер для работы с клиентами. Flask + SQLAlchemy + SQLite, серверный рендеринг на Jinja2, Bootstrap 5, без SPA.

## Возможности

- Вход по единственному полю — паролю (без логина); пароль однозначно определяет учётку.
- Две роли: клиент и админ (среди админов — один суперадмин).
- Пароли шифруются обратимо (`cryptography.Fernet`) и обязаны быть уникальны во всей системе.
- Тикеты с описанием, дедлайном, трекером и статусом из редактируемых в админке справочников.
- Комментарии с вложениями (файлы и картинки), вставка изображений из буфера обмена (Ctrl+V).
- Уведомления: email (в фоновом потоке) + колокольчик в интерфейсе.
- Админка: клиенты, админы, справочники статусов/трекеров, файлы, настройки SMTP.

## Локальный запуск (разработка)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# заполните .env, сгенерировав FERNET_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

python wsgi.py
```

Приложение поднимется на `http://localhost:5000`. При первом старте, если в базе нет ни одного админа, создаётся суперадмин с паролем из `ADMIN_PASSWORD`.

## Переменные окружения

| Переменная | Назначение |
|---|---|
| `SECRET_KEY` | Ключ подписи Flask-сессий |
| `FERNET_KEY` | Ключ обратимого шифрования паролей (`Fernet.generate_key()`) |
| `ADMIN_PASSWORD` | Пароль первого суперадмина (используется только при пустой базе) |
| `BASE_URL` | Базовый URL для ссылок в письмах |
| `DATABASE` | Путь к файлу SQLite |
| `UPLOAD_DIR` | Директория для вложений |
| `PORT` | Порт приложения (по умолчанию 5000) |

SMTP и лимит размера загружаемого файла настраиваются не через env, а в самой админке (раздел «Настройки»).

## Развёртывание

CI (`.github/workflows/docker.yml`) при пуше в `master`/`main` собирает Docker-образ и пушит его в Docker Hub как `almaziko/ticket-tracker:latest`. Деплой на сервер пайплайн не делает — образ разворачивается стеком в **Portainer** (или напрямую через `docker compose up` — оба варианта равноправны).

Ниже — обезличенный шаблон `docker-compose.yml`. Секреты (`SECRET_KEY`, `FERNET_KEY`, `ADMIN_PASSWORD`) в репозиторий не кладутся — подставьте свои значения при создании стека в Portainer (переменные стека) либо впишите их прямо в файл перед `docker compose up`.

```yaml
services:
  gemticket:
    image: almaziko/ticket-tracker:latest
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      SECRET_KEY: <секретный-случайный-ключ>
      FERNET_KEY: <ключ-fernet-см-README>
      ADMIN_PASSWORD: <пароль-первого-суперадмина>
      TZ: Europe/Moscow
      PORT: 5000
      BASE_URL: https://tickets.example.com
      DATABASE: /data/db/gemticket.db
      UPLOAD_DIR: /data/uploads
    volumes:
      - gemticket_db:/data/db
      - gemticket_uploads:/data/uploads
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  gemticket_db:
  gemticket_uploads:
```

`FERNET_KEY` сгенерировать заранее (один раз, и дальше не менять — иначе расшифровка ранее сохранённых паролей сломается):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Оба volume (`gemticket_db` и `gemticket_uploads`) переживают пересоздание контейнера — база SQLite и загруженные файлы не теряются при обновлении образа.

### Вариант 1 — стек в Portainer

Stacks → Add stack → вставить содержимое `docker-compose.yml` выше → задать переменные секретов в разделе Environment variables стека → Deploy.

### Вариант 2 — `docker compose` напрямую

```bash
docker compose up -d
```
