from io import BytesIO

from app.models import Attachment, Status, Ticket


def _create_ticket_with_attachment(client_client):
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Ticket with file', 'description': '<p>d</p>', 'tracker_id': '1',
        'attachments': (BytesIO(b'first file'), 'first.pdf'),
    }, content_type='multipart/form-data', follow_redirects=False)
    ticket_id = int(resp.headers['Location'].rstrip('/').split('/')[-1])
    return ticket_id


def test_client_can_add_attachment_while_editing_description(client_client, db):
    ticket_id = _create_ticket_with_attachment(client_client)

    resp = client_client.post(f'/tickets/{ticket_id}/description', data={
        'description': '<p>updated</p>',
        'attachments': (BytesIO(b'second file'), 'second.pdf'),
    }, content_type='multipart/form-data', follow_redirects=False)
    assert resp.status_code == 302

    attachments = Attachment.query.filter_by(ticket_id=ticket_id).all()
    assert len(attachments) == 2
    assert {a.filename_original for a in attachments} == {'first.pdf', 'second.pdf'}


def test_client_can_delete_own_ticket_attachment_in_default_status(client_client, db):
    ticket_id = _create_ticket_with_attachment(client_client)
    attachment = Attachment.query.filter_by(ticket_id=ticket_id).first()

    resp = client_client.post(f'/attachments/{attachment.id}/delete', follow_redirects=False)
    assert resp.status_code == 302
    assert Attachment.query.get(attachment.id) is None


def test_client_cannot_delete_attachment_once_ticket_left_default_status(admin_client, client_client, db):
    ticket_id = _create_ticket_with_attachment(client_client)
    attachment = Attachment.query.filter_by(ticket_id=ticket_id).first()

    other_status = Status.query.filter(Status.is_default.is_(False), Status.is_active.is_(True)).first()
    admin_client.post(f'/tickets/{ticket_id}/status', data={'status_id': str(other_status.id)})

    resp = client_client.post(f'/attachments/{attachment.id}/delete', follow_redirects=False)
    assert resp.status_code == 403
    assert Attachment.query.get(attachment.id) is not None


def test_admin_cannot_delete_client_ticket_attachment(admin_client, client_client, db):
    """Удаление вложения тикета — только у постановщика (то же окно, что и
    редактирование описания), у админа/исполнителя такой кнопки нет."""
    ticket_id = _create_ticket_with_attachment(client_client)
    attachment = Attachment.query.filter_by(ticket_id=ticket_id).first()

    resp = admin_client.post(f'/attachments/{attachment.id}/delete', follow_redirects=False)
    assert resp.status_code == 403
    assert Attachment.query.get(attachment.id) is not None


def test_comment_attachment_cannot_be_deleted_via_ticket_attachment_route(client_client, db):
    ticket_id = _create_ticket_with_attachment(client_client)
    client_client.post(f'/tickets/{ticket_id}/comment', data={
        'body': '<p>a comment</p>',
        'attachments': (BytesIO(b'comment file'), 'comment.pdf'),
    }, content_type='multipart/form-data')
    comment_attachment = Attachment.query.filter(Attachment.comment_id.isnot(None)).first()

    resp = client_client.post(f'/attachments/{comment_attachment.id}/delete', follow_redirects=False)
    assert resp.status_code == 403
    assert Attachment.query.get(comment_attachment.id) is not None
