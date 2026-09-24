import re
import time as time_module

import pytest
from flask import session
from flask_wtf.csrf import generate_csrf, validate_csrf

from app import create_app
from tests.conftest import ADMIN_PASSWORD


@pytest.fixture()
def csrf_app(tmp_path):
    """Отдельное приложение с ВКЛЮЧЁННОЙ CSRF-защитой (в отличие от общего
    conftest.app, где она выключена ради простоты остальных тестов) — иначе
    этот сценарий (просроченный/битый токен) вообще нечего было бы проверять."""
    db_file = tmp_path / 'csrf_test.db'
    upload_dir = tmp_path / 'uploads'
    application = create_app(config_overrides={
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_file}',
        'UPLOAD_DIR': str(upload_dir),
        'WTF_CSRF_ENABLED': True,
        'TESTING': True,
    })
    return application


def _extract_csrf_token(html):
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    assert m, 'csrf_token input not found on page'
    return m.group(1)


def _login(client, password):
    token = _extract_csrf_token(client.get('/login').data.decode('utf-8'))
    return client.post('/login', data={'password': password, 'csrf_token': token}, follow_redirects=False)


def test_csrf_time_limit_is_disabled(csrf_app):
    assert csrf_app.config['WTF_CSRF_TIME_LIMIT'] is None


def test_two_hour_old_token_still_validates(csrf_app, monkeypatch):
    """Регрессия: раньше форму (например, комментарий), открытую больше часа,
    нельзя было отправить — Flask-WTF по умолчанию считает токен просроченным
    через 3600 секунд ("The CSRF token has expired"), и введённый текст
    комментария терялся вместе с этой ошибкой. WTF_CSRF_TIME_LIMIT = None
    снимает ограничение по времени (токен всё равно проверяется на подпись
    и привязку к сессии)."""
    with csrf_app.test_request_context():
        token = generate_csrf()
        secret = session['csrf_token']

    real_time = time_module.time
    monkeypatch.setattr(time_module, 'time', lambda: real_time() + 7200)  # +2 часа

    with csrf_app.test_request_context():
        session['csrf_token'] = secret
        validate_csrf(token)  # не должно бросить исключение


def test_bad_csrf_token_redirects_with_flash_instead_of_bad_request(csrf_app):
    client = csrf_app.test_client()
    _login(client, ADMIN_PASSWORD)

    resp = client.post('/admin/tickets/new', data={'csrf_token': 'not-a-real-token'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Bad Request' not in resp.data
    assert 'Сессия истекла'.encode() in resp.data
