from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, g, abort,
    send_from_directory, current_app
)

from ...extensions import db
from ...models import (
    Ticket, Comment, Attachment, Status, Tracker, Admin, Notification, Settings,
    get_next_status, get_previous_status,
)
from ... import s3_storage
from ...decorators import login_required, superadmin_required
from ...permissions import (
    can_view_ticket, can_manage_ticket_fields, can_reassign_ticket, can_delete_ticket,
    can_edit_description, can_view_attachment, can_comment, can_change_priority,
    can_advance_status, can_revert_status,
)
from ...attachments import (
    check_files_size, check_files_extensions, save_attachments, delete_attachment_file,
    FileTooLargeError, DisallowedExtensionError,
)
from ...richtext import clean_html
from ...history import record_event
from ... import notifications as notif
from .forms import (
    CommentForm, DescriptionEditForm, StatusChangeForm, AssigneeChangeForm,
    DeadlineChangeForm, TrackerChangeForm, PriorityChangeForm, Bitrix24UrlForm,
)

tickets_bp = Blueprint('tickets', __name__)


def _get_ticket_or_403(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if not can_view_ticket(g.current_user, ticket):
        abort(403)
    return ticket


def _render_detail(ticket, comment_form=None, description_form=None):
    """Общий рендер страницы тикета. Принимает опционально уже заполненные
    (и, возможно, содержащие ошибки валидации) comment_form/description_form —
    так при ошибке (например, недопустимое вложение к комментарию) можно
    перерисовать форму с тем же введённым текстом вместо редиректа, который
    его бы стёр."""
    statuses = Status.query.filter_by(is_active=True).order_by(Status.order).all()
    if ticket.status not in statuses:
        statuses.append(ticket.status)
    trackers = Tracker.query.filter_by(is_active=True).order_by(Tracker.order).all()
    if ticket.tracker not in trackers:
        trackers.append(ticket.tracker)
    admins = Admin.query.order_by(Admin.name).all()

    status_form = StatusChangeForm(status_id=ticket.status_id)
    status_form.status_id.choices = [(s.id, s.name) for s in statuses]
    tracker_form = TrackerChangeForm(tracker_id=ticket.tracker_id)
    tracker_form.tracker_id.choices = [(t.id, t.name) for t in trackers]
    assignee_form = AssigneeChangeForm(assignee_id=ticket.assignee_id)
    assignee_form.assignee_id.choices = [(a.id, a.name) for a in admins]
    deadline_form = DeadlineChangeForm(deadline=ticket.deadline)
    priority_form = PriorityChangeForm(priority=ticket.priority)
    bitrix24_form = Bitrix24UrlForm(bitrix24_url=ticket.bitrix24_url)

    if description_form is None:
        description_form = DescriptionEditForm(description=ticket.description)
    if comment_form is None:
        comment_form = CommentForm()

    return render_template(
        'tickets/detail.html',
        ticket=ticket,
        status_form=status_form,
        tracker_form=tracker_form,
        assignee_form=assignee_form,
        deadline_form=deadline_form,
        priority_form=priority_form,
        bitrix24_form=bitrix24_form,
        description_form=description_form,
        comment_form=comment_form,
        can_manage=can_manage_ticket_fields(g.current_user, ticket),
        can_change_priority=can_change_priority(g.current_user, ticket),
        can_advance_status=can_advance_status(g.current_user, ticket),
        can_revert_status=can_revert_status(g.current_user, ticket),
        can_reassign=can_reassign_ticket(g.current_user),
        can_delete=can_delete_ticket(g.current_user),
        can_edit_desc=can_edit_description(g.current_user, ticket),
        can_comment=can_comment(g.current_user, ticket),
    )


@tickets_bp.route('/tickets/<int:ticket_id>')
@login_required
def detail(ticket_id):
    ticket = _get_ticket_or_403(ticket_id)
    return _render_detail(ticket)


@tickets_bp.route('/tickets/<int:ticket_id>/comment', methods=['POST'])
@login_required
def add_comment(ticket_id):
    ticket = _get_ticket_or_403(ticket_id)
    if not can_comment(g.current_user, ticket):
        abort(403)
    form = CommentForm()
    if form.validate_on_submit():
        files = request.files.getlist('attachments')
        try:
            check_files_size(files)
            check_files_extensions(files)
        except FileTooLargeError as e:
            flash(f'Файл «{e.filename}» превышает лимит {e.limit_mb} МБ. Комментарий не сохранён.', 'danger')
            return _render_detail(ticket, comment_form=form)
        except DisallowedExtensionError as e:
            flash(f'Файл «{e.filename}» имеет неразрешённое расширение. Разрешены: {", ".join(e.allowed)}.', 'danger')
            return _render_detail(ticket, comment_form=form)

        comment = Comment(ticket_id=ticket.id, author_id=g.current_user.id, body=clean_html(form.body.data))
        db.session.add(comment)
        db.session.flush()
        save_attachments(files, g.current_user, comment=comment)
        db.session.commit()
        notif.notify_comment_added(ticket, g.current_user)
        flash('Комментарий добавлен', 'success')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id) + '#comments')

    flash('Не удалось добавить комментарий', 'danger')
    return _render_detail(ticket, comment_form=form)


@tickets_bp.route('/tickets/<int:ticket_id>/description', methods=['POST'])
@login_required
def edit_description(ticket_id):
    ticket = _get_ticket_or_403(ticket_id)
    if not can_edit_description(g.current_user, ticket):
        abort(403)
    form = DescriptionEditForm()
    if form.validate_on_submit():
        files = request.files.getlist('attachments')
        try:
            check_files_size(files)
            check_files_extensions(files)
        except FileTooLargeError as e:
            flash(f'Файл «{e.filename}» превышает лимит {e.limit_mb} МБ. Описание не сохранено.', 'danger')
            return _render_detail(ticket, description_form=form)
        except DisallowedExtensionError as e:
            flash(f'Файл «{e.filename}» имеет неразрешённое расширение. Разрешены: {", ".join(e.allowed)}.', 'danger')
            return _render_detail(ticket, description_form=form)

        ticket.description = clean_html(form.description.data)
        save_attachments(files, g.current_user, ticket=ticket)
        db.session.commit()
        notif.notify_ticket_edited_by_client(ticket)
        record_event(ticket, g.current_user, f'{g.current_user.name} отредактировал(а) описание')
        flash('Описание обновлено', 'success')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))

    flash('Не удалось сохранить описание', 'danger')
    return _render_detail(ticket, description_form=form)


@tickets_bp.route('/attachments/<int:attachment_id>/delete', methods=['POST'])
@login_required
def delete_attachment(attachment_id):
    """Удалить вложение тикета может только сам постановщик и только в том
    же окне, когда ему доступно редактирование описания (тикет в начальном
    статусе) — то есть ровно тем же условием, что и can_edit_description.
    Вложения к комментариям сюда не попадают: attachment.ticket_id у них
    пустой, у комментария своя лента и трогать её задним числом нельзя."""
    attachment = Attachment.query.get_or_404(attachment_id)
    ticket = attachment.parent_ticket
    if ticket is None or attachment.ticket_id is None or not can_edit_description(g.current_user, ticket):
        abort(403)
    delete_attachment_file(attachment)
    db.session.delete(attachment)
    db.session.commit()
    flash('Вложение удалено', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


def _apply_status_change(ticket, new_status, actor, notify_recipient=None):
    """Общая логика смены статуса — используется и ручным выбором статуса
    исполнителем, и кнопкой автоперехода у постановщика. Инициатором в
    истории всегда становится actor (тот, кто нажал/выбрал). notify_recipient
    переопределяет получателя email/колокольчика (по умолчанию — постановщик);
    кнопка автоперехода передаёт сюда исполнителя, т.к. иначе постановщик
    получал бы письмо о своём же собственном действии."""
    old_name = ticket.status.name
    was_final = ticket.status.is_final
    ticket.status = new_status
    if new_status.is_final and not was_final:
        ticket.closed_at = datetime.now()
    elif not new_status.is_final and was_final:
        ticket.closed_at = None
    db.session.commit()
    notif.notify_status_changed(ticket, old_name, new_status.name, recipient=notify_recipient)
    record_event(ticket, actor, f'{actor.name} изменил(а) статус с «{old_name}» на «{new_status.name}»')


@tickets_bp.route('/tickets/<int:ticket_id>/status', methods=['POST'])
@login_required
def change_status(ticket_id):
    ticket = _get_ticket_or_403(ticket_id)
    if not can_manage_ticket_fields(g.current_user, ticket):
        abort(403)
    form = StatusChangeForm()
    form.status_id.choices = [(s.id, s.name) for s in Status.query.all()]
    if form.validate_on_submit():
        new_status = Status.query.get(form.status_id.data)
        if new_status and new_status.id != ticket.status_id:
            _apply_status_change(ticket, new_status, g.current_user)
            flash('Статус обновлён', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/tickets/<int:ticket_id>/advance-status', methods=['POST'])
@login_required
def advance_status(ticket_id):
    """Кнопка автоперехода у постановщика ("Проверено" и т.п.) — переводит
    тикет на следующий статус по общему порядку списка статусов, без выбора
    конкретного статуса вручную."""
    ticket = _get_ticket_or_403(ticket_id)
    if not can_advance_status(g.current_user, ticket):
        abort(403)
    next_status = get_next_status(ticket.status)
    if next_status is None:
        flash('Следующий статус не найден — обратитесь к администратору', 'danger')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
    _apply_status_change(ticket, next_status, g.current_user, notify_recipient=ticket.assignee)
    flash('Статус обновлён', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/tickets/<int:ticket_id>/revert-status', methods=['POST'])
@login_required
def revert_status(ticket_id):
    """Кнопка возврата на доработку у постановщика — переводит тикет на
    предыдущий статус по общему порядку списка статусов."""
    ticket = _get_ticket_or_403(ticket_id)
    if not can_revert_status(g.current_user, ticket):
        abort(403)
    previous_status = get_previous_status(ticket.status)
    if previous_status is None:
        flash('Предыдущий статус не найден — обратитесь к администратору', 'danger')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
    _apply_status_change(ticket, previous_status, g.current_user, notify_recipient=ticket.assignee)
    flash('Статус обновлён', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/tickets/<int:ticket_id>/tracker', methods=['POST'])
@login_required
def change_tracker(ticket_id):
    ticket = _get_ticket_or_403(ticket_id)
    if not can_manage_ticket_fields(g.current_user, ticket):
        abort(403)
    form = TrackerChangeForm()
    form.tracker_id.choices = [(t.id, t.name) for t in Tracker.query.all()]
    if form.validate_on_submit():
        new_tracker = Tracker.query.get(form.tracker_id.data)
        if new_tracker and new_tracker.id != ticket.tracker_id:
            old_name = ticket.tracker.name
            ticket.tracker = new_tracker
            db.session.commit()
            notif.notify_tracker_changed(ticket, old_name, new_tracker.name)
            record_event(ticket, g.current_user, f'{g.current_user.name} изменил(а) категорию с «{old_name}» на «{new_tracker.name}»')
            flash('Категория обновлена', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/tickets/<int:ticket_id>/priority', methods=['POST'])
@login_required
def change_priority(ticket_id):
    ticket = _get_ticket_or_403(ticket_id)
    if not can_change_priority(g.current_user, ticket):
        abort(403)
    form = PriorityChangeForm()
    if form.validate_on_submit():
        if form.priority.data != ticket.priority:
            old_label = ticket.priority_label
            ticket.priority = form.priority.data
            db.session.commit()
            notif.notify_priority_changed(ticket, old_label, ticket.priority_label)
            record_event(ticket, g.current_user, f'{g.current_user.name} изменил(а) приоритет с «{old_label}» на «{ticket.priority_label}»')
            flash('Приоритет обновлён', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/tickets/<int:ticket_id>/deadline', methods=['POST'])
@login_required
def change_deadline(ticket_id):
    ticket = _get_ticket_or_403(ticket_id)
    if not can_manage_ticket_fields(g.current_user, ticket):
        abort(403)
    form = DeadlineChangeForm()
    if form.validate_on_submit():
        old_value = ticket.deadline.strftime('%d.%m.%Y') if ticket.deadline else 'не задан'
        ticket.deadline = form.deadline.data
        new_value = ticket.deadline.strftime('%d.%m.%Y') if ticket.deadline else 'не задан'
        ticket.overdue_notified = False
        db.session.commit()
        if old_value != new_value:
            notif.notify_deadline_changed(ticket, old_value, new_value)
            record_event(ticket, g.current_user, f'{g.current_user.name} изменил(а) дедлайн с «{old_value}» на «{new_value}»')
        flash('Дедлайн обновлён', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/tickets/<int:ticket_id>/bitrix24', methods=['POST'])
@login_required
def change_bitrix24(ticket_id):
    """Произвольная внешняя ссылка (CRM-задача, таблица и т.п.) — служебное
    поле, видно и редактируется только исполнителем/суперадмином
    (постановщик его вообще не видит), поэтому в отличие от остальных полей
    "Управление" здесь не пишем ни уведомление, ни запись в историю (её
    видит и постановщик тоже) — сохранение самой ссылки никого больше
    не касается."""
    ticket = _get_ticket_or_403(ticket_id)
    if not can_manage_ticket_fields(g.current_user, ticket):
        abort(403)
    form = Bitrix24UrlForm()
    if form.validate_on_submit():
        ticket.bitrix24_url = form.bitrix24_url.data or None
        db.session.commit()
        flash('Ссылка сохранена', 'success')
    else:
        flash('Не удалось сохранить ссылку — проверьте формат (нужен http:// или https://)', 'danger')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/tickets/<int:ticket_id>/assignee', methods=['POST'])
@login_required
def change_assignee(ticket_id):
    ticket = _get_ticket_or_403(ticket_id)
    if not can_reassign_ticket(g.current_user):
        abort(403)
    form = AssigneeChangeForm()
    form.assignee_id.choices = [(a.id, a.name) for a in Admin.query.all()]
    if form.validate_on_submit():
        new_assignee = Admin.query.get(form.assignee_id.data)
        if new_assignee and new_assignee.id != ticket.assignee_id:
            old_name = ticket.assignee.name
            ticket.assignee = new_assignee
            db.session.commit()
            notif.notify_assignee_changed(ticket, old_name, new_assignee.name)
            record_event(ticket, g.current_user, f'{g.current_user.name} изменил(а) исполнителя с «{old_name}» на «{new_assignee.name}»')
            flash('Исполнитель обновлён', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/tickets/<int:ticket_id>/delete', methods=['POST'])
@superadmin_required
def delete_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    attachments = list(ticket.attachments)
    for comment in ticket.comments:
        attachments.extend(comment.attachments)
    for attachment in attachments:
        delete_attachment_file(attachment)

    title = ticket.title
    db.session.delete(ticket)
    db.session.commit()
    flash(f'Тикет «{title}» удалён', 'success')
    return redirect(url_for('admin.dashboard'))


@tickets_bp.route('/attachments/<int:attachment_id>/download')
@login_required
def download_attachment(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    if not can_view_attachment(g.current_user, attachment):
        abort(403)
    if attachment.storage == 's3':
        url = s3_storage.generate_download_url(
            Settings.query.first(), attachment.filename_stored, attachment.filename_original,
            attachment.mime_type, as_attachment=not attachment.is_image,
        )
        return redirect(url)
    return send_from_directory(
        current_app.config['UPLOAD_DIR'],
        attachment.filename_stored,
        as_attachment=not attachment.is_image,
        download_name=attachment.filename_original,
    )


@tickets_bp.route('/notifications/<int:notification_id>/open')
@login_required
def open_notification(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.recipient_id != g.current_user.id:
        abort(403)
    notification.is_read = True
    db.session.commit()
    return redirect(url_for('tickets.detail', ticket_id=notification.ticket_id))


@tickets_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(recipient_id=g.current_user.id, is_read=False).update({Notification.is_read: True})
    db.session.commit()
    return redirect(request.referrer or url_for('auth.index'))
