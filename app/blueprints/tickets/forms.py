from flask_wtf import FlaskForm
from wtforms import TextAreaField, SelectField, DateField
from wtforms.validators import DataRequired, Optional
from wtforms.widgets import HiddenInput

from ...richtext import validate_nonempty_richtext


class CommentForm(FlaskForm):
    body = TextAreaField('Комментарий', widget=HiddenInput(), validators=[validate_nonempty_richtext])


class DescriptionEditForm(FlaskForm):
    description = TextAreaField('Описание', widget=HiddenInput(), validators=[validate_nonempty_richtext])


class StatusChangeForm(FlaskForm):
    status_id = SelectField('Статус', coerce=int, validators=[DataRequired()])


class AssigneeChangeForm(FlaskForm):
    assignee_id = SelectField('Исполнитель', coerce=int, validators=[DataRequired()])


class DeadlineChangeForm(FlaskForm):
    deadline = DateField('Дедлайн', validators=[Optional()])


class TrackerChangeForm(FlaskForm):
    tracker_id = SelectField('Трекер', coerce=int, validators=[DataRequired()])
