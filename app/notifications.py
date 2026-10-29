import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app, render_template_string

from .extensions import db
from .models import Notification, Settings, EmailTemplate
from .security import decrypt_secret

#: Переменные, которые рендер шаблона обязан оставлять в тексте нетронутыми,
#: байт в байт, вместо того чтобы (как для любой другой неизвестной
#: переменной) стирать в пустую строку — их подставляет сам Unisender Go
#: при отправке, своим шаблонизатором с тем же синтаксисом {{ }}. Значение
#: каждой переменной — её же литеральная запись без пробелов: Jinja просто
#: подставит эту строку на место {{ UnsubscribeUrl }}/{{UnsubscribeUrl}} в
#: шаблоне, и до Unisender долетит ровно {{UnsubscribeUrl}}.
PASSTHROUGH_TEMPLATE_VARS = {
    'UnsubscribeUrl': '{{UnsubscribeUrl}}',
}


def _build_link(settings, ticket, anchor=None):
    base = (settings.base_url or '').rstrip('/')
    link = f"{base}/tickets/{ticket.id}"
    return f"{link}#{anchor}" if anchor else link


def _append_footer(body, content_type):
    """Системный футер (ссылка отписки и т.п.) — дописывается к уже
    отрендеренному телу письма, а не хранится в самом шаблоне, поэтому в
    редакторе шаблонов (и в его живом превью) не виден. {{UnsubscribeUrl}}
    в футере через render_template_string не проходит вообще, так что
    отдельно защищать его как сквозную переменную не нужно — это обычная
    строка, добавленная уже после рендера."""
    footer = (
        current_app.config['EMAIL_FOOTER_HTML'] if content_type == 'html'
        else current_app.config['EMAIL_FOOTER_PLAIN']
    )
    return body + footer if footer else body


def _send_email_sync(settings, to_address, subject, body, content_type='plain'):
    password = ''
    if settings.smtp_password_encrypted:
        password = decrypt_secret(settings.smtp_password_encrypted)

    body = _append_footer(body, content_type)

    if settings.smtp_use_ssl:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
    try:
        if settings.smtp_use_tls and not settings.smtp_use_ssl:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, password)
        msg = MIMEMultipart()
        msg['From'] = settings.smtp_from_address or settings.smtp_username
        msg['To'] = to_address
        msg['Subject'] = subject
        msg['X-UNISENDER-GO'] = current_app.config['EMAIL_UNISENDER_GO_HEADER']
        msg.attach(MIMEText(body, content_type, 'utf-8'))
        server.sendmail(msg['From'], [to_address], msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass


def send_test_email(settings, to_address):
    """Синхронная отправка — используется кнопкой «отправить тестовое письмо»."""
    _send_email_sync(
        settings, to_address,
        'GemTicket: тестовое письмо',
        'Если вы получили это письмо — настройки SMTP верны.'
    )


def _send_email_async(recipient_email, subject, body, content_type='html'):
    settings = Settings.query.first()
    if not settings or not settings.smtp_host:
        # Раньше это было абсолютно тихо — ни строки в логе, что письмо
        # даже не попыталось уйти (не настроен SMTP). Со стороны выглядело
        # неотличимо от "ушло, но не долетело".
        current_app.logger.warning(
            'Email-уведомление "%s" для %s не отправлено: SMTP не настроен (нет settings/smtp_host)',
            subject, recipient_email,
        )
        return
    app = current_app._get_current_object()

    def worker():
        with app.app_context():
            try:
                fresh_settings = Settings.query.first()
                _send_email_sync(fresh_settings, recipient_email, subject, body, content_type=content_type)
                app.logger.info(
                    'Email-уведомление "%s" для %s: SMTP принял (250 OK) — если письмо всё равно не дошло, '
                    'искать дальше нужно на стороне Unisender Go (спам/фильтры/репутация отправителя), не в коде',
                    subject, recipient_email,
                )
            except Exception:
                app.logger.exception('Не удалось отправить email-уведомление "%s" для %s', subject, recipient_email)

    threading.Thread(target=worker, daemon=True).start()


def render_email(template_key, context):
    """Рендерит тему/тело шаблона письма с подстановкой переменных (Jinja).
    Неизвестные Jinja-переменные по умолчанию стираются в пустую строку —
    кроме тех, что в PASSTHROUGH_TEMPLATE_VARS: они обязаны долететь до
    Unisender Go нетронутыми, поэтому их значение — их же литеральная
    запись, подставляемая вместо себя же. Возвращает (None, None), если
    шаблон почему-то отсутствует в базе."""
    tpl = EmailTemplate.query.filter_by(key=template_key).first()
    if not tpl:
        current_app.logger.error('Не найден шаблон письма "%s"', template_key)
        return None, None
    full_context = dict(context)
    full_context.update(PASSTHROUGH_TEMPLATE_VARS)
    subject = render_template_string(tpl.subject, **full_context)
    body = render_template_string(tpl.body_html, **full_context)
    return subject, body


def _create(recipient, ticket, bell_message, template_key, context, comment=None):
    notification = Notification(
        recipient_id=recipient.id, ticket_id=ticket.id, message=bell_message,
        comment_id=comment.id if comment else None,
    )
    db.session.add(notification)
    db.session.commit()

    anchor = f'comment-{comment.id}' if comment else None
    settings = Settings.query.first()
    link = _build_link(settings, ticket, anchor) if settings else f'/tickets/{ticket.id}' + (f'#{anchor}' if anchor else '')
    full_context = dict(context, ticket_title=ticket.title, ticket_link=link)
    subject, body = render_email(template_key, full_context)
    if subject and body:
        _send_email_async(recipient.email, subject, body)
    elif subject is not None or body is not None:
        # Шаблон найден (иначе render_email уже залогировал бы это сам),
        # но после рендера тема или тело оказались пустой строкой —
        # например, шаблон случайно очистили в редакторе. Раньше здесь
        # тоже было тихое ничего.
        current_app.logger.warning(
            'Шаблон письма "%s" отрендерился в пустую тему/тело — письмо %s не отправлено',
            template_key, recipient.email,
        )


def notify_ticket_created(ticket):
    _create(
        ticket.assignee, ticket, f'Постановщик {ticket.client.name} создал новый тикет',
        'ticket_created', {'client_name': ticket.client.name},
    )


def notify_comment_added(ticket, author, comment):
    recipient = ticket.assignee if author.role == 'client' else ticket.client
    if recipient.id == author.id:
        return
    role_label = author.role_label
    _create(
        recipient, ticket, f'{role_label} {author.name} оставил(а) комментарий к тикету',
        'comment_added', {'author_name': author.name, 'author_role': role_label},
        comment=comment,
    )


def notify_ticket_edited_by_client(ticket):
    _create(
        ticket.assignee, ticket, f'Постановщик {ticket.client.name} отредактировал(а) тикет',
        'ticket_edited_by_client', {'client_name': ticket.client.name},
    )


def notify_status_changed(ticket, old_name, new_name, recipient=None):
    """recipient по умолчанию — постановщик (обычная ручная смена статуса
    исполнителем). Кнопка автоперехода передаёт recipient=ticket.assignee
    явно: там инициатор — сам постановщик, и слать ему письмо о его же
    собственном действии бессмысленно."""
    _create(
        recipient or ticket.client, ticket, f'Статус тикета изменён с «{old_name}» на «{new_name}»',
        'status_changed', {'old_status': old_name, 'new_status': new_name},
    )


def notify_assignee_changed(ticket, old_name, new_name):
    _create(
        ticket.client, ticket, f'Исполнитель тикета изменён с «{old_name}» на «{new_name}»',
        'assignee_changed', {'old_assignee': old_name, 'new_assignee': new_name},
    )


def notify_deadline_changed(ticket, old_value, new_value):
    _create(
        ticket.client, ticket, f'Дедлайн тикета изменён с «{old_value}» на «{new_value}»',
        'deadline_changed', {'old_deadline': old_value, 'new_deadline': new_value},
    )


def notify_tracker_changed(ticket, old_name, new_name):
    _create(
        ticket.client, ticket, f'Категория тикета изменена с «{old_name}» на «{new_name}»',
        'tracker_changed', {'old_tracker': old_name, 'new_tracker': new_name},
    )


def notify_priority_changed(ticket, old_name, new_name):
    _create(
        ticket.client, ticket, f'Приоритет тикета изменён с «{old_name}» на «{new_name}»',
        'priority_changed', {'old_priority': old_name, 'new_priority': new_name},
    )


def notify_deadline_overdue(ticket, recipient):
    deadline_str = ticket.deadline.strftime('%d.%m.%Y') if ticket.deadline else ''
    _create(
        recipient, ticket,
        f'Просрочен дедлайн тикета «{ticket.title}» (исполнитель: {ticket.assignee.name})',
        'deadline_overdue',
        {
            'assignee_name': ticket.assignee.name,
            'client_name': ticket.client.name,
            'deadline': deadline_str,
        },
    )
