from ..extensions import db
from .base import TimestampMixin


class BiometricDevice(TimestampMixin, db.Model):
    __tablename__ = "biometric_devices"

    id = db.Column(db.Integer, primary_key=True)
    device_name = db.Column(db.String(120), nullable=False)
    serial_number = db.Column(db.String(120), unique=True, nullable=False)
    location = db.Column(db.String(255))
    ip_address = db.Column(db.String(45))
    api_key = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    logs = db.relationship("BiometricLog", back_populates="device", lazy="dynamic")


class BiometricLog(TimestampMixin, db.Model):
    __tablename__ = "biometric_logs"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey("biometric_devices.id"))
    punch_time = db.Column(db.DateTime, nullable=False, index=True)
    punch_type = db.Column(db.String(40), nullable=False)
    raw_data = db.Column(db.Text)
    source = db.Column(db.String(40), default="api", nullable=False)

    employee = db.relationship("Employee", back_populates="biometric_logs")
    device = db.relationship("BiometricDevice", back_populates="logs")
