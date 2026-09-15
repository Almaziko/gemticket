from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Optional, Length, Email, NumberRange


class ClientForm(FlaskForm):
    name = StringField('Имя', validators=[DataRequired(message='Введите имя'), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(message='Некорректный email'), Length(max=255)])
    password = PasswordField('Пароль', validators=[Optional(), Length(min=4, max=128)])
    assigned_admin_id = SelectField('Админ-исполнитель', coerce=int, validators=[DataRequired()])


class AdminForm(FlaskForm):
    name = StringField('Имя', validators=[DataRequired(message='Введите имя'), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(message='Некорректный email'), Length(max=255)])
    password = PasswordField('Пароль', validators=[Optional(), Length(min=4, max=128)])


class StatusForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired(), Length(max=80)])
    order = IntegerField('Порядок', validators=[DataRequired()])
    color = StringField('Цвет (bootstrap-класс: success/warning/danger/...)', validators=[Optional(), Length(max=20)])
    is_default = BooleanField('Начальный статус для новых тикетов')
    is_active = BooleanField('Активен')


class TrackerForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired(), Length(max=80)])
    order = IntegerField('Порядок', validators=[DataRequired()])
    is_active = BooleanField('Активен')


class SettingsForm(FlaskForm):
    smtp_host = StringField('SMTP host', validators=[Optional(), Length(max=255)])
    smtp_port = IntegerField('SMTP port', validators=[Optional(), NumberRange(min=1, max=65535)])
    smtp_username = StringField('SMTP username', validators=[Optional(), Length(max=255)])
    smtp_password = PasswordField('SMTP пароль (оставьте пустым, чтобы не менять)', validators=[Optional()])
    smtp_from_address = StringField('Адрес отправителя', validators=[Optional(), Email(message='Некорректный email'), Length(max=255)])
    smtp_use_tls = BooleanField('STARTTLS')
    smtp_use_ssl = BooleanField('SSL')
    base_url = StringField('BASE_URL', validators=[DataRequired(), Length(max=255)])
    max_upload_mb = IntegerField('Лимит размера файла (МБ)', validators=[DataRequired(), NumberRange(min=1, max=10000)])


class TestEmailForm(FlaskForm):
    to_address = StringField('Отправить тест на адрес', validators=[DataRequired(), Email(message='Некорректный email')])
