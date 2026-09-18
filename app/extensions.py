from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
csrf = CSRFProtect()


@event.listens_for(Engine, 'connect')
def _register_unicode_lower_upper(dbapi_connection, connection_record):
    """SQLite-шные LOWER()/UPPER() приводят регистр только у ASCII-букв, а
    .ilike(...) в SQLAlchemy компилируется как lower(x) LIKE lower(y) — из-за
    этого поиск тикетов по кириллическому слову в другом регистре ничего не
    находил. Подменяем встроенные функции на питоновские str.lower()/upper(),
    которые с юникодом работают правильно."""
    if hasattr(dbapi_connection, 'create_function'):
        dbapi_connection.create_function('lower', 1, lambda s: s.lower() if s is not None else None)
        dbapi_connection.create_function('upper', 1, lambda s: s.upper() if s is not None else None)
