"""Разбивка тикетов/статусов по группам статусов (см. models.STATUS_GROUPS)
для списков тикетов — общая логика для client- и admin-роутов."""
from .models import STATUS_GROUPS, StatusGroup, DEFAULT_STATUS_GROUP_NAMES


def get_group_names():
    """{номер группы: название} — с фолбэком на дефолт, если строка почему-то
    не засеялась (не должно происходить, но на всякий случай)."""
    rows = {g.number: g.name for g in StatusGroup.query.all()}
    return {n: rows.get(n, DEFAULT_STATUS_GROUP_NAMES[n]) for n in STATUS_GROUPS}


def group_by_status_group(items, status_getter):
    """items -> [(group_number, [items...]), ...], только непустые группы,
    в порядке group_number по возрастанию (1 первая, 5 последняя)."""
    groups = []
    for group_number in STATUS_GROUPS:
        bucket = [item for item in items if status_getter(item).group == group_number]
        if bucket:
            groups.append((group_number, bucket))
    return groups
