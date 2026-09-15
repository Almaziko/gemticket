from flask_wtf import FlaskForm
from wtforms import PasswordField
from wtforms.validators import DataRequired


class LoginForm(FlaskForm):
    password = PasswordField('Пароль', validators=[DataRequired(message='Введите пароль')])
