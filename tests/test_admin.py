import re

from app.models import Status, EmailTemplate, Ticket


def test_status_list_seeded_with_final_flags(app, db):
    with app.app_context():
        gotov = Status.query.filter_by(name='Готов').first()
        otmenen = Status.query.filter_by(name='Отменён').first()
        novy = Status.query.filter_by(name='Новый').first()
        assert gotov.is_final is True
        assert otmenen.is_final is True
        assert novy.is_final is False


def test_status_list_seeded_with_groups(app, db):
    with app.app_context():
        novy = Status.query.filter_by(name='Новый').first()
        gotov = Status.query.filter_by(name='Готов').first()
        assert novy.group == 1
        assert gotov.group == 2


def test_statuses_admin_list_groups_by_group_field(admin_client):
    resp = admin_client.get('/admin/statuses')
    assert resp.status_code == 200
    text = resp.data.decode('utf-8')

    group1_header = re.search(r'card-header[^>]*>\s*Группа 1', text)
    group2_header = re.search(r'card-header[^>]*>\s*Группа 2', text)
    novy_idx = text.find('>Новый<')
    gotov_idx = text.find('>Готов<')

    assert group1_header and group2_header
    assert group1_header.start() < novy_idx < group2_header.start() < gotov_idx


def test_rename_status_group(admin_client, db):
    resp = admin_client.post('/admin/status-groups/update', data={
        'group_1': 'В работе', 'group_2': 'Завершено',
        'group_3': 'Группа 3', 'group_4': 'Группа 4', 'group_5': 'Группа 5',
        'sort_1': 'priority', 'sort_2': 'closed_at',
        'sort_3': 'priority', 'sort_4': 'priority', 'sort_5': 'priority',
    }, follow_redirects=False)
    assert resp.status_code == 302

    from app.models import StatusGroup
    assert StatusGroup.query.get(1).name == 'В работе'
    assert StatusGroup.query.get(2).name == 'Завершено'
    assert StatusGroup.query.get(2).sort_mode == 'closed_at'

    resp = admin_client.get('/admin/statuses')
    assert 'В работе' in resp.data.decode('utf-8')
    assert 'Завершено' in resp.data.decode('utf-8')


def test_group_sort_mode_by_created_at_ignores_priority(admin_client, client_client, db):
    """Если для группы выбрана сортировка "по дате создания", то тикет с
    низким приоритетом, созданный позже, всё равно должен быть выше более
    старого с высоким приоритетом — сортировка по приоритету в этой группе
    не применяется."""
    from app.models import PRIORITY_LOW, PRIORITY_HIGH

    admin_client.post('/admin/status-groups/update', data={
        'group_1': 'Группа 1', 'group_2': 'Группа 2',
        'group_3': 'Группа 3', 'group_4': 'Группа 4', 'group_5': 'Группа 5',
        'sort_1': 'created_at', 'sort_2': 'priority',
        'sort_3': 'priority', 'sort_4': 'priority', 'sort_5': 'priority',
    })

    client_client.post('/client/tickets/new', data={
        'title': 'High but older', 'description': '<p>d</p>', 'tracker_id': '1',
        'priority': str(PRIORITY_HIGH),
    })
    client_client.post('/client/tickets/new', data={
        'title': 'Low but newer', 'description': '<p>d</p>', 'tracker_id': '1',
        'priority': str(PRIORITY_LOW),
    })

    resp = client_client.get('/client/tickets')
    html = resp.data.decode('utf-8')
    assert html.find('Low but newer') < html.find('High but older')


def test_ticket_closed_at_set_and_cleared_on_status_change(admin_client, client_client, db):
    resp = client_client.post('/client/tickets/new', data={
        'title': 'Closing check', 'description': '<p>d</p>', 'tracker_id': '1',
    }, follow_redirects=False)
    ticket_id = resp.headers['Location'].rstrip('/').split('/')[-1]

    ticket = Ticket.query.get(int(ticket_id))
    assert ticket.closed_at is None

    final_status = Status.query.filter_by(is_final=True).first()
    non_final_status = Status.query.filter_by(is_default=True).first()

    admin_client.post(f'/tickets/{ticket_id}/status', data={'status_id': str(final_status.id)})
    db.session.refresh(ticket)
    assert ticket.closed_at is not None

    admin_client.post(f'/tickets/{ticket_id}/status', data={'status_id': str(non_final_status.id)})
    db.session.refresh(ticket)
    assert ticket.closed_at is None


def test_moving_status_only_reorders_within_same_group(admin_client, db):
    group1 = Status.query.filter_by(group=1).order_by(Status.order).all()
    assert len(group1) >= 2
    first, second = group1[0], group1[1]
    first_order, second_order = first.order, second.order

    other_group_status = Status.query.filter_by(group=2).first()
    other_group_order_before = other_group_status.order

    resp = admin_client.post(f'/admin/statuses/{second.id}/move/up', follow_redirects=False)
    assert resp.status_code == 302

    db.session.refresh(first)
    db.session.refresh(second)
    db.session.refresh(other_group_status)
    assert first.order == second_order
    assert second.order == first_order
    assert other_group_status.order == other_group_order_before  # соседняя группа не затронута


def test_status_group_change_moves_it_to_new_block(admin_client, db):
    status = Status.query.filter_by(name='На проверке').first()
    resp = admin_client.post(f'/admin/statuses/{status.id}/edit', data={
        'name': status.name, 'order': str(status.order), 'color': status.color or '',
        'group': '3', 'is_active': 'y',
    }, follow_redirects=False)
    assert resp.status_code == 302
    db.session.refresh(status)
    assert status.group == 3


def test_cannot_delete_status_in_use(admin_client, client_client, db):
    resp = client_client.post('/client/tickets/new', data={
        'title': 'For status delete test', 'description': '<p>d</p>', 'tracker_id': '1',
    })
    default_status = Status.query.filter_by(is_default=True).first()

    resp = admin_client.post(f'/admin/statuses/{default_status.id}/delete', follow_redirects=True)
    assert resp.status_code == 200
    assert 'используется тикетами'.encode() in resp.data
    assert Status.query.get(default_status.id) is not None


def test_only_one_default_status_at_a_time(admin_client, db):
    statuses = Status.query.order_by(Status.order).all()
    second = statuses[1]

    resp = admin_client.post(f'/admin/statuses/{second.id}/edit', data={
        'name': second.name, 'order': str(second.order), 'color': second.color or '',
        'is_default': 'y', 'is_active': 'y',
    }, follow_redirects=False)
    assert resp.status_code == 302

    defaults = Status.query.filter_by(is_default=True).all()
    assert len(defaults) == 1
    assert defaults[0].id == second.id


def test_email_templates_seeded(app, db):
    keys = {t.key for t in EmailTemplate.query.all()}
    assert {
        'ticket_created', 'comment_added', 'ticket_edited_by_client',
        'status_changed', 'assignee_changed', 'deadline_changed',
        'tracker_changed', 'deadline_overdue',
    } <= keys


def test_seeded_email_templates_bold_their_variables(app, db):
    """Значения переменных ({{ ticket_title }} и т.п.) должны быть обёрнуты в
    <strong>, чтобы в письме на почту они визуально выделялись жирным."""
    tpl = EmailTemplate.query.filter_by(key='status_changed').first()
    assert '<strong>{{ old_status }}</strong>' in tpl.body_html
    assert '<strong>{{ new_status }}</strong>' in tpl.body_html
    assert '<strong>{{ ticket_title }}</strong>' in tpl.body_html

    tpl2 = EmailTemplate.query.filter_by(key='ticket_created').first()
    assert '<strong>{{ client_name }}</strong>' in tpl2.body_html


def test_edit_email_template_sanitizes_html(admin_client, db):
    tpl = EmailTemplate.query.filter_by(key='ticket_created').first()
    resp = admin_client.post(f'/admin/email-templates/{tpl.id}/edit', data={
        'subject': 'New subject {{ ticket_title }}',
        'body_html': '<p>hi <script>alert(1)</script></p>',
    }, follow_redirects=False)
    assert resp.status_code == 302

    updated = EmailTemplate.query.get(tpl.id)
    assert '<script>' not in updated.body_html
    assert updated.subject == 'New subject {{ ticket_title }}'


def test_regular_admin_cannot_access_superadmin_pages(app, admin_client, db):
    from app.models import Admin
    from app.security import hash_password, encrypt_secret
    from tests.conftest import login

    regular = Admin(
        name='Regular', email='regular2@example.com',
        password_hash=hash_password('regularpass456'),
        password_encrypted=encrypt_secret('regularpass456'),
        is_superadmin=False,
    )
    db.session.add(regular)
    db.session.commit()

    session = app.test_client()
    login(session, 'regularpass456')

    for path in ('/admin/statuses', '/admin/trackers', '/admin/admins', '/admin/settings', '/admin/email-templates'):
        resp = session.get(path, follow_redirects=False)
        assert resp.status_code == 403, f'{path} should be superadmin-only'


def test_email_template_edit_form_has_single_body_field(admin_client, db):
    tpl = EmailTemplate.query.first()
    resp = admin_client.get(f'/admin/email-templates/{tpl.id}/edit')
    html = resp.data.decode('utf-8')
    assert html.count('name="body_html"') == 1


def test_superadmin_can_create_ticket_on_behalf_of_client(admin_client, client_user_password, db):
    from app.models import Client, Ticket, TicketEvent

    client_user = Client.query.first()

    resp = admin_client.get('/admin/tickets/new')
    assert resp.status_code == 200

    resp = admin_client.post('/admin/tickets/new', data={
        'client_id': str(client_user.id),
        'assignee_id': '1',
        'title': 'Заведено по звонку',
        'description': '<p>Клиент попросил по телефону</p>',
        'tracker_id': '1',
        'priority': '2',
    }, follow_redirects=False)
    assert resp.status_code == 302

    ticket = Ticket.query.filter_by(title='Заведено по звонку').first()
    assert ticket is not None
    assert ticket.client_id == client_user.id
    assert ticket.assignee_id == 1
    assert ticket.status.is_default is True

    event = TicketEvent.query.filter_by(ticket_id=ticket.id).first()
    assert event is not None
    assert 'от имени постановщика' in event.message


def test_ticket_created_by_admin_appears_in_clients_own_list(app, admin_client, client_user_password, db):
    from app.models import Client
    from tests.conftest import login

    client_user = Client.query.first()
    admin_client.post('/admin/tickets/new', data={
        'client_id': str(client_user.id), 'assignee_id': '1',
        'title': 'Тикет со стороны админа', 'description': '<p>d</p>', 'tracker_id': '1',
    })

    client_session = app.test_client()
    login(client_session, client_user_password)
    resp = client_session.get('/client/tickets')
    assert 'Тикет со стороны админа' in resp.data.decode('utf-8')


def test_regular_admin_cannot_create_ticket_on_behalf_of_client(app, db):
    from app.models import Admin
    from app.security import hash_password, encrypt_secret
    from tests.conftest import login

    regular = Admin(
        name='Regular Ticket Creator', email='regularticket@example.com',
        password_hash=hash_password('regularpassabc'),
        password_encrypted=encrypt_secret('regularpassabc'),
        is_superadmin=False,
    )
    db.session.add(regular)
    db.session.commit()

    session = app.test_client()
    login(session, 'regularpassabc')
    resp = session.get('/admin/tickets/new', follow_redirects=False)
    assert resp.status_code == 403


def test_tracker_renamed_to_category_in_ui(admin_client, client_client, db):
    """Регрессия: сущность "Трекер" переименована в "Категория" по всему
    UI, при этом внутренние Python/URL-имена (Tracker, /admin/trackers,
    tracker_id) намеренно не менялись."""
    resp = admin_client.get('/admin/trackers')
    html = resp.data.decode('utf-8')
    assert 'Категории' in html
    assert 'Трекер' not in html

    client_client.post('/client/tickets/new', data={
        'title': 'Category label check', 'description': '<p>d</p>', 'tracker_id': '1',
    })
    resp = admin_client.get('/admin/')
    html = resp.data.decode('utf-8')
    assert '>Категория<' in html
    assert 'Трекер' not in html
