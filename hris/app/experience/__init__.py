from flask import Blueprint

bp = Blueprint("experience", __name__, url_prefix="/me")

from . import routes  # noqa: E402,F401
