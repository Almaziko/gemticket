import os

from flask import Flask, g, session

from .config import Config
from .extensions import db, csrf


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '', 1)
    os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
    os.makedirs(app.config['UPLOAD_DIR'], exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)

    from .models import User, Notification  # noqa: F401 (регистрация моделей)

    from .blueprints.auth.routes import auth_bp
    from .blueprints.client.routes import client_bp
    from .blueprints.admin.routes import admin_bp
    from .blueprints.tickets.routes import tickets_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(tickets_bp)

    with app.app_context():
        db.create_all()
        from .seed import seed_reference_data, seed_superadmin
        seed_reference_data()
        seed_superadmin(app.config['ADMIN_PASSWORD'])

        from .attachments import refresh_max_content_length
        refresh_max_content_length(app)

    @app.before_request
    def load_current_user():
        g.current_user = None
        user_id = session.get('user_id')
        if user_id:
            g.current_user = User.query.get(user_id)
            if g.current_user is None:
                session.clear()

    @app.context_processor
    def inject_globals():
        unread_count = 0
        recent_notifications = []
        if g.get('current_user'):
            base_q = Notification.query.filter_by(recipient_id=g.current_user.id)
            unread_count = base_q.filter_by(is_read=False).count()
            recent_notifications = base_q.order_by(Notification.created_at.desc()).limit(10).all()
        return dict(
            current_user=g.get('current_user'),
            unread_notifications_count=unread_count,
            recent_notifications=recent_notifications,
        )

    @app.errorhandler(413)
    def too_large(_e):
        from flask import flash, redirect, request
        flash('Загружаемые файлы слишком большие.', 'danger')
        return redirect(request.referrer or '/'), 302

    return app
