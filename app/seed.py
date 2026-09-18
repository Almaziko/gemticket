from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import (
    Admin, Status, Tracker, Settings, User, EmailTemplate,
    StatusGroup, STATUS_GROUPS, DEFAULT_STATUS_GROUP_NAMES,
)
from .security import hash_password, encrypt_secret

DEFAULT_EMAIL_TEMPLATES = (
    dict(
        key='ticket_created',
        name='Постановщик создал тикет (админу)',
        subject='GemTicket: тикет «{{ ticket_title }}»',
        body_html=(
            '<p>Постановщик {{ client_name }} создал(а) новый тикет.</p>'
            '<p>Тикет: {{ ticket_title }}</p>'
            '<p><a href="{{ ticket_link }}">Открыть тикет</a></p>'
        ),
        variables_hint='ticket_title, ticket_link, client_name',
    ),
    dict(
        key='comment_added',
        name='Новый комментарий',
        subject='GemTicket: комментарий в тикете «{{ ticket_title }}»',
        body_html=(
            '<p>{{ author_role }} {{ author_name }} оставил(а) комментарий к тикету.</p>'
            '<p>Тикет: {{ ticket_title }}</p>'
            '<p><a href="{{ ticket_link }}">Открыть тикет</a></p>'
        ),
        variables_hint='ticket_title, ticket_link, author_name, author_role',
    ),
    dict(
        key='ticket_edited_by_client',
        name='Постановщик отредактировал тикет',
        subject='GemTicket: тикет «{{ ticket_title }}» отредактирован',
        body_html=(
            '<p>Постановщик {{ client_name }} отредактировал(а) тикет.</p>'
            '<p>Тикет: {{ ticket_title }}</p>'
            '<p><a href="{{ ticket_link }}">Открыть тикет</a></p>'
        ),
        variables_hint='ticket_title, ticket_link, client_name',
    ),
    dict(
        key='status_changed',
        name='Смена статуса',
        subject='GemTicket: статус тикета «{{ ticket_title }}» изменён',
        body_html=(
            '<p>Статус тикета изменён с «{{ old_status }}» на «{{ new_status }}».</p>'
            '<p>Тикет: {{ ticket_title }}</p>'
            '<p><a href="{{ ticket_link }}">Открыть тикет</a></p>'
        ),
        variables_hint='ticket_title, ticket_link, old_status, new_status',
    ),
    dict(
        key='assignee_changed',
        name='Смена исполнителя',
        subject='GemTicket: исполнитель тикета «{{ ticket_title }}» изменён',
        body_html=(
            '<p>Исполнитель тикета изменён с «{{ old_assignee }}» на «{{ new_assignee }}».</p>'
            '<p>Тикет: {{ ticket_title }}</p>'
            '<p><a href="{{ ticket_link }}">Открыть тикет</a></p>'
        ),
        variables_hint='ticket_title, ticket_link, old_assignee, new_assignee',
    ),
    dict(
        key='deadline_changed',
        name='Смена дедлайна',
        subject='GemTicket: дедлайн тикета «{{ ticket_title }}» изменён',
        body_html=(
            '<p>Дедлайн тикета изменён с «{{ old_deadline }}» на «{{ new_deadline }}».</p>'
            '<p>Тикет: {{ ticket_title }}</p>'
            '<p><a href="{{ ticket_link }}">Открыть тикет</a></p>'
        ),
        variables_hint='ticket_title, ticket_link, old_deadline, new_deadline',
    ),
    dict(
        key='tracker_changed',
        name='Смена категории',
        subject='GemTicket: категория тикета «{{ ticket_title }}» изменена',
        body_html=(
            '<p>Категория тикета изменена с «{{ old_tracker }}» на «{{ new_tracker }}».</p>'
            '<p>Тикет: {{ ticket_title }}</p>'
            '<p><a href="{{ ticket_link }}">Открыть тикет</a></p>'
        ),
        variables_hint='ticket_title, ticket_link, old_tracker, new_tracker',
    ),
    dict(
        key='priority_changed',
        name='Смена приоритета',
        subject='GemTicket: приоритет тикета «{{ ticket_title }}» изменён',
        body_html=(
            '<p>Приоритет тикета изменён с «{{ old_priority }}» на «{{ new_priority }}».</p>'
            '<p>Тикет: {{ ticket_title }}</p>'
            '<p><a href="{{ ticket_link }}">Открыть тикет</a></p>'
        ),
        variables_hint='ticket_title, ticket_link, old_priority, new_priority',
    ),
    dict(
        key='deadline_overdue',
        name='Просрочен дедлайн (суперадмину)',
        subject='GemTicket: просрочен дедлайн тикета «{{ ticket_title }}»',
        body_html=(
            '<p>Дедлайн тикета истёк {{ deadline }}, но тикет ещё не завершён.</p>'
            '<p>Исполнитель: {{ assignee_name }}</p>'
            '<p>Постановщик: {{ client_name }}</p>'
            '<p>Тикет: {{ ticket_title }}</p>'
            '<p><a href="{{ ticket_link }}">Открыть тикет</a></p>'
        ),
        variables_hint='ticket_title, ticket_link, assignee_name, client_name, deadline',
    ),
)


def seed_reference_data():
    if Status.query.count() == 0:
        for name, order, is_default, color, is_final, group in (
            ('Новый', 1, True, 'secondary', False, 1),
            ('В работе', 2, False, 'primary', False, 1),
            ('На проверке', 3, False, 'warning', False, 1),
            ('Готов', 4, False, 'success', True, 2),
            ('Отменён', 5, False, 'danger', True, 2),
        ):
            db.session.add(Status(
                name=name, order=order, is_default=is_default, color=color,
                is_active=True, is_final=is_final, group=group,
            ))

    if StatusGroup.query.count() == 0:
        for n in STATUS_GROUPS:
            db.session.add(StatusGroup(number=n, name=DEFAULT_STATUS_GROUP_NAMES[n]))

    if Tracker.query.count() == 0:
        for name, order in (('Баг', 1), ('Доработка', 2), ('Задача', 3)):
            db.session.add(Tracker(name=name, order=order, is_active=True))

    if Settings.query.count() == 0:
        from flask import current_app
        db.session.add(Settings(id=1, base_url=current_app.config.get('BASE_URL', 'http://localhost:5000'), max_upload_mb=50))

    db.session.commit()


def seed_email_templates():
    """Добавляет только НОВЫЕ шаблоны (по key), не трогая уже существующие —
    на случай если админ их отредактировал. Вызывается при каждом старте,
    поэтому появление нового типа письма в новой версии кода не требует
    ручных действий на уже развёрнутых инсталляциях."""
    existing_keys = {row.key for row in EmailTemplate.query.with_entities(EmailTemplate.key).all()}
    added = False
    for tpl in DEFAULT_EMAIL_TEMPLATES:
        if tpl['key'] not in existing_keys:
            db.session.add(EmailTemplate(**tpl))
            added = True
    if added:
        db.session.commit()


def seed_superadmin(admin_password):
    if Admin.query.count() > 0:
        return

    if not admin_password:
        raise RuntimeError(
            'В базе нет ни одного админа, а переменная окружения ADMIN_PASSWORD не задана. '
            'Задайте ADMIN_PASSWORD и перезапустите приложение.'
        )

    pwd_hash = hash_password(admin_password)
    if User.query.filter_by(password_hash=pwd_hash).first():
        raise RuntimeError(
            'Пароль из ADMIN_PASSWORD уже занят другим пользователем в базе. Смените ADMIN_PASSWORD.'
        )

    admin = Admin(
        name='Суперадмин',
        email='admin@gemticket.local',
        password_hash=pwd_hash,
        password_encrypted=encrypt_secret(admin_password),
        is_superadmin=True,
    )
    db.session.add(admin)
    try:
        db.session.commit()
    except IntegrityError:
        # Гонка между несколькими воркерами при первом старте (обычно
        # предотвращается флагом --preload у gunicorn) — если админа уже
        # успел создать другой процесс, просто ничего не делаем.
        db.session.rollback()
