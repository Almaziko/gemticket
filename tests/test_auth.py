from tests.conftest import ADMIN_PASSWORD, login


def test_login_page_loads(client):
    resp = client.get('/login')
    assert resp.status_code == 200


def test_login_success_redirects_to_admin_dashboard(client):
    resp = login(client, ADMIN_PASSWORD)
    assert resp.status_code == 302
    assert resp.headers['Location'] == '/admin/'


def test_login_wrong_password_shows_error(client):
    resp = login(client, 'definitely-wrong-password')
    assert resp.status_code == 200
    assert 'Неверный пароль'.encode() in resp.data


def test_logout_clears_session(client):
    login(client, ADMIN_PASSWORD)
    resp = client.get('/admin/')
    assert resp.status_code == 200

    client.get('/logout')
    resp = client.get('/admin/', follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers['Location'] == '/login'


def test_unauthenticated_access_redirects_to_login(client):
    resp = client.get('/admin/', follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers['Location'] == '/login'
