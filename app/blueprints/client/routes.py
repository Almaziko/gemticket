from flask import Blueprint, render_template, redirect, url_for, request, flash, g

from ...extensions import db
from ...models import Ticket, Status, Tracker
from ...decorators import client_required
from ...attachments import (
    check_files_size, check_files_extensions, save_attachments,
    FileTooLargeError, DisallowedExtensionError,
)
from ...richtext import clean_html
from ...history import record_event
from ...grouping import group_by_status_group, get_group_names
from ... import notifications as notif
from .forms import TicketCreateForm

client_bp = Blueprint('client', __name__, url_prefix='/client')


@client_bp.route('/tickets')
@client_required
def tickets_list():
    status_filter = request.args.get('status', type=int)
    search = (request.args.get('q') or '').strip()
    query = Ticket.query.filter_by(client_id=g.current_user.id)
    if status_filter:
        query = query.filter_by(status_id=status_filter)
    if search:
        query = query.filter(Ticket.title.ilike(f'%{search}%'))
    tickets = query.order_by(Ticket.priority.desc(), Ticket.created_at.desc()).all()
    statuses = Status.query.order_by(Status.order).all()
    ticket_groups = group_by_status_group(tickets, lambda t: t.status)
    status_groups = group_by_status_group(statuses, lambda s: s)
    return render_template(
        'client/tickets_list.html', tickets=tickets, statuses=statuses,
        ticket_groups=ticket_groups, status_groups=status_groups, group_names=get_group_names(),
        status_filter=status_filter, search=search,
    )


@client_bp.route('/tickets/new', methods=['GET', 'POST'])
@client_required
def ticket_new():
    form = TicketCreateForm()
    form.tracker_id.choices = [
        (t.id, t.name) for t in Tracker.query.filter_by(is_active=True).order_by(Tracker.order).all()
    ]

    if form.validate_on_submit():
        files = request.files.getlist('attachments')
        try:
            check_files_size(files)
            check_files_extensions(files)
        except FileTooLargeError as e:
            flash(f'Файл «{e.filename}» превышает лимит {e.limit_mb} МБ. Тикет не создан.', 'danger')
            return render_template('client/ticket_new.html', form=form)
        except DisallowedExtensionError as e:
            flash(f'Файл «{e.filename}» имеет неразрешённое расширение. Разрешены: {", ".join(e.allowed)}.', 'danger')
            return render_template('client/ticket_new.html', form=form)

        default_status = Status.query.filter_by(is_default=True).first()
        ticket = Ticket(
            title=form.title.data,
            description=clean_html(form.description.data),
            deadline=form.deadline.data,
            tracker_id=form.tracker_id.data,
            priority=form.priority.data,
            status_id=default_status.id,
            client_id=g.current_user.id,
            assignee_id=g.current_user.assigned_admin_id,
        )
        db.session.add(ticket)
        db.session.flush()
        save_attachments(files, g.current_user, ticket=ticket)
        db.session.commit()
        notif.notify_ticket_created(ticket)
        record_event(ticket, g.current_user, f'{g.current_user.name} создал(а) тикет')
        flash('Тикет создан', 'success')
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))

    return render_template('client/ticket_new.html', form=form)
