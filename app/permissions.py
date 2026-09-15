"""Проверки доступа к тикетам/вложениям, общие для нескольких blueprint'ов."""


def can_view_ticket(user, ticket):
    if user is None:
        return False
    if user.role == 'client':
        return ticket.client_id == user.id
    if user.role == 'admin':
        return user.is_superadmin or ticket.assignee_id == user.id
    return False


def can_manage_ticket_fields(user, ticket):
    """Статус / дедлайн / трекер — свой исполнитель или суперадмин."""
    return user is not None and user.role == 'admin' and (user.is_superadmin or ticket.assignee_id == user.id)


def can_reassign_ticket(user):
    return user is not None and user.role == 'admin' and user.is_superadmin


def can_edit_description(user, ticket):
    return (
        user is not None
        and user.role == 'client'
        and ticket.client_id == user.id
        and ticket.status.is_default
    )


def can_view_attachment(user, attachment):
    ticket = attachment.parent_ticket
    return ticket is not None and can_view_ticket(user, ticket)


def can_comment(user, ticket):
    """В финальном статусе (Готов/Отменён и т.п.) клиент писать не может —
    админ по-прежнему может добавить финальную заметку."""
    if not can_view_ticket(user, ticket):
        return False
    if user.role == 'client' and ticket.status.is_final:
        return False
    return True
