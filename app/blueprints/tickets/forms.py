from flask_wtf import FlaskForm
from wtforms import TextAreaField, SelectField, DateField
from wtforms.validators import DataRequired, Optional


class CommentForm(FlaskForm):
    body = TextAreaField('Комментарий', validators=[DataRequired(message='Введите текст комментария')])


class DescriptionEditForm(FlaskForm):
    description = TextAreaField('Описание', validators=[DataRequired(message='Введите описание')])


class StatusChangeForm(FlaskForm):
    status_id = SelectField('Статус', coerce=int, validators=[DataRequired()])


class AssigneeChangeForm(FlaskForm):
    assignee_id = SelectField('Исполнитель', coerce=int, validators=[DataRequired()])


class DeadlineChangeForm(FlaskForm):
    deadline = DateField('Дедлайн', validators=[Optional()])


class TrackerChangeForm(FlaskForm):
    tracker_id = SelectField('Трекер', coerce=int, validators=[DataRequired()])
