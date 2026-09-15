from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DateField, SelectField
from wtforms.validators import DataRequired, Optional, Length


class TicketCreateForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired(message='Введите название'), Length(max=200)])
    description = TextAreaField('Описание', validators=[DataRequired(message='Введите описание')])
    deadline = DateField('Дедлайн', validators=[Optional()])
    tracker_id = SelectField('Трекер', coerce=int, validators=[DataRequired(message='Выберите трекер')])
