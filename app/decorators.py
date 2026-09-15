from functools import wraps

from flask import g, redirect, url_for, abort


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not g.get('current_user'):
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapped


def client_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not g.get('current_user'):
            return redirect(url_for('auth.login'))
        if g.current_user.role != 'client':
            abort(403)
        return f(*args, **kwargs)
    return wrapped


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not g.get('current_user'):
            return redirect(url_for('auth.login'))
        if g.current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return wrapped


def superadmin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not g.get('current_user'):
            return redirect(url_for('auth.login'))
        if g.current_user.role != 'admin' or not g.current_user.is_superadmin:
            abort(403)
        return f(*args, **kwargs)
    return wrapped
