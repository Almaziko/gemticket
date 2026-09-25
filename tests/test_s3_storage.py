import os
from io import BytesIO

from app.models import Attachment, Settings
from app.security import encrypt_secret
from app import s3_storage


def _configure_s3(app):
    with app.app_context():
        settings = Settings.query.first()
        settings.s3_endpoint = 'https://s3.example.com'
        settings.s3_bucket = 'my-bucket'
        settings.s3_access_key = 'AKIAEXAMPLE'
        settings.s3_secret_key_encrypted = encrypt_secret('super-secret')
        from app.extensions import db
        db.session.commit()


def test_admin_can_save_s3_credentials(admin_client, db):
    resp = admin_client.post('/admin/settings', data={
        'base_url': 'http://localhost', 'max_upload_mb': '50',
        'allowed_extensions': 'pdf,png', 'site_name': 'GemTicket',
        's3_endpoint': 'https://s3.beget.com', 's3_bucket': 'tickets-bucket',
        's3_access_key': 'AKIA123', 's3_secret_key': 'topsecret',
    }, follow_redirects=False)
    assert resp.status_code == 302

    settings = Settings.query.first()
    assert settings.s3_endpoint == 'https://s3.beget.com'
    assert settings.s3_bucket == 'tickets-bucket'
    assert settings.s3_access_key == 'AKIA123'
    from app.security import decrypt_secret
    assert decrypt_secret(settings.s3_secret_key_encrypted) == 'topsecret'


def test_settings_page_never_shows_saved_secret_key(admin_client, db):
    admin_client.post('/admin/settings', data={
        'base_url': 'http://localhost', 'max_upload_mb': '50',
        'allowed_extensions': 'pdf,png', 'site_name': 'GemTicket',
        's3_endpoint': 'https://s3.beget.com', 's3_bucket': 'tickets-bucket',
        's3_access_key': 'AKIA123', 's3_secret_key': 'topsecret',
    })
    html = admin_client.get('/admin/settings').data.decode('utf-8')
    assert 'topsecret' not in html


def test_attachment_stays_local_when_s3_not_configured(app, client_client, db):
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Local file', 'description': '<p>d</p>', 'tracker_id': '1',
        'attachments': (BytesIO(b'hello'), 'a.pdf'),
    }, content_type='multipart/form-data', follow_redirects=False)
    assert resp.status_code == 302

    attachment = Attachment.query.first()
    assert attachment.storage == 'local'
    assert os.path.exists(os.path.join(app.config['UPLOAD_DIR'], attachment.filename_stored))


def test_attachment_uploads_to_s3_when_configured(app, client_client, db, monkeypatch):
    _configure_s3(app)
    calls = {}

    def fake_upload_fileobj(settings, file_storage, key, content_type):
        calls['bucket'] = settings.s3_bucket
        calls['key'] = key
        calls['content_type'] = content_type

    monkeypatch.setattr(s3_storage, 'upload_fileobj', fake_upload_fileobj)

    resp = client_client.post('/client/tickets/new', data={
        'title': 'S3 file', 'description': '<p>d</p>', 'tracker_id': '1',
        'attachments': (BytesIO(b'hello from s3 test'), 'a.pdf'),
    }, content_type='multipart/form-data', follow_redirects=False)
    assert resp.status_code == 302

    attachment = Attachment.query.first()
    assert attachment.storage == 's3'
    assert attachment.size_bytes == len(b'hello from s3 test')
    assert calls['bucket'] == 'my-bucket'
    assert calls['key'] == attachment.filename_stored
    assert not os.path.exists(os.path.join(app.config['UPLOAD_DIR'], attachment.filename_stored))


def test_download_s3_attachment_redirects_to_presigned_url(app, admin_client, client_client, db, monkeypatch):
    _configure_s3(app)
    monkeypatch.setattr(s3_storage, 'upload_fileobj', lambda *a, **k: None)
    monkeypatch.setattr(
        s3_storage, 'generate_download_url',
        lambda settings, key, name, mime, as_attachment, expires_in=60: f'https://s3.example.com/signed/{key}',
    )

    resp = client_client.post('/client/tickets/new', data={
        'title': 'S3 download', 'description': '<p>d</p>', 'tracker_id': '1',
        'attachments': (BytesIO(b'content'), 'a.pdf'),
    }, content_type='multipart/form-data', follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    attachment = Attachment.query.filter_by(ticket_id=int(ticket_id)).first()

    resp = admin_client.get(f'/attachments/{attachment.id}/download', follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers['Location'] == f'https://s3.example.com/signed/{attachment.filename_stored}'


def test_delete_ticket_removes_s3_object(app, admin_client, client_client, db, monkeypatch):
    _configure_s3(app)
    monkeypatch.setattr(s3_storage, 'upload_fileobj', lambda *a, **k: None)
    deleted_keys = []
    monkeypatch.setattr(s3_storage, 'delete_object', lambda settings, key: deleted_keys.append(key))

    resp = client_client.post('/client/tickets/new', data={
        'title': 'S3 delete', 'description': '<p>d</p>', 'tracker_id': '1',
        'attachments': (BytesIO(b'content'), 'a.pdf'),
    }, content_type='multipart/form-data', follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]
    attachment = Attachment.query.filter_by(ticket_id=int(ticket_id)).first()

    admin_client.post(f'/tickets/{ticket_id}/delete')

    assert deleted_keys == [attachment.filename_stored]
