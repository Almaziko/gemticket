import os
from datetime import date

from flask import Flask, g, session, url_for

from .config import Config
from .extensions import db, csrf


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

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

        from .migrate import run_light_migrations
        run_light_migrations()

        from .seed import seed_reference_data, seed_email_templates, seed_superadmin
        seed_reference_data()
        seed_email_templates()
        seed_superadmin(app.config['ADMIN_PASSWORD'])

        from .attachments import refresh_max_content_length
        refresh_max_content_length(app)

    from .richtext import render_richtext
    app.jinja_env.filters['richtext'] = render_richtext

    if not app.config.get('TESTING'):
        from .overdue import start_overdue_checker
        start_overdue_checker(app)

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
        from .attachments import get_allowed_extensions
        from .models import Settings
        unread_count = 0
        recent_notifications = []
        if g.get('current_user'):
            base_q = Notification.query.filter_by(recipient_id=g.current_user.id)
            unread_count = base_q.filter_by(is_read=False).count()
            recent_notifications = base_q.order_by(Notification.created_at.desc()).limit(10).all()
        settings = Settings.query.first()
        site_name = settings.site_name if settings and settings.site_name else 'GemTicket'
        favicon_url = (
            url_for('auth.favicon', filename=settings.favicon_filename)
            if settings and settings.favicon_filename else None
        )
        return dict(
            current_user=g.get('current_user'),
            unread_notifications_count=unread_count,
            recent_notifications=recent_notifications,
            allowed_extensions=get_allowed_extensions(),
            today=date.today(),
            site_name=site_name,
            favicon_url=favicon_url,
        )

    @app.errorhandler(413)
    def too_large(_e):
        from flask import flash, redirect, request
        flash('Загружаемые файлы слишком большие.', 'danger')
        return redirect(request.referrer or '/'), 302

    return app
