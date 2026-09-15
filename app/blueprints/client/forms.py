from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DateField, SelectField
from wtforms.validators import DataRequired, Optional, Length
from wtforms.widgets import HiddenInput

from ...richtext import validate_nonempty_richtext


class TicketCreateForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired(message='Введите название'), Length(max=200)])
    description = TextAreaField('Описание', widget=HiddenInput(), validators=[validate_nonempty_richtext])
    deadline = DateField('Дедлайн', validators=[Optional()])
    tracker_id = SelectField('Трекер', coerce=int, validators=[DataRequired(message='Выберите трекер')])
