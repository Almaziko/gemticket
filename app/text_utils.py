"""Мелкие текстовые хелперы для шаблонов Jinja, не связанные с
WYSIWYG-санитайзингом (см. richtext.py)."""
import re

from markupsafe import Markup, escape

_VAR_RE = re.compile(r'(\{\{\s*[a-zA-Z0-9_]+\s*\}\})')


def highlight_template_vars(text):
    """Подсвечивает {{ variable }}-плейсхолдеры в теме/тексте письма
    пилюлей — используется в списке шаблонов писем, чтобы визуально
    было видно, где подставляются переменные."""
    parts = _VAR_RE.split(text or '')
    html = []
    for part in parts:
        if _VAR_RE.match(part):
            html.append('<span class="gt-var-chip">%s</span>' % escape(part))
        else:
            html.append(str(escape(part)))
    return Markup(''.join(html))
