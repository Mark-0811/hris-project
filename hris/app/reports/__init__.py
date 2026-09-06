from flask import Blueprint

bp = Blueprint("reports", __name__, url_prefix="/reports")

from . import routes  # noqa: E402,F401
