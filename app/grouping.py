"""Разбивка тикетов/статусов по группам статусов (см. models.STATUS_GROUPS)
для списков тикетов — общая логика для client- и admin-роутов."""
from .models import STATUS_GROUPS


def group_by_status_group(items, status_getter):
    """items -> [(group_number, [items...]), ...], только непустые группы,
    в порядке group_number по возрастанию (1 первая, 5 последняя)."""
    groups = []
    for group_number in STATUS_GROUPS:
        bucket = [item for item in items if status_getter(item).group == group_number]
        if bucket:
            groups.append((group_number, bucket))
    return groups
