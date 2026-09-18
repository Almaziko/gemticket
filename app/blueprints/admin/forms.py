from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, IntegerField, BooleanField, TextAreaField
from wtforms.validators import DataRequired, Optional, Length, Email, NumberRange
from wtforms.widgets import HiddenInput

from ...richtext import validate_nonempty_richtext


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
    order = IntegerField('Порядок (сортировка внутри группы)', validators=[DataRequired()])
    color = StringField('Цвет (bootstrap-класс: success/warning/danger/...)', validators=[Optional(), Length(max=20)])
    # choices проставляются в роуте из редактируемых в админке названий групп
    group = SelectField('Группа в списках тикетов', coerce=int, default=1)
    is_default = BooleanField('Начальный статус для новых тикетов')
    is_active = BooleanField('Активен')
    is_final = BooleanField('Финальный статус (клиент не может писать в тикет)')


class StatusGroupNamesForm(FlaskForm):
    group_1 = StringField('Группа 1', validators=[DataRequired(), Length(max=80)])
    group_2 = StringField('Группа 2', validators=[DataRequired(), Length(max=80)])
    group_3 = StringField('Группа 3', validators=[DataRequired(), Length(max=80)])
    group_4 = StringField('Группа 4', validators=[DataRequired(), Length(max=80)])
    group_5 = StringField('Группа 5', validators=[DataRequired(), Length(max=80)])


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
    allowed_extensions = StringField(
        'Разрешённые расширения файлов (через запятую, без точки)',
        validators=[DataRequired(), Length(max=500)],
    )


class TestEmailForm(FlaskForm):
    to_address = StringField('Отправить тест на адрес', validators=[DataRequired(), Email(message='Некорректный email')])


class EmailTemplateForm(FlaskForm):
    subject = StringField('Тема письма', validators=[DataRequired(message='Введите тему'), Length(max=300)])
    body_html = TextAreaField('Текст письма', widget=HiddenInput(), validators=[validate_nonempty_richtext])
