from flask import Blueprint

bp = Blueprint("chat", __name__, url_prefix="/chat")

from . import routes  # noqa: E402,F401
