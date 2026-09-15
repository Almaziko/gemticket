"""
Лёгкие ALTER TABLE для уже развёрнутых баз.

db.create_all() создаёт только отсутствующие таблицы — он не добавляет новые
столбцы в уже существующие таблицы. Раз schema развивается без Alembic (по
задумке — простой проект), при добавлении новых колонок к существующим
моделям нужно вручную "догнать" уже накопленные боевые базы. Функция ниже
идемпотентна: проверяет PRAGMA table_info и добавляет столбец, только если
его ещё нет.
"""
from sqlalchemy import text

from .extensions import db


def _has_column(table, column):
    rows = db.session.execute(text(f'PRAGMA table_info({table})')).fetchall()
    return any(row[1] == column for row in rows)


def run_light_migrations():
    added_is_final = False

    if not _has_column('statuses', 'is_final'):
        db.session.execute(text('ALTER TABLE statuses ADD COLUMN is_final BOOLEAN NOT NULL DEFAULT 0'))
        added_is_final = True

    if not _has_column('settings', 'allowed_extensions'):
        db.session.execute(text(
            "ALTER TABLE settings ADD COLUMN allowed_extensions VARCHAR(500) "
            "NOT NULL DEFAULT 'zip,xlsx,xls,csv,docx,doc,pdf,jpeg,png,jpg'"
        ))

    if not _has_column('tickets', 'overdue_notified'):
        db.session.execute(text('ALTER TABLE tickets ADD COLUMN overdue_notified BOOLEAN NOT NULL DEFAULT 0'))

    db.session.commit()

    if added_is_final:
        # Разумный дефолт для уже накопленных статусов из стартового сидинга:
        # "Готов" и "Отменён" помечаем финальными. Дальше это редактируется
        # в админке, поэтому делаем это только один раз — сразу после того,
        # как колонка была добавлена этой же миграцией.
        db.session.execute(text(
            "UPDATE statuses SET is_final = 1 WHERE name IN ('Готов', 'Отменён')"
        ))
        db.session.commit()
