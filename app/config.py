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

    UPLOAD_DIR = os.path.abspath(os.environ.get('UPLOAD_DIR', os.path.join(basedir, 'uploads')))

    PORT = int(os.environ.get('PORT', 5000))

    # Дефолтный запасной потолок на тело запроса (в дополнение к проверке
    # размера каждого файла по настройке max_upload_mb из БД). Пересчитывается
    # в create_app() после загрузки настроек.
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024 * 20
