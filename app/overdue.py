"""
Фоновая проверка просроченных дедлайнов -> письмо суперадминам.

Запускается одним потоком при старте приложения (см. create_app()). Полагается
на то, что gunicorn запущен с --preload (см. Dockerfile) — тогда импорт
приложения и, соответственно, этот поток, выполняются один раз в
арбитр-процессе ДО форка воркеров, и после fork() поток не дублируется на
каждого воркера (тот же приём, что уже используется для устранения гонки в
seed_superadmin). Без --preload с несколькими воркерами поток запустился бы
в каждом из них и дублировал письма — для локального запуска (один процесс)
это не проблема.
"""
import threading
import time
from datetime import date

from .extensions import db
from .models import Ticket, Status, Admin
from . import notifications as notif

CHECK_INTERVAL_SECONDS = 3600
INITIAL_DELAY_SECONDS = 60


def check_overdue_tickets():
    overdue_tickets = (
        Ticket.query.join(Status)
        .filter(Ticket.deadline.isnot(None))
        .filter(Ticket.deadline < date.today())
        .filter(Status.is_final.is_(False))
        .filter(Ticket.overdue_notified.is_(False))
        .all()
    )
    if not overdue_tickets:
        return

    superadmins = Admin.query.filter_by(is_superadmin=True).all()
    for ticket in overdue_tickets:
        for admin in superadmins:
            notif.notify_deadline_overdue(ticket, admin)
        ticket.overdue_notified = True
    db.session.commit()


def start_overdue_checker(app):
    def loop():
        time.sleep(INITIAL_DELAY_SECONDS)
        while True:
            with app.app_context():
                try:
                    check_overdue_tickets()
                except Exception:
                    app.logger.exception('Ошибка проверки просроченных дедлайнов')
            time.sleep(CHECK_INTERVAL_SECONDS)

    threading.Thread(target=loop, daemon=True).start()
