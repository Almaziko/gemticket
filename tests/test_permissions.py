import re

from app.models import Ticket, Status


def _create_ticket(client_client, title='Perm ticket'):
    resp = client_client.post('/client/tickets/new', data={
        'title': title, 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    return resp.headers['Location'].rstrip('/').split('/')[-1]


def test_client_cannot_access_admin_routes(client_client):
    resp = client_client.get('/admin/', follow_redirects=False)
    assert resp.status_code == 403


def test_admin_cannot_create_ticket_as_client(admin_client):
    resp = admin_client.get('/client/tickets/new', follow_redirects=False)
    assert resp.status_code == 403


def test_client_cannot_view_other_clients_ticket(app, admin_client, client_user_password):
    # создаём тикет от имени первого клиента
    first_client = app.test_client()
    from tests.conftest import login
    login(first_client, client_user_password)
    ticket_id = _create_ticket(first_client, 'First client ticket')

    # заводим второго клиента и логинимся под ним
    from tests.conftest import create_client_user
    second_password = create_client_user(
        admin_client, name='Second Client', email='second@example.com', password='secondpass456',
    )
    second_client = app.test_client()
    login(second_client, second_password)

    resp = second_client.get(f'/tickets/{ticket_id}', follow_redirects=False)
    assert resp.status_code == 403


def test_client_blocked_from_commenting_on_final_status(app, admin_client, client_client, db):
    ticket_id = _create_ticket(client_client)

    final_status = Status.query.filter_by(is_final=True).first()
    resp = admin_client.post(f'/tickets/{ticket_id}/status', data={'status_id': str(final_status.id)},
                              follow_redirects=False)
    assert resp.status_code == 302

    resp = client_client.get(f'/tickets/{ticket_id}')
    assert 'не может добавлять комментарии'.encode() in resp.data

    resp = client_client.post(f'/tickets/{ticket_id}/comment', data={'body': '<p>blocked</p>'},
                               follow_redirects=False)
    assert resp.status_code == 403


def test_admin_can_still_comment_on_final_status(app, admin_client, client_client, db):
    ticket_id = _create_ticket(client_client)
    final_status = Status.query.filter_by(is_final=True).first()
    admin_client.post(f'/tickets/{ticket_id}/status', data={'status_id': str(final_status.id)})

    resp = admin_client.post(f'/tickets/{ticket_id}/comment', data={'body': '<p>admin note</p>'},
                              follow_redirects=True)
    assert resp.status_code == 200
    assert b'admin note' in resp.data


def test_client_cannot_edit_description_after_leaving_default_status(admin_client, client_client, db):
    ticket_id = _create_ticket(client_client)
    non_default_status = Status.query.filter(Status.is_default.is_(False), Status.is_final.is_(False)).first()
    admin_client.post(f'/tickets/{ticket_id}/status', data={'status_id': str(non_default_status.id)})

    resp = client_client.post(f'/tickets/{ticket_id}/description', data={'description': '<p>edited</p>'},
                               follow_redirects=False)
    assert resp.status_code == 403


def test_regular_admin_cannot_reassign_ticket(app, admin_client, client_client, db):
    from app.models import Admin
    from app.security import hash_password, encrypt_secret

    other_admin = Admin(
        name='Regular Admin', email='regular@example.com',
        password_hash=hash_password('regularpass123'),
        password_encrypted=encrypt_secret('regularpass123'),
        is_superadmin=False,
    )
    db.session.add(other_admin)
    db.session.commit()

    ticket_id = _create_ticket(client_client)

    regular_session = app.test_client()
    from tests.conftest import login
    login(regular_session, 'regularpass123')

    resp = regular_session.post(f'/tickets/{ticket_id}/assignee', data={'assignee_id': str(other_admin.id)},
                                 follow_redirects=False)
    assert resp.status_code == 403


def test_password_must_be_globally_unique(admin_client, client_user_password):
    resp = admin_client.post('/admin/clients/new', data={
        'name': 'Dup', 'email': 'dup@example.com',
        'password': client_user_password, 'assigned_admin_id': '1',
    }, follow_redirects=False)
    assert resp.status_code == 200
    assert 'уже используется'.encode() in resp.data


def test_client_cannot_delete_ticket(client_client):
    ticket_id = _create_ticket(client_client)
    resp = client_client.post(f'/tickets/{ticket_id}/delete', follow_redirects=False)
    assert resp.status_code == 403


def test_regular_admin_cannot_delete_ticket(app, admin_client, client_client, db):
    from app.models import Admin
    from app.security import hash_password, encrypt_secret
    from tests.conftest import login

    other_admin = Admin(
        name='Regular Admin 2', email='regular3@example.com',
        password_hash=hash_password('regularpass789'),
        password_encrypted=encrypt_secret('regularpass789'),
        is_superadmin=False,
    )
    db.session.add(other_admin)
    db.session.commit()

    ticket_id = _create_ticket(client_client)

    session = app.test_client()
    login(session, 'regularpass789')
    resp = session.post(f'/tickets/{ticket_id}/delete', follow_redirects=False)
    assert resp.status_code == 403
