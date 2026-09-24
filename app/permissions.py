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


def can_change_priority(user, ticket):
    """Приоритет, в отличие от статуса/дедлайна/категории, может менять и
    сам постановщик — причём в любой момент, независимо от статуса тикета
    (без ограничения "только в начальном статусе", как у описания)."""
    if can_manage_ticket_fields(user, ticket):
        return True
    return user is not None and user.role == 'client' and ticket.client_id == user.id


def can_advance_status(user, ticket):
    """Кнопка автоперехода статуса ("Проверено" и т.п.) — видна только
    постановщику, и только пока текущий статус тикета её предусматривает."""
    if user is None or user.role != 'client' or ticket.client_id != user.id:
        return False
    return ticket.status.auto_advance_enabled and bool(ticket.status.auto_advance_button_text)


def can_revert_status(user, ticket):
    """Кнопка возврата на доработку ("На доработку" и т.п.) — тот же
    механизм, что и автопереход, только в обратную сторону по порядку
    статусов."""
    if user is None or user.role != 'client' or ticket.client_id != user.id:
        return False
    return ticket.status.auto_revert_enabled and bool(ticket.status.auto_revert_button_text)


def can_reassign_ticket(user):
    return user is not None and user.role == 'admin' and user.is_superadmin


def can_delete_ticket(user):
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
    """В финальном статусе (Готов/Отменён и т.п.) постановщик писать не может —
    админ по-прежнему может добавить финальную заметку."""
    if not can_view_ticket(user, ticket):
        return False
    if user.role == 'client' and ticket.status.is_final:
        return False
    return True
