"""Разбивка тикетов/статусов по группам статусов (см. models.STATUS_GROUPS)
для списков тикетов — общая логика для client- и admin-роутов."""
from datetime import datetime

from .models import (
    STATUS_GROUPS, StatusGroup, DEFAULT_STATUS_GROUP_NAMES,
    SORT_MODE_CREATED_AT, SORT_MODE_CLOSED_AT, SORT_MODE_ID, DEFAULT_SORT_MODE,
)


def get_group_names():
    """{номер группы: название} — с фолбэком на дефолт, если строка почему-то
    не засеялась (не должно происходить, но на всякий случай)."""
    rows = {g.number: g.name for g in StatusGroup.query.all()}
    return {n: rows.get(n, DEFAULT_STATUS_GROUP_NAMES[n]) for n in STATUS_GROUPS}


def get_group_sort_modes():
    """{номер группы: режим сортировки}, с фолбэком на дефолт (по приоритету)."""
    rows = {g.number: g.sort_mode for g in StatusGroup.query.all()}
    return {n: rows.get(n, DEFAULT_SORT_MODE) for n in STATUS_GROUPS}


def _sort_key(ticket, mode):
    if mode == SORT_MODE_CREATED_AT:
        return ticket.created_at
    if mode == SORT_MODE_CLOSED_AT:
        # Ещё не закрытые тикеты уходят в конец при сортировке по убыванию.
        return ticket.closed_at or datetime.min
    if mode == SORT_MODE_ID:
        return ticket.id
    # SORT_MODE_PRIORITY (и любое неизвестное значение) — по умолчанию.
    return (ticket.priority, ticket.created_at)


def sort_tickets(tickets, mode):
    return sorted(tickets, key=lambda t: _sort_key(t, mode), reverse=True)


def group_by_status_group(items, status_getter):
    """items -> [(group_number, [items...]), ...], только непустые группы,
    в порядке group_number по возрастанию (1 первая, 5 последняя)."""
    groups = []
    for group_number in STATUS_GROUPS:
        bucket = [item for item in items if status_getter(item).group == group_number]
        if bucket:
            groups.append((group_number, bucket))
    return groups


def group_tickets_sorted(tickets):
    """group_by_status_group специально для тикетов: внутри каждого блока
    сортирует по режиму, настроенному для этой группы в админке."""
    sort_modes = get_group_sort_modes()
    groups = group_by_status_group(tickets, lambda t: t.status)
    return [
        (group_number, sort_tickets(group_tickets, sort_modes.get(group_number, DEFAULT_SORT_MODE)))
        for group_number, group_tickets in groups
    ]
