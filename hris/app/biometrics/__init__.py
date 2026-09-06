from flask import Blueprint

bp = Blueprint("biometrics", __name__, url_prefix="/api/biometric")

from . import routes  # noqa: E402,F401
