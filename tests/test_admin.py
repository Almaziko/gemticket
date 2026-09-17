from app.models import Status, EmailTemplate


def test_status_list_seeded_with_final_flags(app, db):
    with app.app_context():
        gotov = Status.query.filter_by(name='Готов').first()
        otmenen = Status.query.filter_by(name='Отменён').first()
        novy = Status.query.filter_by(name='Новый').first()
        assert gotov.is_final is True
        assert otmenen.is_final is True
        assert novy.is_final is False


def test_statuses_admin_list_groups_active_and_final(admin_client):
    resp = admin_client.get('/admin/statuses')
    assert resp.status_code == 200
    text = resp.data.decode('utf-8')
    active_idx = text.find('>Активные<')
    final_heading_idx = text.find('>Завершённые / отменённые<')
    novy_idx = text.find('>Новый<')
    gotov_idx = text.find('>Готов<')
    assert active_idx != -1 and final_heading_idx != -1
    assert active_idx < novy_idx < final_heading_idx < gotov_idx


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
