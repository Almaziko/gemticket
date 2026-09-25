from app.models import Ticket


def _create_ticket(client_client):
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Bitrix24 field check', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    return int(resp.headers['Location'].rstrip('/').split('/')[-1])


def test_admin_can_set_bitrix24_url(admin_client, client_client, db):
    ticket_id = _create_ticket(client_client)

    resp = admin_client.post(f'/tickets/{ticket_id}/bitrix24', data={
        'bitrix24_url': 'https://company.bitrix24.ru/workgroups/group/1/tasks/task/view/42/',
    }, follow_redirects=False)
    assert resp.status_code == 302

    ticket = Ticket.query.get(ticket_id)
    assert ticket.bitrix24_url == 'https://company.bitrix24.ru/workgroups/group/1/tasks/task/view/42/'


def test_bitrix24_link_is_clickable_and_opens_new_tab(admin_client, client_client, db):
    ticket_id = _create_ticket(client_client)
    url = 'https://company.bitrix24.ru/workgroups/group/1/tasks/task/view/42/'
    admin_client.post(f'/tickets/{ticket_id}/bitrix24', data={'bitrix24_url': url})

    html = admin_client.get(f'/tickets/{ticket_id}').data.decode('utf-8')
    assert f'href="{url}"' in html
    assert 'target="_blank"' in html
    assert 'Открыть задачу' in html


def test_bitrix24_field_hidden_from_client(admin_client, client_client, db):
    ticket_id = _create_ticket(client_client)
    admin_client.post(f'/tickets/{ticket_id}/bitrix24', data={
        'bitrix24_url': 'https://company.bitrix24.ru/task/42/',
    })

    html = client_client.get(f'/tickets/{ticket_id}').data.decode('utf-8')
    assert 'Битрикс24' not in html
    assert 'bitrix24.ru' not in html


def test_client_cannot_set_bitrix24_url(client_client, db):
    ticket_id = _create_ticket(client_client)
    resp = client_client.post(f'/tickets/{ticket_id}/bitrix24', data={
        'bitrix24_url': 'https://company.bitrix24.ru/task/42/',
    }, follow_redirects=False)
    assert resp.status_code == 403

    ticket = Ticket.query.get(ticket_id)
    assert ticket.bitrix24_url is None


def test_invalid_bitrix24_url_rejected(admin_client, client_client, db):
    ticket_id = _create_ticket(client_client)
    resp = admin_client.post(f'/tickets/{ticket_id}/bitrix24', data={
        'bitrix24_url': 'not a url',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert 'Не удалось сохранить ссылку'.encode() in resp.data

    ticket = Ticket.query.get(ticket_id)
    assert ticket.bitrix24_url is None


def test_bitrix24_url_can_be_cleared(admin_client, client_client, db):
    ticket_id = _create_ticket(client_client)
    admin_client.post(f'/tickets/{ticket_id}/bitrix24', data={
        'bitrix24_url': 'https://company.bitrix24.ru/task/42/',
    })
    admin_client.post(f'/tickets/{ticket_id}/bitrix24', data={'bitrix24_url': ''})

    ticket = Ticket.query.get(ticket_id)
    assert ticket.bitrix24_url is None

    html = admin_client.get(f'/tickets/{ticket_id}').data.decode('utf-8')
    assert 'не указана' in html
