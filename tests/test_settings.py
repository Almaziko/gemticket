from io import BytesIO

from app.models import Settings


def _base_settings_payload(**overrides):
    payload = {
        'smtp_host': '', 'smtp_port': '', 'smtp_username': '', 'smtp_password': '',
        'smtp_from_address': '', 'base_url': 'http://localhost:5000',
        'max_upload_mb': '50', 'allowed_extensions': 'zip,pdf,png',
        'site_name': 'GemTicket',
    }
    payload.update(overrides)
    return payload


def test_change_site_name_reflected_in_title_and_navbar(admin_client, db):
    resp = admin_client.post('/admin/settings', data=_base_settings_payload(site_name='МояСлужбаПоддержки'), follow_redirects=False)
    assert resp.status_code == 302

    settings = Settings.query.first()
    assert settings.site_name == 'МояСлужбаПоддержки'

    resp = admin_client.get('/admin/')
    html = resp.data.decode('utf-8')
    assert '<title>МояСлужбаПоддержки</title>' in html or 'МояСлужбаПоддержки' in html
    assert 'GemTicket' not in html


def test_upload_favicon_sets_filename_and_serves_file(admin_client, db):
    resp = admin_client.post('/admin/settings', data=_base_settings_payload(
        favicon=(BytesIO(b'\x89PNG\r\n\x1a\nfakepngdata'), 'icon.png'),
    ), content_type='multipart/form-data', follow_redirects=False)
    assert resp.status_code == 302

    settings = Settings.query.first()
    assert settings.favicon_filename is not None
    assert settings.favicon_filename.endswith('.png')

    resp = admin_client.get(f'/favicon-file/{settings.favicon_filename}')
    assert resp.status_code == 200
    assert resp.data.startswith(b'\x89PNG')


def test_favicon_link_appears_in_page_head_once_uploaded(admin_client, db):
    admin_client.post('/admin/settings', data=_base_settings_payload(
        favicon=(BytesIO(b'\x89PNG\r\n\x1a\nfakepngdata'), 'icon2.png'),
    ), content_type='multipart/form-data')

    resp = admin_client.get('/admin/')
    html = resp.data.decode('utf-8')
    assert '<link rel="icon" href="/favicon-file/' in html
