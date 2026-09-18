from io import BytesIO

from app.models import Ticket, Status


def test_create_ticket_success(client_client):
    resp = client_client.post('/client/tickets/new', data={
        'title': 'My first ticket',
        'description': '<p>Something is broken</p>',
        'tracker_id': '1',
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers['Location'].startswith('/tickets/')


def test_create_ticket_missing_title_rerenders_with_description_preserved(client_client):
    """Регрессия: раньше при ошибке валидации (например, не заполнен
    заголовок) форма перерисовывалась, а набранное описание визуально
    пропадало из WYSIWYG-редактора и терялось из скрытого поля."""
    resp = client_client.post('/client/tickets/new', data={
        'title': '',
        'description': '<p>Important text that must not disappear</p>',
        'tracker_id': '1',
    }, follow_redirects=False)
    assert resp.status_code == 200
    assert b'Important text that must not disappear' in resp.data


def test_create_ticket_disallowed_attachment_preserves_description(client_client):
    """Регрессия: та же потеря текста при отклонении вложения (недопустимое
    расширение) в форме создания тикета — validate_on_submit() успешен, но
    последующая проверка вложения проваливается и форма перерисовывается."""
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Ticket with bad attachment',
        'description': '<p>Do not lose me either</p>',
        'tracker_id': '1',
        'attachments': (BytesIO(b'fake exe content'), 'virus.exe'),
    }, content_type='multipart/form-data', follow_redirects=False)
    assert resp.status_code == 200
    assert b'Do not lose me either' in resp.data
    assert 'неразрешённое расширение'.encode() in resp.data


def test_create_ticket_oversized_attachment_preserves_description(client_client, db):
    from app.models import Settings
    settings = Settings.query.first()
    settings.max_upload_mb = 1
    db.session.commit()

    big_content = b'x' * (2 * 1024 * 1024)
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Ticket with huge attachment',
        'description': '<p>Keep this text visible</p>',
        'tracker_id': '1',
        'attachments': (BytesIO(big_content), 'big.pdf'),
    }, content_type='multipart/form-data', follow_redirects=False)
    assert resp.status_code == 200
    assert b'Keep this text visible' in resp.data
    assert 'превышает лимит'.encode() in resp.data


def test_new_ticket_gets_default_status_and_assignee(client_client, db):
    client_client.post('/client/tickets/new', data={
        'title': 'Status check',
        'description': '<p>d</p>',
        'tracker_id': '1',
    }, follow_redirects=False)
    ticket = Ticket.query.filter_by(title='Status check').first()
    assert ticket is not None
    assert ticket.status.is_default is True
    assert ticket.assignee_id == ticket.client.assigned_admin_id


def test_ticket_description_html_is_sanitized_and_stored(client_client, db):
    client_client.post('/client/tickets/new', data={
        'title': 'XSS check',
        'description': '<p>hello <script>alert(1)</script>world</p>',
        'tracker_id': '1',
    }, follow_redirects=False)
    ticket = Ticket.query.filter_by(title='XSS check').first()
    assert '<script>' not in ticket.description
    assert 'alert(1)' in ticket.description  # тег вырезан, текст остаётся


def test_add_comment_success(client_client, db):
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Ticket for comments',
        'description': '<p>d</p>',
        'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    resp = client_client.post(f'/tickets/{ticket_id}/comment', data={
        'body': '<p>My comment</p>',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'My comment' in resp.data


def test_add_comment_disallowed_attachment_preserves_comment_text(client_client):
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Ticket for bad comment attachment',
        'description': '<p>d</p>',
        'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    resp = client_client.post(f'/tickets/{ticket_id}/comment', data={
        'body': '<p>Comment text must survive</p>',
        'attachments': (BytesIO(b'bad'), 'virus.exe'),
    }, content_type='multipart/form-data', follow_redirects=False)
    assert resp.status_code == 200
    assert b'Comment text must survive' in resp.data


def test_ticket_list_shows_separate_blocks_per_status_group(admin_client, client_client, db):
    """Прямая проверка сценария из запроса: если два статуса относятся к
    разным группам, тикеты с этими статусами должны попасть в разные блоки
    списка, а не смешиваться в одном."""
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Group1 ticket', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket1_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    resp = client_client.post('/client/tickets/new', data={
        'title': 'Group2 ticket', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket2_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    group2_status = Status.query.filter_by(group=2).first()
    admin_client.post(f'/tickets/{ticket2_id}/status', data={'status_id': str(group2_status.id)})

    resp = client_client.get('/client/tickets')
    text = resp.data.decode('utf-8')
    group1_idx = text.find('Группа 1')
    group2_idx = text.find('Группа 2')
    ticket1_idx = text.find('Group1 ticket')
    ticket2_idx = text.find('Group2 ticket')

    assert group1_idx != -1 and group2_idx != -1
    assert group1_idx < ticket1_idx < group2_idx < ticket2_idx
