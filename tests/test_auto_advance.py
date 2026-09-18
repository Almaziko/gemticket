from app.models import Status, Ticket, TicketEvent, Notification, get_next_status


def test_get_next_status_follows_group_then_order(app, db):
    with app.app_context():
        novy = Status.query.filter_by(name='Новый').first()
        v_rabote = Status.query.filter_by(name='В работе').first()
        na_proverke = Status.query.filter_by(name='На проверке').first()
        gotov = Status.query.filter_by(name='Готов').first()
        otmenen = Status.query.filter_by(name='Отменён').first()

        assert get_next_status(novy).id == v_rabote.id
        assert get_next_status(v_rabote).id == na_proverke.id
        assert get_next_status(na_proverke).id == gotov.id
        assert get_next_status(gotov).id == otmenen.id
        assert get_next_status(otmenen) is None


def test_enabling_auto_advance_requires_button_text(admin_client, db):
    status = Status.query.filter_by(name='На проверке').first()
    resp = admin_client.post(f'/admin/statuses/{status.id}/edit', data={
        'name': status.name, 'order': str(status.order), 'color': status.color or '',
        'group': '1', 'is_active': 'y', 'auto_advance_enabled': 'y', 'auto_advance_button_text': '',
    }, follow_redirects=False)
    assert resp.status_code == 200
    assert 'Укажите текст кнопки'.encode() in resp.data
    db.session.refresh(status)
    assert status.auto_advance_enabled is False


def test_admin_can_enable_auto_advance_on_status(admin_client, db):
    status = Status.query.filter_by(name='На проверке').first()
    resp = admin_client.post(f'/admin/statuses/{status.id}/edit', data={
        'name': status.name, 'order': str(status.order), 'color': status.color or '',
        'group': '1', 'is_active': 'y', 'auto_advance_enabled': 'y', 'auto_advance_button_text': 'Проверено',
    }, follow_redirects=False)
    assert resp.status_code == 302
    db.session.refresh(status)
    assert status.auto_advance_enabled is True
    assert status.auto_advance_button_text == 'Проверено'


def _create_ticket_and_move_to_na_proverke(admin_client, client_client, db):
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Auto advance check', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    na_proverke = Status.query.filter_by(name='На проверке').first()
    admin_client.post(f'/tickets/{ticket_id}/status', data={'status_id': str(na_proverke.id)})
    return int(ticket_id)


def test_client_sees_and_can_click_advance_button(admin_client, client_client, db):
    status = Status.query.filter_by(name='На проверке').first()
    admin_client.post(f'/admin/statuses/{status.id}/edit', data={
        'name': status.name, 'order': str(status.order), 'color': status.color or '',
        'group': '1', 'is_active': 'y', 'auto_advance_enabled': 'y', 'auto_advance_button_text': 'Проверено',
    })

    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)

    resp = client_client.get(f'/tickets/{ticket_id}')
    assert 'Проверено'.encode() in resp.data

    resp = client_client.post(f'/tickets/{ticket_id}/advance-status', follow_redirects=False)
    assert resp.status_code == 302

    ticket = Ticket.query.get(ticket_id)
    assert ticket.status.name == 'Готов'

    event = TicketEvent.query.filter_by(ticket_id=ticket_id).order_by(TicketEvent.id.desc()).first()
    assert 'изменил(а) статус с' in event.message
    assert 'Готов' in event.message


def test_advance_status_notifies_assignee_not_client(admin_client, client_client, db):
    """Регрессия: при смене статуса кнопкой автоперехода инициатор — сам
    постановщик, поэтому письмо/колокольчик о смене статуса должны уходить
    исполнителю, а не самому постановщику (иначе он получал бы уведомление
    о собственном же действии). Ручная смена статуса исполнителем по-прежнему
    уведомляет постановщика — это не должно измениться."""
    status = Status.query.filter_by(name='На проверке').first()
    admin_client.post(f'/admin/statuses/{status.id}/edit', data={
        'name': status.name, 'order': str(status.order), 'color': status.color or '',
        'group': '1', 'is_active': 'y', 'auto_advance_enabled': 'y', 'auto_advance_button_text': 'Проверено',
    })
    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)
    ticket = Ticket.query.get(ticket_id)
    client_id = ticket.client_id
    assignee_id = ticket.assignee_id

    Notification.query.filter_by(ticket_id=ticket_id).delete()
    db.session.commit()

    client_client.post(f'/tickets/{ticket_id}/advance-status')

    notifications = Notification.query.filter_by(ticket_id=ticket_id).all()
    assert len(notifications) == 1
    assert notifications[0].recipient_id == assignee_id
    assert notifications[0].recipient_id != client_id


def test_manual_status_change_still_notifies_client(admin_client, client_client, db):
    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)
    ticket = Ticket.query.get(ticket_id)
    client_id = ticket.client_id

    Notification.query.filter_by(ticket_id=ticket_id).delete()
    db.session.commit()

    gotov = Status.query.filter_by(name='Готов').first()
    admin_client.post(f'/tickets/{ticket_id}/status', data={'status_id': str(gotov.id)})

    notifications = Notification.query.filter_by(ticket_id=ticket_id).all()
    assert len(notifications) == 1
    assert notifications[0].recipient_id == client_id


def test_advance_button_not_shown_when_disabled(admin_client, client_client, db):
    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)
    resp = client_client.get(f'/tickets/{ticket_id}')
    assert b'advance-status' not in resp.data


def test_advance_status_returns_403_when_not_enabled(admin_client, client_client, db):
    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)
    resp = client_client.post(f'/tickets/{ticket_id}/advance-status', follow_redirects=False)
    assert resp.status_code == 403


def test_advance_status_returns_403_for_admin(admin_client, client_client, db):
    status = Status.query.filter_by(name='На проверке').first()
    admin_client.post(f'/admin/statuses/{status.id}/edit', data={
        'name': status.name, 'order': str(status.order), 'color': status.color or '',
        'group': '1', 'is_active': 'y', 'auto_advance_enabled': 'y', 'auto_advance_button_text': 'Проверено',
    })
    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)

    resp = admin_client.post(f'/tickets/{ticket_id}/advance-status', follow_redirects=False)
    assert resp.status_code == 403


def test_advance_status_returns_403_for_other_clients_ticket(app, admin_client, client_client, db):
    from tests.conftest import create_client_user, login

    status = Status.query.filter_by(name='На проверке').first()
    admin_client.post(f'/admin/statuses/{status.id}/edit', data={
        'name': status.name, 'order': str(status.order), 'color': status.color or '',
        'group': '1', 'is_active': 'y', 'auto_advance_enabled': 'y', 'auto_advance_button_text': 'Проверено',
    })
    ticket_id = _create_ticket_and_move_to_na_proverke(admin_client, client_client, db)

    other_password = create_client_user(
        admin_client, name='Other Client', email='otherclient2@example.com', password='otherclientpass789',
    )
    other_session = app.test_client()
    login(other_session, other_password)

    resp = other_session.post(f'/tickets/{ticket_id}/advance-status', follow_redirects=False)
    assert resp.status_code == 403


def test_advance_status_no_op_when_already_last_status(admin_client, client_client, db):
    otmenen = Status.query.filter_by(name='Отменён').first()
    admin_client.post(f'/admin/statuses/{otmenen.id}/edit', data={
        'name': otmenen.name, 'order': str(otmenen.order), 'color': otmenen.color or '',
        'group': '2', 'is_active': 'y', 'is_final': 'y',
        'auto_advance_enabled': 'y', 'auto_advance_button_text': 'Дальше',
    })

    resp = client_client.post('/client/tickets/new', data={
        'title': 'Last status check', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]
    admin_client.post(f'/tickets/{ticket_id}/status', data={'status_id': str(otmenen.id)})

    resp = client_client.post(f'/tickets/{ticket_id}/advance-status', follow_redirects=True)
    assert resp.status_code == 200
    assert 'Следующий статус не найден'.encode() in resp.data
