from flask import Blueprint

from ..extensions import csrf


bp = Blueprint("mobile", __name__, url_prefix="/api/mobile")
csrf.exempt(bp)


from . import routes  # noqa: E402,F401
