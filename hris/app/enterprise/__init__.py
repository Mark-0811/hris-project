from flask import Blueprint

bp = Blueprint("enterprise", __name__, url_prefix="/enterprise")

from . import routes  # noqa: E402,F401
