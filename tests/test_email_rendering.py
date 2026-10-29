import email
import logging
from unittest.mock import patch, MagicMock

from app.extensions import db as _db
from app.models import EmailTemplate, Settings
from app.notifications import render_email, _send_email_sync, _append_footer, _send_email_async, _create


def _decoded_body(raw_message):
    msg = email.message_from_string(raw_message)
    for part in msg.walk():
        if part.get_content_maintype() == 'text':
            return part.get_payload(decode=True).decode('utf-8')
    raise AssertionError('no text part found in message')


def _make_template(app, key='unit_test_tpl', subject='Тема {{ ticket_title }} {{ unknown_var }}',
                    body='<p>{{ ticket_title }}</p><p>{{ unknown_var }}</p>'
                         '<p><a href="{{ UnsubscribeUrl }}">x</a></p>'
                         '<p>{{UnsubscribeUrl}}</p>'):
    with app.app_context():
        tpl = EmailTemplate(key=key, name='Unit test', subject=subject, body_html=body, variables_hint='')
        _db.session.add(tpl)
        _db.session.commit()


def _make_settings(app):
    """create_app() всегда сидирует ровно одну строку Settings(id=1) без
    smtp_host — заполняем именно её, а не добавляем вторую: иначе
    Settings.query.first() (как в _send_email_async) находит ту, первую,
    пустую строку, а не нашу."""
    with app.app_context():
        settings = Settings.query.first()
        settings.smtp_host = 'smtp.example.com'
        settings.smtp_port = 587
        settings.smtp_username = 'user'
        settings.smtp_from_address = 'from@example.com'
        settings.smtp_use_tls = True
        settings.smtp_use_ssl = False
        _db.session.commit()
        return settings.id


def test_unknown_variable_renders_as_empty_string(app):
    _make_template(app)
    with app.app_context():
        subject, body = render_email('unit_test_tpl', {'ticket_title': 'Заявка №1'})
    assert 'Заявка №1' in subject
    assert 'unknown_var' not in subject
    assert 'Заявка №1' in body


def test_unsubscribe_url_passes_through_untouched_regardless_of_spacing(app):
    _make_template(app)
    with app.app_context():
        subject, body = render_email('unit_test_tpl', {'ticket_title': 'Заявка №1'})
    # И вариант с пробелами внутри {{ }}, и слитный — оба должны дать ровно
    # {{UnsubscribeUrl}} без пробелов на выходе.
    assert body.count('{{UnsubscribeUrl}}') == 2
    assert '{{ UnsubscribeUrl }}' not in body
    assert 'href="{{UnsubscribeUrl}}"' in body


def test_missing_template_returns_none(app):
    with app.app_context():
        subject, body = render_email('does_not_exist', {})
    assert subject is None
    assert body is None


def test_append_footer_html(app):
    with app.app_context():
        result = _append_footer('<p>hello</p>', 'html')
    assert result.startswith('<p>hello</p>')
    assert '{{UnsubscribeUrl}}' in result
    assert 'Отключить уведомления' in result


def test_append_footer_plain(app):
    with app.app_context():
        result = _append_footer('hello', 'plain')
    assert result == 'hello' + app.config['EMAIL_FOOTER_PLAIN']
    assert '{{UnsubscribeUrl}}' in result


def test_append_footer_disabled_via_config(app):
    app.config['EMAIL_FOOTER_HTML'] = ''
    with app.app_context():
        result = _append_footer('<p>hello</p>', 'html')
    assert result == '<p>hello</p>'


@patch('app.notifications.smtplib.SMTP')
def test_send_email_adds_footer_and_unisender_header_html(mock_smtp_cls, app):
    settings_id = _make_settings(app)
    mock_server = MagicMock()
    mock_smtp_cls.return_value = mock_server

    with app.app_context():
        settings = _db.session.get(Settings, settings_id)
        _send_email_sync(settings, 'to@example.com', 'Subject', '<p>Body</p>', content_type='html')

    assert mock_server.sendmail.called
    from_addr, to_list, raw_message = mock_server.sendmail.call_args[0]
    assert to_list == ['to@example.com']
    assert 'X-UNISENDER-GO: {"track_links":0,"track_read":0}' in raw_message
    body = _decoded_body(raw_message)
    assert '{{UnsubscribeUrl}}' in body
    assert 'href="{{UnsubscribeUrl}}"' in body
    # Ссылка не должна быть URL-энкожена — фигурные скобки остаются как есть.
    assert '%7B%7B' not in body


@patch('app.notifications.smtplib.SMTP')
def test_send_email_adds_plain_footer(mock_smtp_cls, app):
    settings_id = _make_settings(app)
    mock_server = MagicMock()
    mock_smtp_cls.return_value = mock_server

    with app.app_context():
        settings = _db.session.get(Settings, settings_id)
        _send_email_sync(settings, 'to@example.com', 'Subject', 'Body text', content_type='plain')

    raw_message = mock_server.sendmail.call_args[0][2]
    body = _decoded_body(raw_message)
    assert 'Отключить уведомления: {{UnsubscribeUrl}}' in body


@patch('app.notifications.smtplib.SMTP')
def test_send_email_header_configurable_without_code_change(mock_smtp_cls, app):
    """Требование 5: значение заголовка и футеры читаются из конфига — можно
    поменять (например, добавить skip_unsubscribe или выключить футер) через
    app.config / переменные окружения, без правки кода notifications.py."""
    settings_id = _make_settings(app)
    app.config['EMAIL_UNISENDER_GO_HEADER'] = '{"track_links":0,"track_read":0,"skip_unsubscribe":1}'
    app.config['EMAIL_FOOTER_HTML'] = ''
    mock_server = MagicMock()
    mock_smtp_cls.return_value = mock_server

    with app.app_context():
        settings = _db.session.get(Settings, settings_id)
        _send_email_sync(settings, 'to@example.com', 'Subject', '<p>Body</p>', content_type='html')

    raw_message = mock_server.sendmail.call_args[0][2]
    assert 'skip_unsubscribe' in raw_message
    assert 'Отключить уведомления' not in raw_message


@patch('app.notifications.smtplib.SMTP')
def test_send_email_async_logs_success(mock_smtp_cls, app, caplog):
    """Раньше успешная фоновая отправка не оставляла в логе ни строки —
    неотличимо от того, что письмо вообще не пыталось уйти."""
    settings_id = _make_settings(app)
    mock_server = MagicMock()
    mock_smtp_cls.return_value = mock_server

    with app.app_context(), caplog.at_level(logging.INFO, logger='app'):
        _send_email_async('to@example.com', 'Subject', 'Body', content_type='plain')
        for t in list(__import__('threading').enumerate()):
            if t is not __import__('threading').current_thread():
                t.join(timeout=5)

    assert mock_server.sendmail.called
    assert any('SMTP принял' in r.message for r in caplog.records)


def test_send_email_async_without_smtp_logs_warning(app, caplog):
    """Нет настроенного SMTP — раньше тихо ничего не делал."""
    with app.app_context(), caplog.at_level(logging.WARNING, logger='app'):
        _send_email_async('to@example.com', 'Subject', 'Body')
    assert any('SMTP не настроен' in r.message for r in caplog.records)


def test_create_logs_warning_when_template_renders_blank(app, client_client, db, caplog):
    """Шаблон существует (иначе render_email сам бы залогировал "не найден"),
    но после очистки в редакторе тема/тело пустые — раньше письмо тихо не
    отправлялось без единого следа в логе."""
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Blank template check', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = int(resp.headers['Location'].rstrip('/').split('/')[-1])

    with app.app_context():
        tpl = EmailTemplate.query.filter_by(key='ticket_created').first()
        tpl.subject = ''
        tpl.body_html = ''
        _db.session.commit()

        from app.models import Ticket
        import app.notifications as notif_module
        ticket = _db.session.get(Ticket, ticket_id)
        with caplog.at_level(logging.WARNING, logger='app'):
            notif_module.notify_ticket_created(ticket)

    assert any('отрендерился в пустую тему/тело' in r.message for r in caplog.records)
