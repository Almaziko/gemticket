from datetime import datetime

from .extensions import db


class User(db.Model):
    """Базовая таблица учётки. Admin и Client — её joined-table наследники.

    Единая таблица паролей (password_hash) даёт глобальную уникальность
    пароля между админами и клиентами "бесплатно" — через один UNIQUE.
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_encrypted = db.Column(db.LargeBinary, nullable=False)
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    __mapper_args__ = {
        'polymorphic_identity': 'user',
        'polymorphic_on': role,
    }

    @property
    def role_label(self):
        return {'admin': 'Админ', 'client': 'Постановщик'}.get(self.role, self.role)


class Admin(User):
    __tablename__ = 'admins'

    id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    is_superadmin = db.Column(db.Boolean, default=False, nullable=False)

    clients = db.relationship(
        'Client', back_populates='assigned_admin', foreign_keys='Client.assigned_admin_id'
    )
    assigned_tickets = db.relationship(
        'Ticket', back_populates='assignee', foreign_keys='Ticket.assignee_id'
    )

    __mapper_args__ = {'polymorphic_identity': 'admin'}


class Client(User):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    assigned_admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False)

    assigned_admin = db.relationship('Admin', back_populates='clients', foreign_keys=[assigned_admin_id])
    tickets = db.relationship('Ticket', back_populates='client', foreign_keys='Ticket.client_id')

    __mapper_args__ = {'polymorphic_identity': 'client'}


#: Ровно 5 предустановленных слотов группировки статусов — количество и
#: порядок сортировки (1 показывается первым в списках тикетов, 5 — последним)
#: зафиксированы системой. Названия групп при этом редактируются в админке —
#: см. модель StatusGroup ниже.
STATUS_GROUPS = (1, 2, 3, 4, 5)
DEFAULT_STATUS_GROUP_NAMES = {n: f'Группа {n}' for n in STATUS_GROUPS}

#: Чем сортируются тикеты внутри блока конкретной группы — задаётся
#: админом отдельно для каждой из 5 групп (см. StatusGroup.sort_mode).
SORT_MODE_PRIORITY = 'priority'
SORT_MODE_CREATED_AT = 'created_at'
SORT_MODE_CLOSED_AT = 'closed_at'
SORT_MODE_ID = 'id'
SORT_MODE_CHOICES = [
    (SORT_MODE_PRIORITY, 'По приоритету'),
    (SORT_MODE_CREATED_AT, 'По дате создания'),
    (SORT_MODE_CLOSED_AT, 'По дате закрытия'),
    (SORT_MODE_ID, 'По ID тикета'),
]
SORT_MODE_LABELS = dict(SORT_MODE_CHOICES)
DEFAULT_SORT_MODE = SORT_MODE_PRIORITY

#: Визуальное оформление блока группы — только в списках тикетов (админский
#: и постановщика), больше нигде. Готовые пресеты вместо произвольных цветов,
#: чтобы результат всегда выглядел опрятно: "приглушённая" — для
#: неважных/архивных групп (например, "Завершено"/"Отменено"), "акцентная" —
#: наоборот, чтобы группа бросалась в глаза.
GROUP_THEME_DEFAULT = 'default'
GROUP_THEME_MUTED = 'muted'
GROUP_THEME_CHOICES = [
    (GROUP_THEME_DEFAULT, 'Обычная'),
    (GROUP_THEME_MUTED, 'Приглушённая'),
    ('accent-blue', 'Акцентная — синяя'),
    ('accent-yellow', 'Акцентная — жёлтая'),
    ('accent-red', 'Акцентная — красная'),
    ('accent-green', 'Акцентная — зелёная'),
    ('accent-gray', 'Акцентная — серая'),
]
GROUP_THEME_LABELS = dict(GROUP_THEME_CHOICES)


class StatusGroup(db.Model):
    """Редактируемые в админке настройки одной из 5 фиксированных групп:
    название, чем внутри неё сортируются тикеты, и её визуальное оформление
    в списках тикетов. Строки на все 5 номеров сидируются один раз при первом
    старте — сама строка (номер) не создаётся и не удаляется, редактируются
    только name/sort_mode/theme."""
    __tablename__ = 'status_groups'

    number = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    sort_mode = db.Column(db.String(20), nullable=False, default=DEFAULT_SORT_MODE)
    theme = db.Column(db.String(20), nullable=False, default=GROUP_THEME_DEFAULT)


class Status(db.Model):
    __tablename__ = 'statuses'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    order = db.Column(db.Integer, nullable=False, default=0)
    color = db.Column(db.String(20), nullable=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_final = db.Column(db.Boolean, nullable=False, default=False)
    group = db.Column(db.Integer, nullable=False, default=1)
    # Кнопка автоперехода ("Проверено" и т.п.): постановщик видит её на
    # странице тикета, пока тикет в этом статусе, и по нажатию тикет сам
    # переходит на следующий статус по общему порядку (группа -> order).
    auto_advance_enabled = db.Column(db.Boolean, nullable=False, default=False)
    auto_advance_button_text = db.Column(db.String(80), nullable=True)
    # Кнопка возврата на доработку — тот же механизм, но в обратную сторону
    # по общему порядку (группа -> order) и с уведомлением исполнителя, а не
    # постановщика (тот, кто её нажал — сам постановщик).
    auto_revert_enabled = db.Column(db.Boolean, nullable=False, default=False)
    auto_revert_button_text = db.Column(db.String(80), nullable=True)

    tickets = db.relationship('Ticket', back_populates='status')

    @property
    def in_use(self):
        return len(self.tickets) > 0


def get_next_status(current_status):
    """Следующий статус по общему порядку списка статусов: сначала группа
    1..5, внутри группы — по order (это ровно тот порядок, в котором статусы
    показаны на /admin/statuses). Используется кнопкой автоперехода. None,
    если текущий статус последний по этому порядку."""
    ordered = Status.query.order_by(Status.group, Status.order).all()
    ids = [s.id for s in ordered]
    try:
        idx = ids.index(current_status.id)
    except ValueError:
        return None
    if idx + 1 < len(ordered):
        return ordered[idx + 1]
    return None


def get_previous_status(current_status):
    """Зеркально get_next_status — предыдущий статус по тому же общему
    порядку. Используется кнопкой возврата на доработку. None, если текущий
    статус первый по этому порядку."""
    ordered = Status.query.order_by(Status.group, Status.order).all()
    ids = [s.id for s in ordered]
    try:
        idx = ids.index(current_status.id)
    except ValueError:
        return None
    if idx - 1 >= 0:
        return ordered[idx - 1]
    return None


class Tracker(db.Model):
    __tablename__ = 'trackers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    tickets = db.relationship('Ticket', back_populates='tracker')

    @property
    def in_use(self):
        return len(self.tickets) > 0


#: Три фиксированных приоритета тикета. Числовые значения подобраны так,
#: чтобы сортировка "высокий приоритет выше" была простым ORDER BY DESC.
PRIORITY_HIGH = 3
PRIORITY_MEDIUM = 2
PRIORITY_LOW = 1
PRIORITY_CHOICES = [(PRIORITY_HIGH, 'Высокий'), (PRIORITY_MEDIUM, 'Средний'), (PRIORITY_LOW, 'Низкий')]
PRIORITY_LABELS = dict(PRIORITY_CHOICES)
PRIORITY_COLORS = {PRIORITY_HIGH: 'danger', PRIORITY_MEDIUM: 'warning', PRIORITY_LOW: 'secondary'}


class Ticket(db.Model):
    __tablename__ = 'tickets'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default='')
    deadline = db.Column(db.Date, nullable=True)
    priority = db.Column(db.Integer, nullable=False, default=PRIORITY_LOW)
    overdue_notified = db.Column(db.Boolean, nullable=False, default=False)
    #: Произвольная внешняя ссылка (задача в CRM, таблица и т.п.) — служебное
    #: поле только для исполнителя/суперадмина (постановщик его не видит и
    #: не редактирует), чтобы не терять, где именно ведётся тикет.
    bitrix24_url = db.Column(db.String(500), nullable=True)
    #: Проставляется/сбрасывается автоматически при смене статуса — см.
    #: change_status в tickets/routes.py. Нужно для сортировки группы "по
    #: дате закрытия".
    closed_at = db.Column(db.DateTime, nullable=True)

    tracker_id = db.Column(db.Integer, db.ForeignKey('trackers.id'), nullable=False)
    status_id = db.Column(db.Integer, db.ForeignKey('statuses.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    tracker = db.relationship('Tracker', back_populates='tickets')
    status = db.relationship('Status', back_populates='tickets')
    client = db.relationship('Client', back_populates='tickets', foreign_keys=[client_id])
    assignee = db.relationship('Admin', back_populates='assigned_tickets', foreign_keys=[assignee_id])

    comments = db.relationship(
        'Comment', back_populates='ticket', cascade='all, delete-orphan', order_by='Comment.created_at'
    )
    attachments = db.relationship(
        'Attachment', back_populates='ticket', cascade='all, delete-orphan',
        foreign_keys='Attachment.ticket_id'
    )
    events = db.relationship(
        'TicketEvent', cascade='all, delete-orphan', order_by='TicketEvent.created_at',
        primaryjoin='Ticket.id == TicketEvent.ticket_id'
    )
    notifications = db.relationship(
        'Notification', cascade='all, delete-orphan',
        primaryjoin='Ticket.id == Notification.ticket_id'
    )

    @property
    def priority_label(self):
        return PRIORITY_LABELS.get(self.priority, str(self.priority))

    @property
    def priority_color(self):
        return PRIORITY_COLORS.get(self.priority, 'secondary')


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body = db.Column(db.Text, nullable=False, default='')
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    ticket = db.relationship('Ticket', back_populates='comments')
    author = db.relationship('User')
    attachments = db.relationship(
        'Attachment', back_populates='comment', cascade='all, delete-orphan',
        foreign_keys='Attachment.comment_id'
    )


class Attachment(db.Model):
    __tablename__ = 'attachments'
    __table_args__ = (
        db.CheckConstraint(
            '(ticket_id IS NOT NULL AND comment_id IS NULL) OR '
            '(ticket_id IS NULL AND comment_id IS NOT NULL)',
            name='attachment_exactly_one_parent'
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    filename_original = db.Column(db.String(255), nullable=False)
    filename_stored = db.Column(db.String(255), nullable=False, unique=True)
    size_bytes = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(120), nullable=False)
    #: Где физически лежит файл — 'local' (диск сервера, как было всегда) или
    #: 's3' (S3-совместимое хранилище, см. Settings.s3_*). Нужен, чтобы старые
    #: вложения (сохранённые ещё до подключения S3) продолжали читаться с
    #: диска, а не только новые.
    storage = db.Column(db.String(10), nullable=False, default='local')
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True)

    ticket = db.relationship('Ticket', back_populates='attachments', foreign_keys=[ticket_id])
    comment = db.relationship('Comment', back_populates='attachments', foreign_keys=[comment_id])
    uploaded_by = db.relationship('User')

    @property
    def is_image(self):
        return (self.mime_type or '').startswith('image/')

    @property
    def parent_ticket(self):
        return self.ticket if self.ticket_id else (self.comment.ticket if self.comment else None)


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    recipient = db.relationship('User')
    ticket = db.relationship('Ticket')


class Settings(db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)

    smtp_host = db.Column(db.String(255), nullable=True)
    smtp_port = db.Column(db.Integer, nullable=True, default=587)
    smtp_username = db.Column(db.String(255), nullable=True)
    smtp_password_encrypted = db.Column(db.LargeBinary, nullable=True)
    smtp_from_address = db.Column(db.String(255), nullable=True)
    smtp_use_tls = db.Column(db.Boolean, nullable=False, default=True)
    smtp_use_ssl = db.Column(db.Boolean, nullable=False, default=False)

    base_url = db.Column(db.String(255), nullable=False, default='http://localhost:5000')
    max_upload_mb = db.Column(db.Integer, nullable=False, default=50)
    allowed_extensions = db.Column(db.String(500), nullable=False, default='zip,xlsx,xls,csv,docx,doc,pdf,jpeg,png,jpg')
    site_name = db.Column(db.String(120), nullable=False, default='GemTicket')
    favicon_filename = db.Column(db.String(255), nullable=True)

    #: S3-совместимое объектное хранилище для НОВЫХ вложений тикетов — чтобы
    #: не упираться в место на диске сервера. Если не заполнено (bucket
    #: пустой), вложения как и раньше сохраняются на локальный диск — старые
    #: вложения, уже лежащие локально, при заполнении этих полей никуда
    #: не переносятся (см. Attachment.storage).
    s3_endpoint = db.Column(db.String(255), nullable=True)
    s3_bucket = db.Column(db.String(255), nullable=True)
    #: Необязательный префикс ("папка") внутри бакета — чтобы разные проекты
    #: на одном бакете не путали файлы друг друга. Прибавляется только к
    #: НОВЫМ вложениям (см. s3_storage.build_key) — уже загруженные файлы
    #: свой ключ не меняют, даже если префикс потом поменять в настройках.
    s3_prefix = db.Column(db.String(255), nullable=True)
    s3_access_key = db.Column(db.String(255), nullable=True)
    s3_secret_key_encrypted = db.Column(db.LargeBinary, nullable=True)


class TicketEvent(db.Model):
    """Журнал истории тикета: кто и что поменял (статус, исполнитель, дедлайн, трекер, описание)."""
    __tablename__ = 'ticket_events'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    actor = db.relationship('User')


class EmailTemplate(db.Model):
    """Редактируемые в админке шаблоны писем-уведомлений. Тема и тело —
    строки Jinja (те же {{ переменная }}), body_html — санитайзится тем же
    bleach-пайплайном, что описание/комментарии (см. app/richtext.py)."""
    __tablename__ = 'email_templates'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(300), nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    variables_hint = db.Column(db.String(500), nullable=False, default='')
