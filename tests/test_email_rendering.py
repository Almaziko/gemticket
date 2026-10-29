import email
from unittest.mock import patch, MagicMock

from app.extensions import db as _db
from app.models import EmailTemplate, Settings
from app.notifications import render_email, _send_email_sync, _append_footer


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
    with app.app_context():
        settings = Settings(
            smtp_host='smtp.example.com', smtp_port=587,
            smtp_username='user', smtp_from_address='from@example.com',
            smtp_use_tls=True, smtp_use_ssl=False,
        )
        _db.session.add(settings)
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
