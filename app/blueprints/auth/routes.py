from flask import Blueprint, render_template, redirect, url_for, session, flash, g, current_app, send_from_directory

from ...models import User
from ...security import hash_password
from .forms import LoginForm

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    if g.get('current_user'):
        return redirect(_home_for(g.current_user))
    return redirect(url_for('auth.login'))


@auth_bp.route('/favicon-file/<path:filename>')
def favicon(filename):
    """Публичная (без логина) отдача иконки сайта — нужна и на странице
    логина, и как favicon вкладки браузера до какой-либо аутентификации."""
    return send_from_directory(current_app.config['UPLOAD_DIR'], filename)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if g.get('current_user'):
        return redirect(_home_for(g.current_user))

    form = LoginForm()
    if form.validate_on_submit():
        pwd_hash = hash_password(form.password.data)
        user = User.query.filter_by(password_hash=pwd_hash).first()
        if user is None:
            flash('Неверный пароль', 'danger')
        else:
            session.clear()
            session['user_id'] = user.id
            return redirect(_home_for(user))

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


def _home_for(user):
    if user.role == 'admin':
        return url_for('admin.dashboard')
    return url_for('client.tickets_list')
