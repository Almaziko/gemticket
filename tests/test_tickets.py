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


def test_ticket_new_form_has_single_description_field(client_client):
    """Регрессия: form.hidden_tag() без аргументов рендерит ЛЮБОЕ поле с
    виджетом HiddenInput (в т.ч. наше WYSIWYG-поле description), а оно же
    рендерится вручную через richtext_editor — получались два <input
    name="description">, и сервер брал первый (всегда пустой), из-за чего
    реальный пользователь в браузере не мог создать тикет: JS правильно
    синхронизировал свой скрытый инпут, но сервер читал чужой, пустой."""
    resp = client_client.get('/client/tickets/new')
    html = resp.data.decode('utf-8')
    assert html.count('name="description"') == 1


def test_ticket_detail_forms_have_single_body_and_description_fields(client_client):
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Field count check', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    resp = client_client.get(f'/tickets/{ticket_id}')
    html = resp.data.decode('utf-8')
    assert html.count('name="description"') == 1
    assert html.count('name="body"') == 1


def test_superadmin_can_delete_ticket_with_files_and_notifications(app, admin_client, client_client, db):
    import os
    from app.models import Comment, Attachment, Notification, TicketEvent

    resp = client_client.post('/client/tickets/new', data={
        'title': 'Ticket to delete', 'description': '<p>d</p>', 'tracker_id': '1',
        'attachments': (BytesIO(b'ticket file content'), 'ticket_file.pdf'),
    }, content_type='multipart/form-data', follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    client_client.post(f'/tickets/{ticket_id}/comment', data={
        'body': '<p>a comment</p>',
        'attachments': (BytesIO(b'comment file content'), 'comment_file.pdf'),
    }, content_type='multipart/form-data', follow_redirects=False)

    attachments = Attachment.query.all()
    assert len(attachments) == 2
    stored_paths = [os.path.join(app.config['UPLOAD_DIR'], a.filename_stored) for a in attachments]
    assert all(os.path.exists(p) for p in stored_paths)

    assert Comment.query.count() == 1
    assert Notification.query.filter_by(ticket_id=ticket_id).count() >= 1
    assert TicketEvent.query.filter_by(ticket_id=ticket_id).count() >= 1

    resp = admin_client.post(f'/tickets/{ticket_id}/delete', follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers['Location'] == '/admin/'

    assert Ticket.query.get(int(ticket_id)) is None
    assert Comment.query.count() == 0
    assert Attachment.query.count() == 0
    assert Notification.query.filter_by(ticket_id=ticket_id).count() == 0
    assert TicketEvent.query.filter_by(ticket_id=ticket_id).count() == 0
    assert not any(os.path.exists(p) for p in stored_paths)

    resp = client_client.get(f'/tickets/{ticket_id}', follow_redirects=False)
    assert resp.status_code == 404


def test_comment_badge_shows_executor_for_admin_author(admin_client, client_client):
    """В ленте комментариев роль автора-админа подписана "Исполнитель",
    а не общим role_label ("Админ") — иначе смешивается с тем, как сам
    админ видит свою роль в шапке."""
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Badge check', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    admin_client.post(f'/tickets/{ticket_id}/comment', data={'body': '<p>admin reply</p>'})

    resp = client_client.get(f'/tickets/{ticket_id}')
    html = resp.data.decode('utf-8')
    idx = html.find('admin reply')
    surrounding = html[max(0, idx - 400):idx]
    assert 'Исполнитель' in surrounding
    assert '>Админ<' not in surrounding


def test_ticket_created_with_chosen_priority(client_client, db):
    from app.models import PRIORITY_HIGH

    resp = client_client.post('/client/tickets/new', data={
        'title': 'High priority ticket', 'description': '<p>d</p>', 'tracker_id': '1',
        'priority': str(PRIORITY_HIGH),
    }, follow_redirects=False)
    assert resp.status_code == 302
    ticket = Ticket.query.filter_by(title='High priority ticket').first()
    assert ticket.priority == PRIORITY_HIGH
    assert ticket.priority_label == 'Высокий'


def test_ticket_defaults_to_medium_priority_when_not_specified(client_client, db):
    from app.models import PRIORITY_MEDIUM

    client_client.post('/client/tickets/new', data={
        'title': 'Default priority ticket', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket = Ticket.query.filter_by(title='Default priority ticket').first()
    assert ticket.priority == PRIORITY_MEDIUM


def test_admin_can_change_ticket_priority(admin_client, client_client, db):
    from app.models import PRIORITY_LOW

    resp = client_client.post('/client/tickets/new', data={
        'title': 'Priority change check', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    resp = admin_client.post(f'/tickets/{ticket_id}/priority', data={'priority': str(PRIORITY_LOW)},
                              follow_redirects=False)
    assert resp.status_code == 302

    ticket = Ticket.query.get(int(ticket_id))
    assert ticket.priority == PRIORITY_LOW


def test_client_cannot_change_ticket_priority(client_client, db):
    from app.models import PRIORITY_LOW

    resp = client_client.post('/client/tickets/new', data={
        'title': 'Client priority check', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    resp = client_client.post(f'/tickets/{ticket_id}/priority', data={'priority': str(PRIORITY_LOW)},
                               follow_redirects=False)
    assert resp.status_code == 403


def test_tickets_sorted_by_priority_then_creation_date(client_client, db):
    """Внутри одного блока (группы статуса) высокий приоритет должен идти
    выше среднего/низкого, а при равном приоритете — новее выше."""
    from app.models import PRIORITY_HIGH, PRIORITY_LOW

    def create(title, priority):
        client_client.post('/client/tickets/new', data={
            'title': title, 'description': '<p>d</p>', 'tracker_id': '1', 'priority': str(priority),
        }, follow_redirects=False)

    create('Low first', PRIORITY_LOW)
    create('Low second (newer)', PRIORITY_LOW)
    create('High but created last', PRIORITY_HIGH)

    resp = client_client.get('/client/tickets')
    html = resp.data.decode('utf-8')

    idx_high = html.find('High but created last')
    idx_low_second = html.find('Low second (newer)')
    idx_low_first = html.find('Low first')

    assert idx_high != -1 and idx_low_second != -1 and idx_low_first != -1
    # высокий приоритет — выше обоих низких, несмотря на то что создан позже
    assert idx_high < idx_low_second < idx_low_first
