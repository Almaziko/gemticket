import os

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    FERNET_KEY = os.environ.get('FERNET_KEY')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')

    # Абсолютный путь обязателен: Flask-SQLAlchemy резолвит относительные
    # sqlite-пути относительно app.instance_path, что даёт задвоение вида
    # instance/instance/gemticket.db, если передать сюда что-то относительное.
    _db_path = os.path.abspath(os.environ.get('DATABASE', os.path.join(basedir, 'instance', 'gemticket.db')))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + _db_path.replace(os.sep, '/')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # По умолчанию Flask-WTF считает CSRF-токен просроченным через час — если
    # страницу тикета открыть и не торопясь написать комментарий (или просто
    # оставить вкладку открытой), сабмит уже после истечения часа падал с
    # "The CSRF token has expired", а введённый текст комментария терялся.
    # Токен всё равно привязан к сессии и проверяется на каждый POST — просто
    # без искусственного лимита по времени.
    WTF_CSRF_TIME_LIMIT = None

    UPLOAD_DIR = os.path.abspath(os.environ.get('UPLOAD_DIR', os.path.join(basedir, 'uploads')))

    PORT = int(os.environ.get('PORT', 5000))

    # SMTP-релей — Unisender Go, у которого свой шаблонизатор с тем же
    # синтаксисом {{ }} (например, {{UnsubscribeUrl}} он сам подставляет
    # при отправке). Этот заголовок просит его не переписывать ссылки и не
    # вставлять пиксель трекинга; когда Unisender разрешит skip_unsubscribe
    # — поменять только значение здесь (или через env EMAIL_UNISENDER_GO_HEADER),
    # без правки кода, и одновременно обнулить EMAIL_FOOTER_HTML/_PLAIN ниже,
    # раз обязательную ссылку отписки будет вставлять сам Unisender.
    EMAIL_UNISENDER_GO_HEADER = os.environ.get(
        'EMAIL_UNISENDER_GO_HEADER',
        '{"track_links":0,"track_read":0}',
    )

    # Дописывается ко ВСЕМ исходящим письмам после рендера шаблона (и в
    # html, и в plain-текст — какая версия есть у конкретного письма), сам
    # шаблон его не содержит и не хранит. {{UnsubscribeUrl}} здесь — тот же
    # сквозной плейсхолдер Unisender Go (см. PASSTHROUGH_TEMPLATE_VARS в
    # notifications.py), в рендер шаблона эта строка не попадает вообще,
    # поэтому дополнительно защищать её не нужно.
    EMAIL_FOOTER_HTML = os.environ.get(
        'EMAIL_FOOTER_HTML',
        '<p style="font-size:12px;color:#888;margin-top:24px">Вы получили это письмо как участник заявки. '
        '<a href="{{UnsubscribeUrl}}" style="color:#888">Отключить уведомления</a></p>',
    )
    EMAIL_FOOTER_PLAIN = os.environ.get(
        'EMAIL_FOOTER_PLAIN',
        'Отключить уведомления: {{UnsubscribeUrl}}',
    )

    # Дефолтный запасной потолок на тело запроса (в дополнение к проверке
    # размера каждого файла по настройке max_upload_mb из БД). Пересчитывается
    # в create_app() после загрузки настроек.
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024 * 20
