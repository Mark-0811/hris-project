from functools import wraps

from flask import abort
from flask_login import current_user

from .menu_access import user_has_menu_access


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role is None or current_user.role.name not in allowed_roles:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator


def menu_access_required(*menu_keys):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not user_has_menu_access(current_user, *menu_keys):
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator
