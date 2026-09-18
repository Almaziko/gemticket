from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DateField, SelectField
from wtforms.validators import DataRequired, Optional, Length

from ...models import PRIORITY_CHOICES, PRIORITY_MEDIUM
from ...richtext import validate_nonempty_richtext


class TicketCreateForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired(message='Введите название'), Length(max=200)])
    # Без widget=HiddenInput(): такой виджет заставил бы form.hidden_tag()
    # (без аргументов сканирует все поля формы) рендерить это поле ещё раз
    # само по себе — вторым <input name="description">, всегда пустым,
    # который сервер бы читал вместо реального (см. richtext_macro.html,
    # где этот hidden-инпут рисуется вручную).
    description = TextAreaField('Описание', validators=[validate_nonempty_richtext])
    deadline = DateField('Дедлайн', validators=[Optional()])
    tracker_id = SelectField('Трекер', coerce=int, validators=[DataRequired(message='Выберите трекер')])
    priority = SelectField('Приоритет', choices=PRIORITY_CHOICES, coerce=int, default=PRIORITY_MEDIUM)
