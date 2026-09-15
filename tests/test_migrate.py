import sqlite3

from app import create_app


def _make_legacy_db(path):
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(64) NOT NULL UNIQUE,
            password_encrypted BLOB NOT NULL,
            role VARCHAR(20) NOT NULL,
            created_at DATETIME NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE admins (
            id INTEGER PRIMARY KEY REFERENCES users(id),
            is_superadmin BOOLEAN NOT NULL DEFAULT 0
        )
    ''')
    cur.execute('''
        CREATE TABLE statuses (
            id INTEGER PRIMARY KEY,
            name VARCHAR(80) NOT NULL,
            "order" INTEGER NOT NULL DEFAULT 0,
            color VARCHAR(20),
            is_default BOOLEAN NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT 1
        )
    ''')
    cur.execute('''
        CREATE TABLE settings (
            id INTEGER PRIMARY KEY,
            smtp_host VARCHAR(255),
            smtp_port INTEGER,
            smtp_username VARCHAR(255),
            smtp_password_encrypted BLOB,
            smtp_from_address VARCHAR(255),
            smtp_use_tls BOOLEAN NOT NULL DEFAULT 1,
            smtp_use_ssl BOOLEAN NOT NULL DEFAULT 0,
            base_url VARCHAR(255) NOT NULL DEFAULT 'http://localhost:5000',
            max_upload_mb INTEGER NOT NULL DEFAULT 50
        )
    ''')
    cur.executemany(
        'INSERT INTO statuses (name, "order", color, is_default, is_active) VALUES (?, ?, ?, ?, ?)',
        [
            ('Новый', 1, 'secondary', 1, 1),
            ('В работе', 2, 'primary', 0, 1),
            ('Готов', 4, 'success', 0, 1),
            ('Отменён', 5, 'danger', 0, 1),
            ('Кастомный статус клиента', 6, 'dark', 0, 1),
        ]
    )
    cur.execute("INSERT INTO settings (id, base_url, max_upload_mb) VALUES (1, 'https://old.example.com', 50)")
    con.commit()
    con.close()


def test_light_migration_backfills_new_columns_on_legacy_db(tmp_path):
    db_file = tmp_path / 'legacy.db'
    _make_legacy_db(str(db_file))

    upload_dir = tmp_path / 'uploads'
    app = create_app(config_overrides={
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_file}',
        'UPLOAD_DIR': str(upload_dir),
        'WTF_CSRF_ENABLED': False,
        'TESTING': True,
    })

    with app.app_context():
        from app.models import Status, Settings

        gotov = Status.query.filter_by(name='Готов').first()
        otmenen = Status.query.filter_by(name='Отменён').first()
        custom = Status.query.filter_by(name='Кастомный статус клиента').first()
        assert gotov.is_final is True
        assert otmenen.is_final is True
        assert custom.is_final is False

        settings = Settings.query.first()
        assert settings.base_url == 'https://old.example.com'  # не затёрто
        assert settings.allowed_extensions  # дефолт подставлен

        from app.models import Admin
        assert Admin.query.filter_by(is_superadmin=True).count() == 1


def test_migration_is_idempotent_on_rerun(tmp_path):
    db_file = tmp_path / 'legacy2.db'
    _make_legacy_db(str(db_file))
    upload_dir = tmp_path / 'uploads2'
    overrides = {
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_file}',
        'UPLOAD_DIR': str(upload_dir),
        'WTF_CSRF_ENABLED': False,
        'TESTING': True,
    }

    create_app(config_overrides=overrides)
    # второй "деплой" на ту же базу не должен падать
    app2 = create_app(config_overrides=overrides)
    with app2.app_context():
        from app.models import Admin
        assert Admin.query.filter_by(is_superadmin=True).count() == 1
