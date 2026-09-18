from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, g, abort, current_app
)

from ...extensions import db
from ...models import (
    User, Admin, Client, Status, Tracker, Ticket, Attachment, Settings, EmailTemplate,
    StatusGroup, STATUS_GROUPS,
)
from ...decorators import admin_required, superadmin_required
from ...security import hash_password, encrypt_secret, decrypt_secret
from ...attachments import (
    delete_attachment_file, refresh_max_content_length,
    check_files_size, check_files_extensions, save_attachments,
    save_favicon_file, delete_favicon_file,
    FileTooLargeError, DisallowedExtensionError,
)
from ...notifications import send_test_email
from ... import notifications as notif
from ...richtext import clean_html
from ...history import record_event
from ...grouping import group_by_status_group, group_tickets_sorted, get_group_names, get_group_sort_modes
from .forms import (
    ClientForm, AdminForm, StatusForm, StatusGroupSettingsForm, TrackerForm, SettingsForm,
    TestEmailForm, EmailTemplateForm, AdminTicketCreateForm,
)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _password_taken(password, exclude_user_id=None):
    pwd_hash = hash_password(password)
    q = User.query.filter_by(password_hash=pwd_hash)
    if exclude_user_id is not None:
        q = q.filter(User.id != exclude_user_id)
    return q.first() is not None


# ---------- Dashboard ----------

@admin_bp.route('/')
@admin_required
def dashboard():
    status_filter = request.args.get('status', type=int)
    search = (request.args.get('q') or '').strip()
    query = Ticket.query
    if not g.current_user.is_superadmin:
        query = query.filter_by(assignee_id=g.current_user.id)
    if status_filter:
        query = query.filter_by(status_id=status_filter)
    if search:
        query = query.filter(Ticket.title.ilike(f'%{search}%'))
    tickets = query.all()
    statuses = Status.query.order_by(Status.order).all()
    ticket_groups = group_tickets_sorted(tickets)
    status_groups = group_by_status_group(statuses, lambda s: s)
    return render_template(
        'admin/dashboard.html', tickets=tickets, statuses=statuses,
        ticket_groups=ticket_groups, status_groups=status_groups, group_names=get_group_names(),
        status_filter=status_filter, search=search,
    )


@admin_bp.route('/tickets/new', methods=['GET', 'POST'])
@superadmin_required
def ticket_new():
    """Тикет заводит суперадмин от имени клиента — например, клиент попросил
    об этом по телефону/в чате, пока сам зайти в систему не может. Дальше
    такой тикет ничем не отличается от созданного самим клиентом: постановщик
    — выбранный клиент, статус — стартовый по умолчанию."""
    form = AdminTicketCreateForm()
    form.client_id.choices = [(c.id, f'{c.name} ({c.email})') for c in Client.query.order_by(Client.name).all()]
    form.assignee_id.choices = [(a.id, a.name) for a in Admin.query.order_by(Admin.name).all()]
    form.tracker_id.choices = [
        (t.id, t.name) for t in Tracker.query.filter_by(is_active=True).order_by(Tracker.order).all()
    ]

    if not form.client_id.choices:
        flash('Сначала заведите хотя бы одного постановщика', 'danger')
        return redirect(url_for('admin.clients_list'))

    if form.validate_on_submit():
        files = request.files.getlist('attachments')
        try:
            check_files_size(files)
            check_files_extensions(files)
        except FileTooLargeError as e:
            flash(f'Файл «{e.filename}» превышает лимит {e.limit_mb} МБ. Тикет не создан.', 'danger')
            return render_template('admin/ticket_new.html', form=form)
        except DisallowedExtensionError as e:
            flash(f'Файл «{e.filename}» имеет неразрешённое расширение. Разрешены: {", ".join(e.allowed)}.', 'danger')
            return render_template('admin/ticket_new.html', form=form)

        client = Client.query.get_or_404(form.client_id.data)
        default_status = Status.query.filter_by(is_default=True).first()
        ticket = Ticket(
            title=form.title.data,
            description=clean_html(form.description.data),
            deadline=form.deadline.data,
            tracker_id=form.tracker_id.data,
            priority=form.priority.data,
            status_id=default_status.id,
            client_id=client.id,
            assignee_id=form.assignee_id.data,
        )
        db.session.add(ticket)
        db.session.flush()
        save_attachments(files, g.current_user, ticket=ticket)
        db.session.commit()

        if ticket.assignee_id != g.current_user.id:
            notif.notify_ticket_created(ticket)
        record_event(
            ticket, g.current_user,
            f'{g.current_user.name} создал(а) тикет от имени постановщика «{client.name}»',
        )
        flash('Тикет создан', 'success')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))

    return render_template('admin/ticket_new.html', form=form)


# ---------- Clients CRUD ----------

@admin_bp.route('/clients')
@admin_required
def clients_list():
    if g.current_user.is_superadmin:
        clients = Client.query.order_by(Client.name).all()
    else:
        clients = Client.query.filter_by(assigned_admin_id=g.current_user.id).order_by(Client.name).all()
    return render_template('admin/clients_list.html', clients=clients)


@admin_bp.route('/clients/new', methods=['GET', 'POST'])
@admin_required
def client_new():
    form = ClientForm()
    form.assigned_admin_id.choices = [(a.id, a.name) for a in Admin.query.order_by(Admin.name).all()]
    if request.method == 'GET' and not g.current_user.is_superadmin:
        form.assigned_admin_id.data = g.current_user.id

    if form.validate_on_submit():
        if not form.password.data:
            form.password.errors.append('Пароль обязателен для нового постановщика')
        elif _password_taken(form.password.data):
            form.password.errors.append('Этот пароль уже используется другим пользователем системы')
        else:
            assigned_admin_id = form.assigned_admin_id.data if g.current_user.is_superadmin else g.current_user.id
            client = Client(
                name=form.name.data,
                email=form.email.data,
                password_hash=hash_password(form.password.data),
                password_encrypted=encrypt_secret(form.password.data),
                assigned_admin_id=assigned_admin_id,
            )
            db.session.add(client)
            db.session.commit()
            flash('Постановщик создан', 'success')
            return redirect(url_for('admin.clients_list'))

    return render_template('admin/client_form.html', form=form, client=None)


@admin_bp.route('/clients/<int:client_id>/edit', methods=['GET', 'POST'])
@admin_required
def client_edit(client_id):
    client = Client.query.get_or_404(client_id)
    if not g.current_user.is_superadmin and client.assigned_admin_id != g.current_user.id:
        abort(403)

    form = ClientForm(obj=client)
    form.assigned_admin_id.choices = [(a.id, a.name) for a in Admin.query.order_by(Admin.name).all()]
    if request.method == 'GET':
        form.password.data = ''

    if form.validate_on_submit():
        if form.password.data and _password_taken(form.password.data, exclude_user_id=client.id):
            form.password.errors.append('Этот пароль уже используется другим пользователем системы')
        else:
            client.name = form.name.data
            client.email = form.email.data
            if g.current_user.is_superadmin:
                client.assigned_admin_id = form.assigned_admin_id.data
            if form.password.data:
                client.password_hash = hash_password(form.password.data)
                client.password_encrypted = encrypt_secret(form.password.data)
            db.session.commit()
            flash('Постановщик обновлён', 'success')
            return redirect(url_for('admin.clients_list'))

    return render_template('admin/client_form.html', form=form, client=client)


@admin_bp.route('/clients/<int:client_id>/password')
@admin_required
def client_show_password(client_id):
    client = Client.query.get_or_404(client_id)
    if not g.current_user.is_superadmin and client.assigned_admin_id != g.current_user.id:
        abort(403)
    plain = decrypt_secret(client.password_encrypted)
    flash(f'Пароль постановщика «{client.name}»: {plain}', 'info')
    return redirect(url_for('admin.clients_list'))


@admin_bp.route('/clients/<int:client_id>/delete', methods=['POST'])
@superadmin_required
def client_delete(client_id):
    client = Client.query.get_or_404(client_id)
    if client.tickets:
        flash('Нельзя удалить постановщика, у которого есть тикеты', 'danger')
    else:
        db.session.delete(client)
        db.session.commit()
        flash('Постановщик удалён', 'success')
    return redirect(url_for('admin.clients_list'))


# ---------- Admins CRUD (только суперадмин) ----------

@admin_bp.route('/admins')
@superadmin_required
def admins_list():
    admins = Admin.query.order_by(Admin.name).all()
    return render_template('admin/admins_list.html', admins=admins)


@admin_bp.route('/admins/new', methods=['GET', 'POST'])
@superadmin_required
def admin_new():
    form = AdminForm()
    if form.validate_on_submit():
        if not form.password.data:
            form.password.errors.append('Пароль обязателен')
        elif _password_taken(form.password.data):
            form.password.errors.append('Этот пароль уже используется другим пользователем системы')
        else:
            admin = Admin(
                name=form.name.data,
                email=form.email.data,
                password_hash=hash_password(form.password.data),
                password_encrypted=encrypt_secret(form.password.data),
                is_superadmin=False,
            )
            db.session.add(admin)
            db.session.commit()
            flash('Админ создан', 'success')
            return redirect(url_for('admin.admins_list'))
    return render_template('admin/admin_form.html', form=form, admin=None)


@admin_bp.route('/admins/<int:admin_id>/edit', methods=['GET', 'POST'])
@superadmin_required
def admin_edit(admin_id):
    admin = Admin.query.get_or_404(admin_id)
    form = AdminForm(obj=admin)
    if request.method == 'GET':
        form.password.data = ''

    if form.validate_on_submit():
        if form.password.data and _password_taken(form.password.data, exclude_user_id=admin.id):
            form.password.errors.append('Этот пароль уже используется другим пользователем системы')
        else:
            admin.name = form.name.data
            admin.email = form.email.data
            if form.password.data:
                admin.password_hash = hash_password(form.password.data)
                admin.password_encrypted = encrypt_secret(form.password.data)
            db.session.commit()
            flash('Админ обновлён', 'success')
            return redirect(url_for('admin.admins_list'))

    return render_template('admin/admin_form.html', form=form, admin=admin)


@admin_bp.route('/admins/<int:admin_id>/password')
@superadmin_required
def admin_show_password(admin_id):
    admin = Admin.query.get_or_404(admin_id)
    plain = decrypt_secret(admin.password_encrypted)
    flash(f'Пароль админа «{admin.name}»: {plain}', 'info')
    return redirect(url_for('admin.admins_list'))


@admin_bp.route('/admins/<int:admin_id>/delete', methods=['POST'])
@superadmin_required
def admin_delete(admin_id):
    admin = Admin.query.get_or_404(admin_id)
    if admin.id == g.current_user.id:
        flash('Нельзя удалить самого себя', 'danger')
    elif admin.is_superadmin:
        flash('Нельзя удалить суперадмина', 'danger')
    elif admin.clients:
        flash('Нельзя удалить админа с закреплёнными постановщиками — сначала переназначьте их', 'danger')
    else:
        db.session.delete(admin)
        db.session.commit()
        flash('Админ удалён', 'success')
    return redirect(url_for('admin.admins_list'))


# ---------- Статусы ----------

def _ensure_single_default(current_status):
    if current_status.is_default:
        Status.query.filter(Status.id != current_status.id).update({Status.is_default: False})
        db.session.commit()


@admin_bp.route('/statuses')
@superadmin_required
def statuses_list():
    statuses = Status.query.order_by(Status.order).all()
    group_names = get_group_names()
    group_sort_modes = get_group_sort_modes()
    group_settings_form = StatusGroupSettingsForm(data={
        **{f'group_{n}': name for n, name in group_names.items()},
        **{f'sort_{n}': mode for n, mode in group_sort_modes.items()},
    })
    return render_template('admin/statuses_list.html', statuses=statuses, group_settings_form=group_settings_form)


@admin_bp.route('/status-groups/update', methods=['POST'])
@superadmin_required
def status_groups_update():
    form = StatusGroupSettingsForm()
    if form.validate_on_submit():
        for n in STATUS_GROUPS:
            group_row = StatusGroup.query.get(n)
            group_row.name = getattr(form, f'group_{n}').data
            group_row.sort_mode = getattr(form, f'sort_{n}').data
        db.session.commit()
        flash('Настройки групп сохранены', 'success')
    else:
        flash('Не удалось сохранить настройки групп', 'danger')
    return redirect(url_for('admin.statuses_list'))


@admin_bp.route('/statuses/new', methods=['GET', 'POST'])
@superadmin_required
def status_new():
    form = StatusForm()
    form.group.choices = [(n, name) for n, name in get_group_names().items()]
    if request.method == 'GET':
        form.order.data = (db.session.query(db.func.max(Status.order)).scalar() or 0) + 1
        form.is_active.data = True
    if form.validate_on_submit():
        status = Status(
            name=form.name.data,
            order=form.order.data,
            color=form.color.data or None,
            group=form.group.data,
            is_default=form.is_default.data,
            is_active=form.is_active.data,
            is_final=form.is_final.data,
        )
        db.session.add(status)
        db.session.commit()
        _ensure_single_default(status)
        flash('Статус создан', 'success')
        return redirect(url_for('admin.statuses_list'))
    return render_template('admin/status_form.html', form=form, status=None)


@admin_bp.route('/statuses/<int:status_id>/edit', methods=['GET', 'POST'])
@superadmin_required
def status_edit(status_id):
    status = Status.query.get_or_404(status_id)
    form = StatusForm(obj=status)
    form.group.choices = [(n, name) for n, name in get_group_names().items()]
    if form.validate_on_submit():
        was_default = status.is_default
        status.name = form.name.data
        status.order = form.order.data
        status.color = form.color.data or None
        status.group = form.group.data
        status.is_active = form.is_active.data
        status.is_final = form.is_final.data
        if was_default and not form.is_default.data:
            flash('Нельзя снять флаг «начальный» — сначала назначьте начальным другой статус', 'warning')
            status.is_default = True
        else:
            status.is_default = form.is_default.data
        db.session.commit()
        _ensure_single_default(status)
        flash('Статус обновлён', 'success')
        return redirect(url_for('admin.statuses_list'))
    return render_template('admin/status_form.html', form=form, status=status)


@admin_bp.route('/statuses/<int:status_id>/delete', methods=['POST'])
@superadmin_required
def status_delete(status_id):
    status = Status.query.get_or_404(status_id)
    if status.in_use:
        flash('Нельзя удалить статус, который используется тикетами — деактивируйте его', 'danger')
    elif status.is_default:
        flash('Нельзя удалить начальный статус', 'danger')
    else:
        db.session.delete(status)
        db.session.commit()
        flash('Статус удалён', 'success')
    return redirect(url_for('admin.statuses_list'))


@admin_bp.route('/statuses/<int:status_id>/move/<direction>', methods=['POST'])
@superadmin_required
def status_move(status_id, direction):
    status = Status.query.get_or_404(status_id)
    # Порядок переставляется только внутри той же группы — группы это
    # отдельные блоки в списках, смешивать сортировку между ними не нужно.
    siblings = Status.query.filter_by(group=status.group).order_by(Status.order).all()
    idx = next(i for i, s in enumerate(siblings) if s.id == status_id)
    swap_idx = idx - 1 if direction == 'up' else idx + 1
    if 0 <= swap_idx < len(siblings):
        siblings[idx].order, siblings[swap_idx].order = siblings[swap_idx].order, siblings[idx].order
        db.session.commit()
    return redirect(url_for('admin.statuses_list'))


# ---------- Трекеры ----------

@admin_bp.route('/trackers')
@superadmin_required
def trackers_list():
    trackers = Tracker.query.order_by(Tracker.order).all()
    return render_template('admin/trackers_list.html', trackers=trackers)


@admin_bp.route('/trackers/new', methods=['GET', 'POST'])
@superadmin_required
def tracker_new():
    form = TrackerForm()
    if request.method == 'GET':
        form.order.data = (db.session.query(db.func.max(Tracker.order)).scalar() or 0) + 1
        form.is_active.data = True
    if form.validate_on_submit():
        tracker = Tracker(name=form.name.data, order=form.order.data, is_active=form.is_active.data)
        db.session.add(tracker)
        db.session.commit()
        flash('Категория создана', 'success')
        return redirect(url_for('admin.trackers_list'))
    return render_template('admin/tracker_form.html', form=form, tracker=None)


@admin_bp.route('/trackers/<int:tracker_id>/edit', methods=['GET', 'POST'])
@superadmin_required
def tracker_edit(tracker_id):
    tracker = Tracker.query.get_or_404(tracker_id)
    form = TrackerForm(obj=tracker)
    if form.validate_on_submit():
        tracker.name = form.name.data
        tracker.order = form.order.data
        tracker.is_active = form.is_active.data
        db.session.commit()
        flash('Категория обновлена', 'success')
        return redirect(url_for('admin.trackers_list'))
    return render_template('admin/tracker_form.html', form=form, tracker=tracker)


@admin_bp.route('/trackers/<int:tracker_id>/delete', methods=['POST'])
@superadmin_required
def tracker_delete(tracker_id):
    tracker = Tracker.query.get_or_404(tracker_id)
    if tracker.in_use:
        flash('Нельзя удалить категорию, которая используется тикетами — деактивируйте её', 'danger')
    else:
        db.session.delete(tracker)
        db.session.commit()
        flash('Категория удалена', 'success')
    return redirect(url_for('admin.trackers_list'))


@admin_bp.route('/trackers/<int:tracker_id>/move/<direction>', methods=['POST'])
@superadmin_required
def tracker_move(tracker_id, direction):
    trackers = Tracker.query.order_by(Tracker.order).all()
    idx = next((i for i, t in enumerate(trackers) if t.id == tracker_id), None)
    if idx is None:
        abort(404)
    swap_idx = idx - 1 if direction == 'up' else idx + 1
    if 0 <= swap_idx < len(trackers):
        trackers[idx].order, trackers[swap_idx].order = trackers[swap_idx].order, trackers[idx].order
        db.session.commit()
    return redirect(url_for('admin.trackers_list'))


# ---------- Файлы ----------

@admin_bp.route('/files')
@superadmin_required
def files_list():
    sort = request.args.get('sort', 'date')
    query = Attachment.query
    query = query.order_by(Attachment.size_bytes.desc()) if sort == 'size' else query.order_by(Attachment.created_at.desc())
    attachments = query.all()
    total_size = sum(a.size_bytes for a in attachments)
    return render_template('admin/files_list.html', attachments=attachments, total_size=total_size, sort=sort)


@admin_bp.route('/files/<int:attachment_id>/delete', methods=['POST'])
@superadmin_required
def file_delete(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    delete_attachment_file(attachment)
    db.session.delete(attachment)
    db.session.commit()
    flash('Файл удалён', 'success')
    return redirect(url_for('admin.files_list'))


# ---------- Настройки ----------

@admin_bp.route('/settings', methods=['GET', 'POST'])
@superadmin_required
def settings_page():
    settings = Settings.query.first()
    form = SettingsForm(obj=settings)
    test_form = TestEmailForm()
    if request.method == 'GET':
        form.smtp_password.data = ''

    if form.validate_on_submit():
        settings.smtp_host = form.smtp_host.data or None
        settings.smtp_port = form.smtp_port.data
        settings.smtp_username = form.smtp_username.data or None
        if form.smtp_password.data:
            settings.smtp_password_encrypted = encrypt_secret(form.smtp_password.data)
        settings.smtp_from_address = form.smtp_from_address.data or None
        settings.smtp_use_tls = form.smtp_use_tls.data
        settings.smtp_use_ssl = form.smtp_use_ssl.data
        settings.base_url = form.base_url.data
        settings.max_upload_mb = form.max_upload_mb.data
        normalized_ext = [e.strip().lower().lstrip('.') for e in form.allowed_extensions.data.split(',') if e.strip()]
        settings.allowed_extensions = ','.join(dict.fromkeys(normalized_ext))
        settings.site_name = form.site_name.data
        if form.favicon.data:
            old_favicon = settings.favicon_filename
            settings.favicon_filename = save_favicon_file(form.favicon.data)
            delete_favicon_file(old_favicon)
        db.session.commit()
        refresh_max_content_length(current_app._get_current_object())
        flash('Настройки сохранены', 'success')
        return redirect(url_for('admin.settings_page'))

    return render_template('admin/settings.html', form=form, test_form=test_form)


@admin_bp.route('/settings/test-email', methods=['POST'])
@superadmin_required
def settings_test_email():
    test_form = TestEmailForm()
    settings = Settings.query.first()
    if test_form.validate_on_submit():
        if not settings or not settings.smtp_host:
            flash('Сначала заполните и сохраните настройки SMTP', 'danger')
        else:
            try:
                send_test_email(settings, test_form.to_address.data)
                flash(f'Тестовое письмо отправлено на {test_form.to_address.data}', 'success')
            except Exception as e:
                flash(f'Не удалось отправить письмо: {e}', 'danger')
    return redirect(url_for('admin.settings_page'))


# ---------- Шаблоны писем ----------

@admin_bp.route('/email-templates')
@superadmin_required
def email_templates_list():
    templates = EmailTemplate.query.order_by(EmailTemplate.name).all()
    return render_template('admin/email_templates_list.html', templates=templates)


@admin_bp.route('/email-templates/<int:template_id>/edit', methods=['GET', 'POST'])
@superadmin_required
def email_template_edit(template_id):
    template = EmailTemplate.query.get_or_404(template_id)
    form = EmailTemplateForm(obj=template)
    if form.validate_on_submit():
        template.subject = form.subject.data
        template.body_html = clean_html(form.body_html.data)
        db.session.commit()
        flash('Шаблон письма сохранён', 'success')
        return redirect(url_for('admin.email_templates_list'))
    return render_template('admin/email_template_form.html', form=form, template=template)
