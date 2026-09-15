import os

# Должны быть выставлены ДО первого импорта пакета app — Config читает
# переменные окружения на уровне тела класса, один раз за процесс.
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('ADMIN_PASSWORD', 'admin-test-password')
os.environ.setdefault('BASE_URL', 'http://localhost')

from cryptography.fernet import Fernet  # noqa: E402

os.environ.setdefault('FERNET_KEY', Fernet.generate_key().decode())

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db as _db  # noqa: E402

ADMIN_PASSWORD = os.environ['ADMIN_PASSWORD']


@pytest.fixture()
def app(tmp_path):
    db_file = tmp_path / 'test.db'
    upload_dir = tmp_path / 'uploads'
    application = create_app(config_overrides={
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_file}',
        'UPLOAD_DIR': str(upload_dir),
        'WTF_CSRF_ENABLED': False,
        'TESTING': True,
    })
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    with app.app_context():
        yield _db


def login(test_client, password):
    return test_client.post('/login', data={'password': password}, follow_redirects=False)


def logout(test_client):
    return test_client.get('/logout', follow_redirects=False)


def create_client_user(admin_test_client, name='Test Client', email='client@example.com',
                        password='clientpass123', assigned_admin_id=1):
    resp = admin_test_client.post('/admin/clients/new', data={
        'name': name, 'email': email, 'password': password,
        'assigned_admin_id': str(assigned_admin_id),
    }, follow_redirects=False)
    assert resp.status_code == 302, f'client creation failed: {resp.status_code} {resp.data[:300]}'
    return password


@pytest.fixture()
def admin_client(client):
    """Test client логинится суперадмином и остаётся им же (общая сессия)."""
    login(client, ADMIN_PASSWORD)
    return client


@pytest.fixture()
def client_user_password(admin_client):
    return create_client_user(admin_client)


@pytest.fixture()
def client_client(app, admin_client, client_user_password):
    """Отдельная тестовая сессия, залогиненная клиентом (не суперадмином)."""
    test_client = app.test_client()
    login(test_client, client_user_password)
    return test_client
