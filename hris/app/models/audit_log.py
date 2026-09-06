from ..extensions import db
from .base import TimestampMixin


class AuditLog(TimestampMixin, db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    module = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    record_id = db.Column(db.String(80))
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
