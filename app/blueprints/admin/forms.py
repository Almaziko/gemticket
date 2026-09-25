from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, IntegerField, BooleanField, TextAreaField, DateField
from wtforms.validators import DataRequired, Optional, Length, Email, NumberRange, ValidationError

from ...models import SORT_MODE_CHOICES, PRIORITY_CHOICES, PRIORITY_LOW, GROUP_THEME_CHOICES
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
    is_final = BooleanField('Финальный статус (постановщик не может писать в тикет)')
    auto_advance_enabled = BooleanField(
        'Кнопка автоперехода на следующий статус (постановщик нажимает и тикет '
        'сам переходит на следующий статус по общему порядку списка)'
    )
    # Без Optional(): при пустом значении она бы бросала StopValidation и
    # обрывала цепочку до нашего кастомного validate_auto_advance_button_text
    # ниже, из-за чего проверка "текст обязателен, если автопереход включён"
    # никогда бы не сработала.
    auto_advance_button_text = StringField('Текст кнопки', validators=[Length(max=80)])

    def validate_auto_advance_button_text(self, field):
        if self.auto_advance_enabled.data and not (field.data or '').strip():
            raise ValidationError('Укажите текст кнопки — иначе автопереход включить нельзя')

    auto_revert_enabled = BooleanField(
        'Кнопка возврата на доработку (постановщик нажимает и тикет '
        'переходит на предыдущий статус по общему порядку списка)'
    )
    auto_revert_button_text = StringField('Текст кнопки', validators=[Length(max=80)])

    def validate_auto_revert_button_text(self, field):
        if self.auto_revert_enabled.data and not (field.data or '').strip():
            raise ValidationError('Укажите текст кнопки — иначе возврат на доработку включить нельзя')


class StatusGroupSettingsForm(FlaskForm):
    group_1 = StringField('Группа 1', validators=[DataRequired(), Length(max=80)])
    group_2 = StringField('Группа 2', validators=[DataRequired(), Length(max=80)])
    group_3 = StringField('Группа 3', validators=[DataRequired(), Length(max=80)])
    group_4 = StringField('Группа 4', validators=[DataRequired(), Length(max=80)])
    group_5 = StringField('Группа 5', validators=[DataRequired(), Length(max=80)])
    sort_1 = SelectField('Сортировка группы 1', choices=SORT_MODE_CHOICES)
    sort_2 = SelectField('Сортировка группы 2', choices=SORT_MODE_CHOICES)
    sort_3 = SelectField('Сортировка группы 3', choices=SORT_MODE_CHOICES)
    sort_4 = SelectField('Сортировка группы 4', choices=SORT_MODE_CHOICES)
    sort_5 = SelectField('Сортировка группы 5', choices=SORT_MODE_CHOICES)
    theme_1 = SelectField('Оформление группы 1', choices=GROUP_THEME_CHOICES)
    theme_2 = SelectField('Оформление группы 2', choices=GROUP_THEME_CHOICES)
    theme_3 = SelectField('Оформление группы 3', choices=GROUP_THEME_CHOICES)
    theme_4 = SelectField('Оформление группы 4', choices=GROUP_THEME_CHOICES)
    theme_5 = SelectField('Оформление группы 5', choices=GROUP_THEME_CHOICES)


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
    site_name = StringField('Название сайта', validators=[DataRequired(), Length(max=120)])
    favicon = FileField(
        'Иконка сайта (favicon)',
        validators=[FileAllowed(['png', 'jpg', 'jpeg', 'ico', 'svg', 'gif', 'webp'], 'Только изображения')],
    )


class TestEmailForm(FlaskForm):
    to_address = StringField('Отправить тест на адрес', validators=[DataRequired(), Email(message='Некорректный email')])


class EmailTemplateForm(FlaskForm):
    subject = StringField('Тема письма', validators=[DataRequired(message='Введите тему'), Length(max=300)])
    # Без widget=HiddenInput() — см. комментарий в tickets/forms.py: иначе
    # form.hidden_tag() рендерит поле повторно, и сервер читает пустой дубль.
    body_html = TextAreaField('Текст письма', validators=[validate_nonempty_richtext])


class AdminTicketCreateForm(FlaskForm):
    """Тикет "за клиента" — суперадмин заводит его сам (клиент попросил
    по другому каналу связи), но постановщиком остаётся выбранный клиент."""
    client_id = SelectField('Постановщик', coerce=int, validators=[DataRequired(message='Выберите постановщика')])
    assignee_id = SelectField('Исполнитель', coerce=int, validators=[DataRequired(message='Выберите исполнителя')])
    title = StringField('Название', validators=[DataRequired(message='Введите название'), Length(max=80)])
    description = TextAreaField('Описание', validators=[validate_nonempty_richtext])
    deadline = DateField('Дедлайн', validators=[Optional()])
    tracker_id = SelectField('Категория', coerce=int, validators=[DataRequired(message='Выберите категорию')])
    priority = SelectField('Приоритет', choices=PRIORITY_CHOICES, coerce=int, default=PRIORITY_LOW)
