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

    added_group = False
    if not _has_column('statuses', 'group'):
        db.session.execute(text('ALTER TABLE statuses ADD COLUMN "group" INTEGER NOT NULL DEFAULT 1'))
        added_group = True

    if not _has_column('tickets', 'priority'):
        # 2 = средний приоритет (см. models.PRIORITY_MEDIUM) — разумный
        # дефолт для уже существующих тикетов.
        db.session.execute(text('ALTER TABLE tickets ADD COLUMN priority INTEGER NOT NULL DEFAULT 2'))

    added_closed_at = False
    if not _has_column('tickets', 'closed_at'):
        db.session.execute(text('ALTER TABLE tickets ADD COLUMN closed_at DATETIME'))
        added_closed_at = True

    if not _has_column('status_groups', 'sort_mode'):
        db.session.execute(text(
            "ALTER TABLE status_groups ADD COLUMN sort_mode VARCHAR(20) NOT NULL DEFAULT 'priority'"
        ))

    if not _has_column('settings', 'site_name'):
        db.session.execute(text(
            "ALTER TABLE settings ADD COLUMN site_name VARCHAR(120) NOT NULL DEFAULT 'GemTicket'"
        ))

    if not _has_column('settings', 'favicon_filename'):
        db.session.execute(text('ALTER TABLE settings ADD COLUMN favicon_filename VARCHAR(255)'))

    if not _has_column('statuses', 'auto_advance_enabled'):
        db.session.execute(text('ALTER TABLE statuses ADD COLUMN auto_advance_enabled BOOLEAN NOT NULL DEFAULT 0'))

    if not _has_column('statuses', 'auto_advance_button_text'):
        db.session.execute(text('ALTER TABLE statuses ADD COLUMN auto_advance_button_text VARCHAR(80)'))

    if not _has_column('statuses', 'auto_revert_enabled'):
        db.session.execute(text('ALTER TABLE statuses ADD COLUMN auto_revert_enabled BOOLEAN NOT NULL DEFAULT 0'))

    if not _has_column('statuses', 'auto_revert_button_text'):
        db.session.execute(text('ALTER TABLE statuses ADD COLUMN auto_revert_button_text VARCHAR(80)'))

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

    if added_group:
        # Все статусы попадают в колонку по умолчанию (DEFAULT 1 выше), но
        # чтобы сразу сохранить привычное разделение "активные/финальные" —
        # раскидываем уже существующие финальные статусы во 2-ю группу.
        # Дальше группировка полностью редактируется в админке.
        db.session.execute(text('UPDATE statuses SET "group" = 2 WHERE is_final = 1'))
        db.session.commit()

    if added_closed_at:
        # Точной даты закрытия для уже накопленных тикетов у нас нет —
        # берём updated_at как разумное приближение для тех, что уже сейчас
        # в финальном статусе. Дальше closed_at ведётся точно, при смене
        # статуса (см. change_status в tickets/routes.py).
        db.session.execute(text(
            "UPDATE tickets SET closed_at = updated_at "
            "WHERE status_id IN (SELECT id FROM statuses WHERE is_final = 1)"
        ))
        db.session.commit()
