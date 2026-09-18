from flask_wtf import FlaskForm
from wtforms import TextAreaField, SelectField, DateField
from wtforms.validators import DataRequired, Optional

from ...models import PRIORITY_CHOICES
from ...richtext import validate_nonempty_richtext

# Без widget=HiddenInput() на body/description — иначе form.hidden_tag()
# (без аргументов сканирует все поля формы) рендерит их ещё раз сам по
# себе, вторым <input> с тем же name, всегда пустым, который сервер читает
# вместо настоящего значения из richtext-редактора (см. richtext_macro.html,
# где скрытый инпут для этих полей рисуется вручную).


class CommentForm(FlaskForm):
    body = TextAreaField('Комментарий', validators=[validate_nonempty_richtext])


class DescriptionEditForm(FlaskForm):
    description = TextAreaField('Описание', validators=[validate_nonempty_richtext])


class StatusChangeForm(FlaskForm):
    status_id = SelectField('Статус', coerce=int, validators=[DataRequired()])


class AssigneeChangeForm(FlaskForm):
    assignee_id = SelectField('Исполнитель', coerce=int, validators=[DataRequired()])


class DeadlineChangeForm(FlaskForm):
    deadline = DateField('Дедлайн', validators=[Optional()])


class TrackerChangeForm(FlaskForm):
    tracker_id = SelectField('Категория', coerce=int, validators=[DataRequired()])


class PriorityChangeForm(FlaskForm):
    priority = SelectField('Приоритет', choices=PRIORITY_CHOICES, coerce=int, validators=[DataRequired()])
