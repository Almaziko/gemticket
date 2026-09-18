# GemTicket

Тикет-трекер для работы с клиентами. Flask + SQLAlchemy + SQLite, серверный рендеринг на Jinja2, Bootstrap 5, без SPA.

## Возможности

- Вход по единственному полю — паролю (без логина); пароль однозначно определяет учётку.
- Две роли: постановщик и админ (среди админов — один суперадмин).
- Пароли шифруются обратимо (`cryptography.Fernet`) и обязаны быть уникальны во всей системе.
- Тикеты с WYSIWYG-описанием, дедлайном, трекером и статусом из редактируемых в админке справочников; история изменений тикета.
- Комментарии с вложениями (ограничение расширений и размера файла — настраивается в админке).
- Финальные статусы (например, «Готов»/«Отменён») — постановщик не может писать в такой тикет.
- Уведомления: email по редактируемым в админке шаблонам (в фоновом потоке) + колокольчик в интерфейсе; отдельное письмо суперадминам при просрочке дедлайна.
- Админка: постановщики, админы, справочники статусов/трекеров, файлы, шаблоны писем, настройки SMTP.

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

## Тесты

```bash
pip install -r requirements-dev.txt
pytest
```

Тесты гоняют полный сценарий через тестовый Flask-клиент на изолированной временной SQLite-базе (своя на каждый тест): логин, создание тикетов и комментариев (включая регрессионные проверки на потерю введённого текста при ошибках валидации), права доступа, финальные статусы, справочники, шаблоны писем и миграцию на смоделированной «старой» базе. GitHub Actions (`.github/workflows/docker.yml`) прогоняет их при каждом пуше в `master`/`main` — сборка и публикация Docker-образа запускаются только если все тесты прошли.

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

CI (`.github/workflows/docker.yml`) при пуше в `master`/`main` собирает Docker-образ и пушит его в Docker Hub как `almaziko/gemticket:latest`. Деплой на сервер пайплайн не делает — образ разворачивается стеком в **Portainer** (или напрямую через `docker compose up` — оба варианта равноправны).

Ниже — обезличенный шаблон `docker-compose.yml`. Секреты (`SECRET_KEY`, `FERNET_KEY`, `ADMIN_PASSWORD`) в репозиторий не кладутся: в шаблоне это `${ПЕРЕМЕННЫЕ}` — Portainer подставит в них значения из раздела «Environment variables» стека (см. пошагово ниже); при запуске через голый `docker compose` эти же переменные нужно объявить в `.env`-файле рядом с `docker-compose.yml` или экспортировать в окружении перед `up`.

```yaml
services:
  gemticket:
    image: almaziko/gemticket:latest
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      SECRET_KEY: ${SECRET_KEY}
      FERNET_KEY: ${FERNET_KEY}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}
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

1. Заранее сгенерируйте `FERNET_KEY` и произвольный `SECRET_KEY` (команда выше) и придумайте `ADMIN_PASSWORD` для первого суперадмина.
2. В Portainer: **Stacks → Add stack**, дайте имя (например, `gemticket`).
3. В поле **Web editor** вставьте `docker-compose.yml` из блока выше как есть — с `${SECRET_KEY}` и т.д., ничего не редактируя.
4. Ниже, в разделе **Environment variables**, добавьте три переменные (по кнопке *Add an environment variable*, каждая — имя/значение отдельно, без кавычек):
   - `SECRET_KEY` = сгенерированная строка
   - `FERNET_KEY` = ключ из `Fernet.generate_key()`
   - `ADMIN_PASSWORD` = пароль первого суперадмина
5. При желании поправьте `BASE_URL` прямо в тексте compose (на реальный домен/IP, под которым будет открываться приложение) — это не секрет, его можно вписать напрямую в YAML.
6. **Deploy the stack**. Portainer подставит переменные в `${...}` и поднимет контейнер.
7. Проверьте логи контейнера (Containers → gemticket → Logs) — должно быть видно, что gunicorn стартовал без ошибок.
8. Откройте `http://<host>:5000` (или порт, который вы указали в `ports:`), войдите паролем из `ADMIN_PASSWORD` — это и есть суперадмин.

Обновление образа: **Stacks → gemticket → Pull and redeploy** (или Re-deploy после ручного pull) — данные не потеряются, они лежат в volume’ах `gemticket_db`/`gemticket_uploads`, а не в самом контейнере.

### Вариант 2 — `docker compose` напрямую

Создайте рядом с `docker-compose.yml` файл `.env` с теми же тремя переменными (`SECRET_KEY`, `FERNET_KEY`, `ADMIN_PASSWORD`), затем:

```bash
docker compose up -d
```
