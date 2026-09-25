from app.models import StatusGroup, GROUP_THEME_DEFAULT


def _update_groups(admin_client, **theme_overrides):
    data = {
        'group_1': 'Группа 1', 'group_2': 'Группа 2',
        'group_3': 'Группа 3', 'group_4': 'Группа 4', 'group_5': 'Группа 5',
        'sort_1': 'priority', 'sort_2': 'priority',
        'sort_3': 'priority', 'sort_4': 'priority', 'sort_5': 'priority',
        'theme_1': 'default', 'theme_2': 'default',
        'theme_3': 'default', 'theme_4': 'default', 'theme_5': 'default',
    }
    data.update(theme_overrides)
    return admin_client.post('/admin/status-groups/update', data=data, follow_redirects=False)


def _create_ticket(client_client, title='Theme check'):
    resp = client_client.post('/client/tickets/new', data={
        'title': title, 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    return int(resp.headers['Location'].rstrip('/').split('/')[-1])


def test_status_group_defaults_to_default_theme(db):
    assert StatusGroup.query.get(1).theme == GROUP_THEME_DEFAULT


def test_admin_can_save_group_theme(admin_client, db):
    resp = _update_groups(admin_client, theme_2='muted')
    assert resp.status_code == 302
    assert StatusGroup.query.get(2).theme == 'muted'


def test_theme_class_appears_on_correct_group_card_in_admin_dashboard(admin_client, client_client, db):
    _create_ticket(client_client, 'In group one')
    _update_groups(admin_client, theme_1='muted')

    html = admin_client.get('/admin/').data.decode('utf-8')
    assert 'status-group-muted' in html


def test_theme_class_appears_on_client_tickets_list(admin_client, client_client, db):
    _create_ticket(client_client)
    _update_groups(admin_client, theme_1='accent-red')

    html = client_client.get('/client/tickets').data.decode('utf-8')
    assert 'status-group-accent-red' in html


def test_theme_class_absent_on_ticket_detail_page(admin_client, client_client, db):
    ticket_id = _create_ticket(client_client)
    _update_groups(admin_client, theme_1='accent-green')

    html = admin_client.get(f'/tickets/{ticket_id}').data.decode('utf-8')
    assert 'status-group-accent-green' not in html


def test_theme_class_absent_on_statuses_admin_page(admin_client, db):
    _update_groups(admin_client, theme_1='accent-yellow')

    html = admin_client.get('/admin/statuses').data.decode('utf-8')
    assert 'status-group-accent-yellow' not in html
