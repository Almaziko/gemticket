from app.models import Status, Ticket, TicketEvent, Notification, get_previous_status


def test_get_previous_status_follows_group_then_order(app, db):
    with app.app_context():
        novy = Status.query.filter_by(name='Новый').first()
        v_rabote = Status.query.filter_by(name='В работе').first()
        na_proverke = Status.query.filter_by(name='На проверке').first()
        gotov = Status.query.filter_by(name='Готов').first()
        otmenen = Status.query.filter_by(name='Отменён').first()

        assert get_previous_status(novy) is None
        assert get_previous_status(v_rabote).id == novy.id
        assert get_previous_status(na_proverke).id == v_rabote.id
        assert get_previous_status(gotov).id == na_proverke.id
        assert get_previous_status(otmenen).id == gotov.id


def test_enabling_auto_revert_requires_button_text(admin_client, db):
    status = Status.query.filter_by(name='На проверке').first()
    resp = admin_client.post(f'/admin/statuses/{status.id}/edit', data={
        'name': status.name, 'order': str(status.order), 'color': status.color or '',
        'group': '1', 'is_active': 'y', 'auto_revert_enabled': 'y', 'auto_revert_button_text': '',
    }, follow_redirects=False)
    assert resp.status_code == 200
    assert 'Укажите текст кнопки'.encode() in resp.data
    db.session.refresh(status)
    assert status.auto_revert_enabled is False


def test_admin_can_enable_auto_revert_on_status(admin_client, db):
    status = Status.query.filter_by(name='На проверке').first()
    resp = admin_client.post(f'/admin/statuses/{status.id}/edit', data={
        'name': status.name, 'order': str(status.order), 'color': status.color or '',
        'group': '1', 'is_active': 'y', 'auto_revert_enabled': 'y', 'auto_revert_button_text': 'На доработку',
    }, follow_redirects=False)
    assert resp.status_code == 302
    db.session.refresh(status)
    assert status.auto_revert_enabled is True
    assert status.auto_revert_button_text == 'На доработку'


def _create_ticket_and_move_to_na_proverke(admin_client, client_client, db):
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Auto revert check', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    na_proverke = Status.query.filter_by(name='На проверке').first()
    admin_client.post(f'/tickets/{ticket_id}/status', data={'status_id': str(na_proverke.id)})
    return int(ticket_id)


def _enable_revert(admin_client, status, text='На доработку'):
    admin_client.post(f'/admin/statuses/{status.id}/edit', data={
        'name': status.name, 'order': str(status.order), 'color': status.color or '',
        'group': '1', 'is_active': 'y', 'auto_revert_enabled': 'y', 'auto_revert_button_text': text,
    })


def test_client_sees_and_can_click_revert_button(admin_client, client_client, db):
    status = Status.query.filter_by(name='На проверке').first()
    _enable_revert(admin_client, status)

    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)

    resp = client_client.get(f'/tickets/{ticket_id}')
    assert 'На доработку'.encode() in resp.data

    resp = client_client.post(f'/tickets/{ticket_id}/revert-status', follow_redirects=False)
    assert resp.status_code == 302

    ticket = Ticket.query.get(ticket_id)
    assert ticket.status.name == 'В работе'

    event = TicketEvent.query.filter_by(ticket_id=ticket_id).order_by(TicketEvent.id.desc()).first()
    assert 'изменил(а) статус с' in event.message
    assert 'В работе' in event.message


def test_revert_status_notifies_assignee_not_client(admin_client, client_client, db):
    status = Status.query.filter_by(name='На проверке').first()
    _enable_revert(admin_client, status)
    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)
    ticket = Ticket.query.get(ticket_id)
    client_id = ticket.client_id
    assignee_id = ticket.assignee_id

    Notification.query.filter_by(ticket_id=ticket_id).delete()
    db.session.commit()

    client_client.post(f'/tickets/{ticket_id}/revert-status')

    notifications = Notification.query.filter_by(ticket_id=ticket_id).all()
    assert len(notifications) == 1
    assert notifications[0].recipient_id == assignee_id
    assert notifications[0].recipient_id != client_id


def test_revert_button_not_shown_when_disabled(admin_client, client_client, db):
    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)
    resp = client_client.get(f'/tickets/{ticket_id}')
    assert b'revert-status' not in resp.data


def test_revert_status_returns_403_when_not_enabled(admin_client, client_client, db):
    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)
    resp = client_client.post(f'/tickets/{ticket_id}/revert-status', follow_redirects=False)
    assert resp.status_code == 403


def test_revert_status_returns_403_for_admin(admin_client, client_client, db):
    status = Status.query.filter_by(name='На проверке').first()
    _enable_revert(admin_client, status)
    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)

    resp = admin_client.post(f'/tickets/{ticket_id}/revert-status', follow_redirects=False)
    assert resp.status_code == 403


def test_revert_status_returns_403_for_other_clients_ticket(app, admin_client, client_client, db):
    from tests.conftest import create_client_user, login

    status = Status.query.filter_by(name='На проверке').first()
    _enable_revert(admin_client, status)
    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)

    other_password = create_client_user(
        admin_client, name='Other Client', email='otherclient3@example.com', password='otherclientpass321',
    )
    other_session = app.test_client()
    login(other_session, other_password)

    resp = other_session.post(f'/tickets/{ticket_id}/revert-status', follow_redirects=False)
    assert resp.status_code == 403


def test_revert_status_no_op_when_already_first_status(admin_client, client_client, db):
    novy = Status.query.filter_by(name='Новый').first()
    _enable_revert(admin_client, novy, text='Назад')

    resp = client_client.post('/client/tickets/new', data={
        'title': 'First status check', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    resp = client_client.post(f'/tickets/{ticket_id}/revert-status', follow_redirects=True)
    assert resp.status_code == 200
    assert 'Предыдущий статус не найден'.encode() in resp.data


def test_both_advance_and_revert_buttons_can_be_shown_together(admin_client, client_client, db):
    status = Status.query.filter_by(name='На проверке').first()
    admin_client.post(f'/admin/statuses/{status.id}/edit', data={
        'name': status.name, 'order': str(status.order), 'color': status.color or '',
        'group': '1', 'is_active': 'y',
        'auto_advance_enabled': 'y', 'auto_advance_button_text': 'Проверено',
        'auto_revert_enabled': 'y', 'auto_revert_button_text': 'На доработку',
    })
    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)

    html = client_client.get(f'/tickets/{ticket_id}').data.decode('utf-8')
    assert 'Проверено' in html
    assert 'На доработку' in html
