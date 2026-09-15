import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

from .extensions import db
from .models import Notification, Settings
from .security import decrypt_secret


def _build_link(settings, ticket):
    base = (settings.base_url or '').rstrip('/')
    return f"{base}/tickets/{ticket.id}"


def _send_email_sync(settings, to_address, subject, body):
    password = ''
    if settings.smtp_password_encrypted:
        password = decrypt_secret(settings.smtp_password_encrypted)

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
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
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


def _send_email_async(recipient_email, subject, body):
    settings = Settings.query.first()
    if not settings or not settings.smtp_host:
        return
    app = current_app._get_current_object()

    def worker():
        with app.app_context():
            try:
                fresh_settings = Settings.query.first()
                _send_email_sync(fresh_settings, recipient_email, subject, body)
            except Exception:
                app.logger.exception('Не удалось отправить email-уведомление')

    threading.Thread(target=worker, daemon=True).start()


def _create(recipient, ticket, message):
    notif = Notification(recipient_id=recipient.id, ticket_id=ticket.id, message=message)
    db.session.add(notif)
    db.session.commit()

    settings = Settings.query.first()
    link = _build_link(settings, ticket) if settings else f'/tickets/{ticket.id}'
    subject = f'GemTicket: тикет «{ticket.title}»'
    body = f"{message}\n\nТикет: {ticket.title}\nСсылка: {link}"
    _send_email_async(recipient.email, subject, body)


def notify_ticket_created(ticket):
    _create(ticket.assignee, ticket, f'Клиент {ticket.client.name} создал новый тикет')


def notify_comment_added(ticket, author):
    recipient = ticket.assignee if author.role == 'client' else ticket.client
    if recipient.id == author.id:
        return
    role_label = author.role_label
    _create(recipient, ticket, f'{role_label} {author.name} оставил(а) комментарий к тикету')


def notify_ticket_edited_by_client(ticket):
    _create(ticket.assignee, ticket, f'Клиент {ticket.client.name} отредактировал(а) тикет')


def notify_status_changed(ticket, old_name, new_name):
    _create(ticket.client, ticket, f'Статус тикета изменён с «{old_name}» на «{new_name}»')


def notify_assignee_changed(ticket, old_name, new_name):
    _create(ticket.client, ticket, f'Исполнитель тикета изменён с «{old_name}» на «{new_name}»')


def notify_deadline_changed(ticket, old_value, new_value):
    _create(ticket.client, ticket, f'Дедлайн тикета изменён с «{old_value}» на «{new_value}»')


def notify_tracker_changed(ticket, old_name, new_name):
    _create(ticket.client, ticket, f'Трекер тикета изменён с «{old_name}» на «{new_name}»')
