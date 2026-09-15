"""
Санитайзинг HTML из простого WYSIWYG-редактора (описание тикета,
комментарии) + автоматическое превращение голых ссылок в кликабельные.

Разрешён очень небольшой набор тегов — ровно то, что даёт наш редактор
(bold/italic/underline/список/ссылка). Всё остальное (script, style,
атрибуты вроде onclick и т.д.) обрезается bleach'ем.
"""
import bleach
from wtforms.validators import ValidationError

ALLOWED_TAGS = ['p', 'br', 'b', 'strong', 'i', 'em', 'u', 'ul', 'ol', 'li', 'a', 'div']
ALLOWED_ATTRIBUTES = {'a': ['href', 'title']}
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']


def clean_html(raw_html):
    """Сохраняем в БД уже очищенным — на случай если сервер отдаёт это
    напрямую в обход рендер-фильтра где-то ещё."""
    return bleach.clean(
        raw_html or '',
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )


def _link_attrs(attrs, new=False):
    attrs[(None, 'target')] = '_blank'
    attrs[(None, 'rel')] = 'noopener noreferrer nofollow'
    return attrs


def render_richtext(html):
    """Используется во ВСЕХ местах вывода описания/комментария (фильтр
    Jinja `richtext`). Чистит ещё раз (идемпотентно — не ломает уже чистый
    HTML) и добавляет линкификацию голых URL. Повторная чистка здесь — не
    паранойя, а единственная защита для тикетов/комментариев, созданных ДО
    появления WYSIWYG-редактора: та старая plain-text могла содержать
    произвольные `<`/`>`, и раньше это было безопасно только потому, что
    шаблон не помечал её `|safe`. Теперь помечаем — так что чистим здесь."""
    cleaned = clean_html(html)
    return bleach.linkify(cleaned, callbacks=[_link_attrs])


def html_to_text(html):
    return bleach.clean(html or '', tags=[], strip=True).strip()


def validate_nonempty_richtext(form, field):
    if not html_to_text(field.data):
        raise ValidationError('Введите текст')
