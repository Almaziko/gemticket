from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import Admin, Status, Tracker, Settings, User
from .security import hash_password, encrypt_secret


def seed_reference_data():
    if Status.query.count() == 0:
        for name, order, is_default, color in (
            ('Новый', 1, True, 'secondary'),
            ('В работе', 2, False, 'primary'),
            ('На проверке', 3, False, 'warning'),
            ('Готов', 4, False, 'success'),
            ('Отменён', 5, False, 'danger'),
        ):
            db.session.add(Status(name=name, order=order, is_default=is_default, color=color, is_active=True))

    if Tracker.query.count() == 0:
        for name, order in (('Баг', 1), ('Доработка', 2), ('Задача', 3)):
            db.session.add(Tracker(name=name, order=order, is_active=True))

    if Settings.query.count() == 0:
        from flask import current_app
        db.session.add(Settings(id=1, base_url=current_app.config.get('BASE_URL', 'http://localhost:5000'), max_upload_mb=50))

    db.session.commit()


def seed_superadmin(admin_password):
    if Admin.query.count() > 0:
        return

    if not admin_password:
        raise RuntimeError(
            'В базе нет ни одного админа, а переменная окружения ADMIN_PASSWORD не задана. '
            'Задайте ADMIN_PASSWORD и перезапустите приложение.'
        )

    pwd_hash = hash_password(admin_password)
    if User.query.filter_by(password_hash=pwd_hash).first():
        raise RuntimeError(
            'Пароль из ADMIN_PASSWORD уже занят другим пользователем в базе. Смените ADMIN_PASSWORD.'
        )

    admin = Admin(
        name='Суперадмин',
        email='admin@gemticket.local',
        password_hash=pwd_hash,
        password_encrypted=encrypt_secret(admin_password),
        is_superadmin=True,
    )
    db.session.add(admin)
    try:
        db.session.commit()
    except IntegrityError:
        # Гонка между несколькими воркерами при первом старте (обычно
        # предотвращается флагом --preload у gunicorn) — если админа уже
        # успел создать другой процесс, просто ничего не делаем.
        db.session.rollback()
