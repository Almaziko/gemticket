from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, g, abort,
    send_from_directory, current_app
)

from ...extensions import db
from ...models import Ticket, Comment, Attachment, Status, Tracker, Admin, Notification
from ...decorators import login_required
from ...permissions import (
    can_view_ticket, can_manage_ticket_fields, can_reassign_ticket,
    can_edit_description, can_view_attachment,
)
from ...attachments import check_files_size, save_attachments, FileTooLargeError
from ... import notifications as notif
from .forms import (
    CommentForm, DescriptionEditForm, StatusChangeForm, AssigneeChangeForm,
    DeadlineChangeForm, TrackerChangeForm,
)

tickets_bp = Blueprint('tickets', __name__)


def _get_ticket_or_403(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if not can_view_ticket(g.current_user, ticket):
        abort(403)
    return ticket


@tickets_bp.route('/tickets/<int:ticket_id>')
@login_required
def detail(ticket_id):
    ticket = _get_ticket_or_403(ticket_id)

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
    description_form = DescriptionEditForm(description=ticket.description)
    comment_form = CommentForm()

    return render_template(
        'tickets/detail.html',
        ticket=ticket,
        status_form=status_form,
        tracker_form=tracker_form,
        assignee_form=assignee_form,
        deadline_form=deadline_form,
        description_form=description_form,
        comment_form=comment_form,
        can_manage=can_manage_ticket_fields(g.current_user, ticket),
        can_reassign=can_reassign_ticket(g.current_user),
        can_edit_desc=can_edit_description(g.current_user, ticket),
    )


@tickets_bp.route('/tickets/<int:ticket_id>/comment', methods=['POST'])
@login_required
def add_comment(ticket_id):
    ticket = _get_ticket_or_403(ticket_id)
    form = CommentForm()
    if form.validate_on_submit():
        files = request.files.getlist('attachments')
        try:
            check_files_size(files)
        except FileTooLargeError as e:
            flash(f'Файл «{e.filename}» превышает лимит {e.limit_mb} МБ. Комментарий не сохранён.', 'danger')
            return redirect(url_for('tickets.detail', ticket_id=ticket.id) + '#comments')

        comment = Comment(ticket_id=ticket.id, author_id=g.current_user.id, body=form.body.data)
        db.session.add(comment)
        db.session.flush()
        save_attachments(files, g.current_user, comment=comment)
        db.session.commit()
        notif.notify_comment_added(ticket, g.current_user)
        flash('Комментарий добавлен', 'success')
    else:
        flash('Не удалось добавить комментарий', 'danger')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id) + '#comments')


@tickets_bp.route('/tickets/<int:ticket_id>/description', methods=['POST'])
@login_required
def edit_description(ticket_id):
    ticket = _get_ticket_or_403(ticket_id)
    if not can_edit_description(g.current_user, ticket):
        abort(403)
    form = DescriptionEditForm()
    if form.validate_on_submit():
        ticket.description = form.description.data
        db.session.commit()
        notif.notify_ticket_edited_by_client(ticket)
        flash('Описание обновлено', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


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
            old_name = ticket.status.name
            ticket.status = new_status
            db.session.commit()
            notif.notify_status_changed(ticket, old_name, new_status.name)
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
            flash('Трекер обновлён', 'success')
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
        db.session.commit()
        if old_value != new_value:
            notif.notify_deadline_changed(ticket, old_value, new_value)
        flash('Дедлайн обновлён', 'success')
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
            flash('Исполнитель обновлён', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.id))


@tickets_bp.route('/attachments/<int:attachment_id>/download')
@login_required
def download_attachment(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    if not can_view_attachment(g.current_user, attachment):
        abort(403)
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
